from django.urls import path, include
from . import views

urlpatterns = [
    path('ratings/', views.show_ratings, name='show_ratings'),
    path('sort_ratings/', views.show_ratings, name='sort_ratings'),
    path('punt/', views.punt, name='punt'),
    path('breakdown/', views.breakdown, name='breakdown'),
    path('team/', views.team, name='team'),
    path('create_team/', views.create_team, name='create_team'),
    path('team/<int:team_id>/edit/', views.edit_team, name='edit_team'),
    path('team/<int:team_id>/activate/', views.activate_team, name='activate_team'),
    path('team/<int:team_id>/delete/', views.delete_team, name='delete_team'),
    path('update_player_status/', views.update_player_status, name='update_player_status'),
    path('move_draft_pick/', views.move_draft_pick, name='move_draft_pick'),
    path('toggle_highlight/', views.toggle_highlight, name='toggle_highlight'),
    path('toggle_injured/', views.toggle_injured, name='toggle_injured'),
    path('toggle_categories/', views.toggle_categories, name='toggle_categories'),
    path('set_draft_order/', views.set_draft_order, name='set_draft_order'),
    
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/login_register/', views.login_register, name='login_register'),
    path('accounts/', include('django.contrib.auth.urls')),

]