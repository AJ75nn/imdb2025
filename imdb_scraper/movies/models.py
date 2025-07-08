from django.db import models

class Movie(models.Model):
    title = models.CharField(max_length=255)
    year = models.IntegerField()
    imdb_id = models.CharField(max_length=20, unique=True)
    poster_url = models.URLField(max_length=500, blank=True, null=True)
    plot_summary = models.TextField(blank=True, null=True)
    release_date = models.DateField(blank=True, null=True)
    genres = models.ManyToManyField('Genre', blank=True, related_name='movies')

    def __str__(self):
        return f"{self.title} ({self.year})"

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
