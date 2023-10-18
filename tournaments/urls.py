from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('profile/', views.profile, name='profile'),
    path('', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('<str:tournament_name>/overall_standings/', views.team_standings, name='team_standings'),
    path('update_standings/', views.update_standings, name='update_standings'),
    path('create_tournament/', views.create_tournament, name='create_tournament'),
    path('update_match/<int:match_schedule_id>/', views.update_match, name='update_match'),
    path('update_match/<int:match_schedule_id>/save/', views.save_match, name='save_match'),
    path('<str:tournament_name>/<int:match_number>/winner/', views.set_winner_and_kills, name='set_winner_and_kills'),
    # path('<str:tournament_name>/<int:match_number>/add_points/', views.add_points_to_teams, name='add_points_to_teams'),
    path('<str:tournament_name>/<int:match_number>/add_points/', views.add_points_to_teams, name='add_points_to_teams'),
    # path('add_points_to_teams/<str:tournament_name>/<int:match_number>/', views.add_points_to_teams, name='add_points_to_teams')
    path('save_points_to_database/<str:tournament_name>/<int:match_number>/', views.save_points_to_database, name='save_points_to_database')

    # path('update_match_card/<int:match_schedule_id>/', views.update_match_card, name='update_match_card'),

    # Other app-specific URLs can be added here
]