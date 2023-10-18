# tournaments/views.py
from django.contrib.auth.models import User
from django.shortcuts import render, redirect,get_object_or_404 
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from .models import Tournament,OverallStandings,MatchSchedule,MatchResult,Group,Team
from django.http import HttpResponse , Http404 , HttpResponseRedirect , JsonResponse
from django.urls import reverse
from django.db.models import F,Q
import json
from django.template.context_processors import csrf




def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('profile')  # Redirect to the user's profile page
        else:
            return render(request, 'tournaments/registration/login.html')


def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        email = request.POST['email']
        
        # Create a new user
        user = User.objects.create_user(username=username, password=password, email=email)
        user.save()
        
        # Log in the user
        login(request, user)
        
        return redirect('profile')  # Redirect to the user's profile page

    return render(request, 'registration/register.html')

@login_required
def profile(request):
    # Retrieve tournaments associated with the current user
    user_tournaments = Tournament.objects.filter(user=request.user)

    context = {
        'user_tournaments': user_tournaments,
    }
    return render(request, 'registration/profile.html', context)

def team_standings(request, tournament_name):
    # Retrieve team data and sort it based on criteria for the specified tournament
    teams = OverallStandings.objects.filter(tournament__name=tournament_name).order_by(
        '-total_points',  # Sort by total points (highest to lowest)
        '-total_position_points',  # In case of a tie, sort by position points
        '-total_finishes_points',  # In case of a tie, sort by finishes points
        '-total_wins'  # In case of a tie, sort by total wins
    )

    return render(request, 'standings/team_standings.html', {'teams': teams, 'tournament_name': tournament_name})


def update_standings(request):
    # Retrieve the tournament and match schedule information
    tournament = Tournament.objects.get(user=request.user)  # Replace with your own logic to get the tournament
    match_schedules = MatchSchedule.objects.filter(tournament=tournament)

    # Check if the number of match schedules matches the defined no_of_matches
    no_of_matches_defined = tournament.no_of_matches
    no_of_matches_created = match_schedules.count()

    if no_of_matches_created < no_of_matches_defined:
        # Create missing match schedules
        for i in range(no_of_matches_created + 1, no_of_matches_defined + 1):
            MatchSchedule.objects.create(tournament=tournament, match_number=i, map="TBD")

        # Fetch the updated match schedules
        match_schedules = MatchSchedule.objects.filter(tournament=tournament)

    return render(request, 'standings/update_standings.html', {'match_schedules': match_schedules})


def update_match(request, match_schedule_id):
    match_schedule = get_object_or_404(MatchSchedule, pk=match_schedule_id)
    # In your view function
    all_groups = Group.objects.all()  # Fetch all groups

    # If the request method is not POST, display the form
    return render(request, 'match/update_match.html', {'match_schedule': match_schedule,'all_groups': all_groups})

def save_match(request, match_schedule_id):
    match_schedule = get_object_or_404(MatchSchedule, pk=match_schedule_id)

    if request.method == 'POST':
        map = request.POST.get('map')
        group_ids = request.POST.getlist('groups')

        # Update map if a new value is provided
        if map:
            match_schedule.map = map

        # Handle group selections (checkboxes)
        if group_ids:
            groups = Group.objects.filter(id__in=group_ids)
            match_schedule.groups.set(groups)

        # Save the updated match schedule
        match_schedule.save()

        # Generate the URL for 'set_winner_and_kills' and provide the required parameters
        url = reverse('set_winner_and_kills', kwargs={'tournament_name': match_schedule.tournament.name, 'match_number': match_schedule.match_number})

        # Redirect to the generated URL
        return redirect(url)

    # If the request method is not POST, you can handle it as needed.
    return redirect('update_match', match_schedule_id=match_schedule_id)


