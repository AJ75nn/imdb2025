import requests
import re # Import regular expression module
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from movies.models import Movie, Genre # Import Genre model
from datetime import datetime

# Base URL for IMDb's list of 2025 movies.
# This URL might need to be updated if IMDb changes its structure.
# A more robust solution would involve finding this URL dynamically or using an API.
IMDB_2025_MOVIES_URL = "https://www.imdb.com/calendar/?ref_=watch_tpks_nv_menu"

class Command(BaseCommand):
    help = 'Scrapes IMDb for 2025 movies and stores them in the database'

    def handle(self, *args, **options):
        # --- Temporary debug: Print existing poster URLs ---
        self.stdout.write(self.style.SUCCESS("--- Checking existing poster URLs for some 2025 movies ---")) # Changed to SUCCESS for visibility
        existing_movies = Movie.objects.filter(year=2025).order_by('title')[:5]
        if not existing_movies:
            self.stdout.write(self.style.SUCCESS("No existing 2025 movies found in DB to check poster URLs."))
        else:
            for movie_obj in existing_movies:
                self.stdout.write(self.style.SUCCESS(f"  Movie: {movie_obj.title}, Stored Poster URL: {movie_obj.poster_url}"))
        self.stdout.write(self.style.SUCCESS("--- End of existing poster URL check ---"))
        # --- End Temporary debug ---

        self.stdout.write(self.style.SUCCESS('Starting IMDb scrape for 2025 movies...'))

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            response = requests.get(IMDB_2025_MOVIES_URL, headers=headers)
            response.raise_for_status()  # Raise an exception for bad status codes
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f'Error fetching IMDb page: {e}'))
            return

        soup = BeautifulSoup(response.content, 'html.parser')

        # IMDb's HTML structure can change. These selectors are guesses for the /calendar page.
        # Option 1: Try to find release cards
        movie_items = soup.select('div[data-testid="release-card"]')

        # Option 2: If no release cards, try another common list item selector (more generic)
        if not movie_items:
            movie_items = soup.select('li.ipc-metadata-list-summary-item') # Common for modern IMDb lists

        # Option 3: A more general article approach if the above fail
        if not movie_items:
            movie_items = soup.select('article.ipc-article')


        if not movie_items:
            self.stdout.write(self.style.WARNING('No movie items found. The IMDb page structure for /calendar is different or the list is empty.'))
            self.stdout.write(self.style.WARNING(f'Please verify the URL and selectors: {IMDB_2025_MOVIES_URL}'))
            # For debugging, you can save the HTML content:
            # with open("imdb_page_content.html", "w", encoding="utf-8") as f:
            # f.write(soup.prettify())
            # self.stdout.write(self.style.WARNING('Saved page content to imdb_page_content.html for inspection.'))
            return

        scraped_count = 0
        updated_count = 0
        skipped_count = 0

        for item in movie_items:
            try:
                # Title, Year, and Link from <a class="ipc-metadata-list-summary-item__t" ...>
                title_link_tag = item.select_one('a.ipc-metadata-list-summary-item__t')

                if not title_link_tag or not title_link_tag.has_attr('href'):
                    self.stdout.write(self.style.WARNING('Skipping item: Title link or href not found with "a.ipc-metadata-list-summary-item__t".'))
                    skipped_count += 1
                    continue

                full_title_text = title_link_tag.get_text(strip=True) # E.g., "Superman (2025)"
                href = title_link_tag['href']

                # Extract IMDb ID
                if '/title/tt' not in href:
                    self.stdout.write(self.style.WARNING(f"Skipping item '{full_title_text}', IMDb ID not found in href: {href}"))
                    skipped_count += 1
                    continue
                imdb_id_raw = href.split('/title/')[1].split('/')[0]

                # Parse Title and Year from full_title_text
                title = full_title_text
                year = None
                release_date_obj = None # Calendar page has release dates, this could be parsed

                # Attempt to parse year from "Title (YYYY)" format
                if full_title_text.endswith(')'):
                    year_match = re.search(r'\((\d{4})\)$', full_title_text)
                    if year_match:
                        year = int(year_match.group(1))
                        title = full_title_text[:year_match.start()].strip() # Remove year part from title
                    else: # Sometimes it might be (I) (2025) or similar
                        year_match_complex = re.search(r'\((\w+\s)?(\d{4})\)$', full_title_text)
                        if year_match_complex:
                            year = int(year_match_complex.group(2))
                            title = full_title_text[:year_match_complex.start()].strip()


                # If year couldn't be parsed from title, it might be in a separate element or section header.
                # The calendar page is organized by dates. We need to find the date context.
                # For now, if not in title, we'll default to 2025 if the *section* is for 2025.
                # This part is still tricky without seeing the broader page structure around items.
                # The provided snippet is for one item, not its date section.
                # For now, we rely on year in title, or skip if not 2025.

                if year is None: # If year not found in title text
                    # We need a strategy for year if not in title.
                    # For the calendar page, movies are usually grouped under date headings.
                    # A robust scraper would find the closest preceding date heading.
                    # For now, if we can't get it from title, we can't be sure it's 2025.
                    self.stdout.write(self.style.WARNING(f"Skipping '{title}': Year not found in title text and no date context parsing implemented yet."))
                    skipped_count += 1
                    continue

                if year != 2025: # Filter for 2025 movies
                    self.stdout.write(self.style.NOTICE(f"Skipping '{title}' (Year: {year}) as it's not a 2025 film."))
                    skipped_count += 1
                    continue

                # Refined Poster URL extraction
                poster_img_tag = item.select_one('div.ipc-poster div.ipc-media img.ipc-image') # More specific selector
                poster_url_str = None # Use a temporary variable for the raw extracted string
                poster_url = None     # Final URL to be stored

                poster_img_tag = item.select_one('img.ipc-image')

                if poster_img_tag:
                    if poster_img_tag.has_attr('srcset'):
                        actual_srcset = poster_img_tag['srcset']
                        srcset_matches = re.findall(r'(\S+?)\s+(\d+w)', actual_srcset)

                        if srcset_matches:
                            best_url = None
                            max_width = 0
                            for url, width_descriptor in srcset_matches:
                                try:
                                    current_width = int(width_descriptor[:-1])
                                    if current_width > max_width:
                                        max_width = current_width
                                        best_url = url
                                except ValueError:
                                    if not best_url: best_url = url # Fallback if width parse fails

                            if best_url:
                                poster_url_str = best_url
                            elif srcset_matches: # Fallback if all width parsing failed
                                poster_url_str = srcset_matches[0][0]
                        # else:
                        #     self.stdout.write(self.style.WARNING(f"    No regex matches in srcset for {title}: {actual_srcset}"))
                    elif poster_img_tag.has_attr('src'):
                        poster_url_str = poster_img_tag['src']
                    # else:
                    #    self.stdout.write(self.style.WARNING(f"    No src or srcset found for {title} on poster_img_tag"))
                # else:
                #    self.stdout.write(self.style.WARNING(f"    No poster_img_tag found for {title} using 'img.ipc-image'"))

                # Validate and process the extracted URL
                if poster_url_str and poster_url_str.startswith('http'):
                    # It's a full URL, proceed with V1 processing if applicable
                    if '._V1_' in poster_url_str and not poster_url_str.endswith('_AL_.jpg'):
                        # Attempt to get a standard high-quality version
                        base_poster_url = poster_url_str.split('._V1_')[0]
                        poster_url = f"{base_poster_url}._V1_QL75_UX380_CR0,0,380,562_.jpg"
                    else:
                        # Already a full URL, might be fine as is (e.g. already _AL_.jpg or no _V1_ part)
                        poster_url = poster_url_str
                else:
                    if poster_url_str: # It was extracted but isn't a full URL
                        self.stdout.write(self.style.WARNING(f"Movie: {title} - Extracted poster_url '{poster_url_str}' is not a full URL. Storing None."))
                    # poster_url remains None if not a valid absolute URL or not found

                # Plot Summary - not in the provided snippet for the list item
                plot_summary = "Plot summary not available on calendar page."

                # TODO: Parse actual release date from the page if possible
                # For now, release_date_obj remains None.

                # Scrape Genres
                movie_genres = []
                genre_ul_tag = item.select_one('ul.ipc-metadata-list-summary-item__tl')
                if genre_ul_tag:
                    genre_span_tags = genre_ul_tag.select('span.ipc-metadata-list-summary-item__li')
                    for span_tag in genre_span_tags:
                        genre_name = span_tag.get_text(strip=True)
                        if genre_name:
                            genre, _ = Genre.objects.get_or_create(name=genre_name)
                            movie_genres.append(genre)

                defaults_dict = {
                    'title': title,
                    'year': year,
                    'poster_url': poster_url,
                    'plot_summary': plot_summary,
                    'release_date': release_date_obj,
                }

                movie, created = Movie.objects.update_or_create(
                    imdb_id=imdb_id_raw,
                    defaults=defaults_dict
                )

                if movie_genres:
                    movie.genres.set(movie_genres) # Set the genres for the movie

                if created:
                    self.stdout.write(self.style.SUCCESS(f'Successfully scraped and saved: {movie.title} (Genres: {[g.name for g in movie_genres]})'))
                    scraped_count += 1
                else:
                    self.stdout.write(self.style.NOTICE(f'Successfully updated: {movie.title}'))
                    updated_count +=1

            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error processing item: {e}'))
                self.stderr.write(self.style.ERROR(f'Problematic item HTML snippet: {item.prettify()[:500]}...')) # Log part of the item
                skipped_count +=1

        self.stdout.write(self.style.SUCCESS(f'IMDb scrape finished. {scraped_count} new movies added, {updated_count} movies updated, {skipped_count} movies skipped/errored.'))

    def get_movie_details(self, movie_url_path):
        # This function would be used if we wanted to scrape individual movie pages
        # for more details (e.g., full cast, more reliable release date, genres).
        # For this initial task, we are keeping it simpler by only using the list page.
        # Example:
        # detail_url = f"https://www.imdb.com{movie_url_path}"
        # response = requests.get(detail_url, headers=self.headers)
        # soup = BeautifulSoup(response.content, 'html.parser')
        # ... extract more details ...
        pass
