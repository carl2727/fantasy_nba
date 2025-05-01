from django.urls import path
from . import views

urlpatterns = [
    path('show_ratings/', views.show_ratings, name='show_ratings'),
    path('sort_ratings/', views.sort_ratings, name='sort_ratings'),
    path('blog/', views.blog, name='blog'),
]