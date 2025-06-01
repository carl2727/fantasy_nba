from django.urls import path, include
from . import views

urlpatterns = [
    path('show_ratings/', views.show_ratings, name='show_ratings'),
    # path('ratings/sort/<str:sort_by>/', views.show_ratings, name='sort_ratings_explicit'), # Keep if you use explicit path-based sorting
    path('sort_ratings/', views.sort_ratings, name='sort_ratings'), # For query param based sorting (ensure this points to the correct sort view)
    path('punt/', views.punt, name='punt'),
    path('breakdown/', views.breakdown, name='breakdown'),
    path('team/', views.team, name='team'),
    path('create_team/', views.create_team, name='create_team'),
    path('update_player_status/', views.update_player_status, name='update_player_status'), # New primary endpoint for player status
    
    # Authentication related URLs
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/login_register/', views.login_register, name='login_register'), # Your custom login/register page
    path('accounts/', include('django.contrib.auth.urls')), # Standard Django auth URLs (password reset, etc.)

    # Old, now deprecated player management URLs (can be removed)
    # path('add_player/', views.add_player, name='add_player'),
    # path('remove_player/', views.remove_player, name='remove_player'),
    # path('toggle_availability/', views.toggle_availability, name='toggle_availability'),
]