def set_winner_and_kills(request, tournament_name, match_number):
    # Retrieve the tournament and match schedule using the provided names and numbers
    tournament = get_object_or_404(Tournament, name=tournament_name)
    match_schedule = get_object_or_404(MatchSchedule, tournament=tournament, match_number=match_number)

    # Fetch teams from the match groups associated with this match_schedule
    match_groups = match_schedule.groups.all()
    teams_in_match_groups = Team.objects.filter(groups__in=match_groups).distinct()

    if request.method == 'POST':
        # Handle form data
        winner_name = request.POST.get('winner_name')
        kills = request.POST.get('kills')

        # Check if a new winner is selected
        if winner_name:
            winner_team = Team.objects.get(name=winner_name)

            # Retrieve the previous winning team (if any)
            previous_winner = match_schedule.winning_team

            if previous_winner == winner_team:
                # Update scores for the current winning team without resetting to 0
                winner_match_result, created = MatchResult.objects.get_or_create(
                    tournament=tournament,
                    team=winner_team,
                    match_schedule=match_schedule,
                )

                # Set finishes_points to kills (you can add your own processing logic here)
                if kills:
                    winner_match_result.finishes_points = int(kills)

                winner_match_result.save()
            else:
                # Set the previous winner's scores to 0 and reduce total_wins
                if previous_winner:
                    previous_winner_match_result = MatchResult.objects.filter(
                        tournament=tournament,
                        team=previous_winner,
                        match_schedule=match_schedule,
                    ).first()

                    if previous_winner_match_result:
                        # Reset scores to 0
                        previous_winner_match_result.position_points = 0
                        previous_winner_match_result.finishes_points = 0
                        previous_winner_match_result.save()

                        # Reduce total_wins by 1
                        previous_winner_overall_standings = OverallStandings.objects.get(
                            team=previous_winner,
                            tournament=tournament
                        )
                        previous_winner_overall_standings.total_wins -= 1
                        previous_winner_overall_standings.save()

                # Update the winner's name
                match_schedule.winning_team = winner_team
                match_schedule.save()  # Save the match_schedule with the updated winner

                # Calculate and update position_points and finishes_points for the new winning team
                winner_match_result, created = MatchResult.objects.get_or_create(
                    tournament=tournament,
                    team=winner_team,
                    match_schedule=match_schedule,
                    finishes_points=kills,
                    position_points=15,
                )

                winner_match_result.save()

        # Update kills (you can add your own processing logic here)
        if kills:
            match_schedule.kills = int(kills)
            match_schedule.save()  # Save the match_schedule with updated kills and position points

        # Redirect to a success page or any other page as needed
        return HttpResponseRedirect(reverse('add_points_to_teams', args=[tournament_name, match_number]))

    return render(request, 'match/set_winner_and_kills.html', {
        'match_schedule': match_schedule,
        'teams_in_match_groups': teams_in_match_groups,
    })

     
def add_points_to_teams(request, tournament_name, match_number):
    # Retrieve the tournament and match schedule using the provided names and numbers
    tournament = get_object_or_404(Tournament, name=tournament_name)
    match_schedule = get_object_or_404(MatchSchedule, tournament=tournament, match_number=match_number)
    
    # Get the map associated with the match_schedule
    map_name = match_schedule.map
    
    # Retrieve the groups associated with the match_schedule
    groups = match_schedule.groups.all()
    
    # Identify the winning team for this match_schedule
    winning_team = match_schedule.winning_team

    # Fetch teams for the dropdown, excluding the winning team
    teams = Team.objects.filter(groups__in=groups).exclude(id=winning_team.id)

    if request.method == 'POST':
        # Handle form submission here
        # You can access the selected team, position points, and finishes points from request.POST

        # Create a MatchResult object for the selected team and match schedule
        selected_team_id = request.POST.get('selected_team')
        selected_team = Team.objects.get(id=selected_team_id)
        position_points = request.POST.get('position_points')
        finishes_points = request.POST.get('finishes_points')

        # Check if a MatchResult already exists for this team and match schedule
        try:
            match_result = MatchResult.objects.get(
                tournament=tournament,
                team=selected_team,
                match_schedule=match_schedule
            )
        except MatchResult.DoesNotExist:
            # If it doesn't exist, create a new MatchResult
            match_result = MatchResult(
                tournament=tournament,
                team=selected_team,
                match_schedule=match_schedule
            )

        # Update position_points and finishes_points for the selected team
        if position_points:
            match_result.position_points = int(position_points)
        if finishes_points:
            match_result.finishes_points = int(finishes_points)

        # Save the MatchResult
        match_result.save()

        # Redirect to a success page or any other page as needed
        return HttpResponse("Points added successfully")

    # If the request method is not POST, display the form
    return render(request, 'match/add_points.html', {
        'tournament': tournament,
        'map_name': map_name,
        'groups': groups,
        'winning_team': winning_team,
        'teams': teams,
    })

from django.http import JsonResponse
import json
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET", "POST"])
def save_points_to_database(request, tournament_name, match_number):
    # Retrieve the tournament and match schedule using the provided names and numbers
    tournament = get_object_or_404(Tournament, name=tournament_name)
    match_schedule = get_object_or_404(MatchSchedule, tournament=tournament, match_number=match_number)
    
    # Handle form submission
    data = request.POST

    # Extract the relevant data
    selected_team_id = data.get('selected_team')
    position_points = data.get('position_points')
    finishes_points = data.get('finishes_points')

    # Make sure the necessary fields are provided
    if not (selected_team_id and position_points and finishes_points):
        return JsonResponse({'message': 'Please provide all required fields'}, status=400)

    # Get the selected team and other required data
    selected_team = get_object_or_404(Team, id=selected_team_id)

    # Check if a MatchResult already exists for this team and match schedule
    match_result, created = MatchResult.objects.get_or_create(
        tournament=tournament,
        team=selected_team,
        match_schedule=match_schedule,
        tournament_name= tournament_name,
        match_number = match_number
    )

    # Update position_points and finishes_points for the selected team
    if position_points:
        match_result.position_points = int(position_points)
    if finishes_points:
        match_result.finishes_points = int(finishes_points)

    # Save the MatchResult
    match_result.save()

    return JsonResponse({'message': 'Data saved successfully'})



def create_tournament(request):
    # Implement the logic to create tournaments here
    return render(request, 'create_tournament.html')
