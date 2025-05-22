from django.urls import path, include
from . import views

urlpatterns = [
    path('show_ratings/', views.show_ratings, name='show_ratings'),
    path('sort_ratings/', views.sort_ratings, name='sort_ratings'),
    path('punt/', views.punt, name='punt'),
    path('breakdown/', views.breakdown, name='breakdown'),
    path('team/', views.team, name='team'),
    path('create_team/', views.create_team, name='create_team'),
    path('add_player/', views.add_player, name='add_player'),
    path('remove_player/', views.remove_player, name='remove_player'),
    path('toggle_availability/', views.toggle_availability, name='toggle_availability'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/', views.login_register, name='login_register'),
    path('accounts/', include('django.contrib.auth.urls')),
] 