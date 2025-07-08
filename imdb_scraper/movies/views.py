from django.shortcuts import render
from .models import Movie, Genre # Import Genre model
from django.db.models import Count, Q as QueryObject # Import Q
from django.db import models # Import models for models.Q

def movie_list(request):
    selected_genre_name = request.GET.get('genre')

    movies_query = Movie.objects.filter(year=2025)

    if selected_genre_name:
        try:
            # Filter by movies that have the selected genre
            movies_query = movies_query.filter(genres__name=selected_genre_name)
        except Genre.DoesNotExist: # Should not happen if genre name comes from valid list
            pass

    movies = movies_query.order_by('title')

    # Get all genres that are actually associated with 2025 movies for the filter dropdown
    # Order them by name for consistent display
    # Annotate with movie_count to only show genres that have 2025 movies
    available_genres = Genre.objects.filter(movies__year=2025).distinct().annotate(
        num_movies=Count('movies', filter=models.Q(movies__year=2025))
    ).filter(num_movies__gt=0).order_by('name')

    context = {
        'movies': movies,
        'movie_count': movies.count(),
        'available_genres': available_genres,
        'selected_genre': selected_genre_name
    }
    return render(request, 'movies/movie_list.html', context)
