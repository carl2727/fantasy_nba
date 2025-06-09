from django.urls import path, include
from . import views

urlpatterns = [
    path('ratings/', views.show_ratings, name='show_ratings'),
    path('sort_ratings/', views.show_ratings, name='sort_ratings'),
    path('punt/', views.punt, name='punt'),
    path('breakdown/', views.breakdown, name='breakdown'),
    path('team/', views.team, name='team'),
    path('create_team/', views.create_team, name='create_team'),
    path('update_player_status/', views.update_player_status, name='update_player_status'),
    
    # Authentication related URLs
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/login_register/', views.login_register, name='login_register'),
    path('accounts/', include('django.contrib.auth.urls')),

]