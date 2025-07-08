from django.shortcuts import render
from .models import Movie

def movie_list(request):
    movies = Movie.objects.filter(year=2025).order_by('title')
    # You could also order by release_date if it were reliably populated:
    # movies = Movie.objects.filter(year=2025).order_by('release_date', 'title')

    context = {
        'movies': movies,
        'movie_count': movies.count()
    }
    return render(request, 'movies/movie_list.html', context)
