from django.contrib import admin
from django.urls import path, include
from fantasy_nba.views import show_ratings, health_check  # Import the views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),  # Health check endpoint for Render
    path('', show_ratings, name='landing_page'),  # Set show_ratings as the landing page
    path('fantasy_nba/', include('fantasy_nba.urls')),  # Include other app URLs
]