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
from PIL import Image, ImageDraw, ImageFont
from django.db.models import Sum
from django.db.models import Subquery
import io,os




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


# Define a helper function to calculate team-specific data
def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

def team_standings(request, tournament_name):
    try:
        tournament = Tournament.objects.get(name=tournament_name)
        teams = Team.objects.filter(tournaments=tournament)
        
        # Handle the selected match using the GET parameter
        selected_match = request.GET.get('selected_match', 'overall')
        match_results = MatchResult.objects.filter(tournament=tournament)
        if selected_match != 'overall':
            match_results = match_results.filter(match_schedule__match_number=selected_match)

        # Calculate team-specific data
        team_data = []
        for team in teams:
            team_match_results = match_results.filter(team=team)
            total_points = sum(result.total_points for result in team_match_results)
            total_position_points = sum(result.position_points for result in team_match_results)
            total_finishes_points = sum(result.finishes_points for result in team_match_results)
            total_wins = team_match_results.filter(match_schedule__winning_team=team).count()
            team_data.append({
                'name': team.name,
                'logo_url': team.logo.url,
                'total_points': total_points,
                'total_position_points': total_position_points,
                'total_finishes_points': total_finishes_points,
                'total_wins': total_wins
            })

        if is_ajax(request):
            return JsonResponse({'team_data': team_data})

        # Retrieve match numbers for the dropdown
        match_numbers = ['overall'] + list(match_results.values_list('match_schedule__match_number', flat=True).distinct())

        return render(request, 'standings/team_standings.html', {
            'tournament_name': tournament_name,
            'teams': teams,
            'matches': match_numbers,
            'selected_match': selected_match,
        })
    except Tournament.DoesNotExist:
        return HttpResponse('Tournament not found', status=404)
    
def sort(team):
    return (
        -team['total_points'],
        -team['total_position_points'],
        -team['total_finishes_points']
    )


def team_standings_json(request, tournament_name):
    selected_match = request.GET.get('selected_match')
    
    if selected_match == 'overall':
        # Retrieve overall team data
        teams = OverallStandings.objects.filter(tournament__name=tournament_name).order_by(
            '-total_points', '-total_position_points', '-total_finishes_points', '-total_wins'
        )
        team_data = []
        for team in teams:
            team_data.append({
                'name': team.team.name,
                'total_points': team.total_points,
                'total_position_points': team.total_position_points,
                'total_finishes_points': team.total_finishes_points,
                'total_wins': team.total_wins,
                'logo_url': team.team.logo.url
            })
    else:
        # Retrieve match-specific data
        match_results = MatchResult.objects.filter(
            tournament__name=tournament_name,
            match_schedule__match_number=selected_match
        )

        # Get a list of distinct team IDs that participated in the selected match
        team_ids = match_results.values_list('team', flat=True).distinct()

        # Calculate team-specific data for the selected match
        team_data = []
        for team_id in team_ids:
            team_match_results = match_results.filter(team_id=team_id)
            total_points = sum(result.total_points for result in team_match_results)
            total_position_points = sum(result.position_points for result in team_match_results)
            total_finishes_points = sum(result.finishes_points for result in team_match_results)
            total_wins = team_match_results.filter(match_schedule__winning_team_id=team_id).count()
            team_data.append({
                'name': team_match_results[0].team.name,
                'total_points': total_points,
                'total_position_points': total_position_points,
                'total_finishes_points': total_finishes_points,
                'total_wins': total_wins,
                'logo_url': team_match_results[0].team.logo.url
            })

        # # Sort teams based on total points for the selected match
        # team_data.sort(key=lambda x: x['total_points'], reverse=True)
        
        # Sort the team_data based on the custom sorting key
        team_data.sort(key=sort)

    # Convert team data to a JSON-friendly format
    team_data = [
        {
            'name': team['name'],
            'total_points': team['total_points'],
            'total_position_points': team['total_position_points'],
            'total_finishes_points': team['total_finishes_points'],
            'total_wins': team['total_wins'],
            'logo_url': team['logo_url']
        }
        for team in team_data
    ]

    return JsonResponse({'team_data': team_data})

def generate_team_standings_poster(request, tournament_name):
    # Retrieve team data and sort it based on criteria for the specified tournament
    teams = OverallStandings.objects.filter(tournament__name=tournament_name).order_by(
        '-total_points',
        '-total_position_points',
        '-total_finishes_points',
        '-total_wins'
    )

    # Define image template path, font path, and font settings
    image_path = "template.jpg"
    font_path = "SCHABO-Condensed.otf"
    font_size = 25
    letter_spacing = 16.8

    # Define the image coordinate settings to match 'download_team_data_image'
    coordinates = {
        'team_name_x': 331,
        'team_name_y': 460,  # Initial position for the first team's name (same as sample code)
        'logo_x': 252,  # Initial position for the first team's logo (same as sample code)
        'logo_y':454,
        'boundary_left': 252,
        'boundary_right': 316,
        'boundary_top': 444,
        'boundary_bottom': 498,
        'vertical_spacing': 58,
        'max_logo_width': 50,  # Maximum allowable logo width (same as sample code)
        'max_logo_height': 40,  # Maximum allowable logo height (same as sample code)
    }

    # Create an RGBA image
    image = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(image)

    # Load the font
    font = ImageFont.truetype(font_path, size=font_size)

    for team in teams:
        # Load the team logo
        team_logo = team.team.logo
        logo = Image.open(team_logo.path).convert("RGBA")  # Convert to RGBA mode

        # Ensure the output format is RGBA
        if logo.mode != 'RGBA':
            logo = logo.convert("RGBA")

        # Calculate the new dimensions to fit within the specified boundary while maintaining aspect ratio
        width, height = logo.size
        aspect_ratio = width / height

        # Check if the logo height is too close to the boundary (adjust the percentage as needed)
        min_allowed_height = coordinates['max_logo_height'] * 0.2
        if height > min_allowed_height:
            if width > coordinates['max_logo_width']:
                width = coordinates['max_logo_width']
                height = int(width / aspect_ratio)
            if height > coordinates['max_logo_height']:
                height = coordinates['max_logo_height']
                width = int(height * aspect_ratio)

        # Resize the logo to fit within the boundary
        logo = logo.resize((width, height), Image.LANCZOS)

        # Calculate the position to center the logo
        x = coordinates['logo_x'] + (coordinates['max_logo_width'] - width) // 2
        y = coordinates['logo_y'] + (coordinates['max_logo_height'] - height) // 2

        # Paste the logo onto the image with transparency at the calculated position
        image.paste(logo, (x, y), logo)

        # Draw team name with letter spacing
        text = f"{team.team.name}"
        draw.text((coordinates['team_name_x'], coordinates['team_name_y']), text, fill="white", font=font, spacing=letter_spacing)

        # Set the coordinates for other elements
        wins_x = 531
        other_elements_coords = (wins_x, coordinates['team_name_y'])  # Wins, TP, PP, FP at the same y-coordinate as the logo

        # Draw other elements like Wins, TP, PP, FP
        elements = [
            f"{team.total_points}",
            f"{team.total_position_points}",
            f"{team.total_finishes_points}"
        ]
        for element in elements:
            draw.text(other_elements_coords, element, fill="white", font=font, spacing=letter_spacing)
            other_elements_coords = (other_elements_coords[0] + 150, other_elements_coords[1])  # Adjust x-coordinate for the next element

        # Update the y-coordinate for the next team (58 pixels below the current one)
        coordinates['team_name_y'] += coordinates['vertical_spacing']
        coordinates['logo_y'] += coordinates['vertical_spacing']

    # Create an HttpResponse with image content
    response = HttpResponse(content_type="image/png")
    image.save(response, "PNG", quality=95)  # Maintain clarity with high quality

    # Set a filename for the downloaded image
    response["Content-Disposition"] = 'attachment; filename="team_standings.png"'

    return response

def update_standings(request, tournament_name):
    # Retrieve the tournament based on the provided name
    tournament = get_object_or_404(Tournament, name=tournament_name, user=request.user)

    # Retrieve the match schedule information for the selected tournament
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

    # Retrieve the groups associated with the match schedule
    match_groups = match_schedule.groups.all()

    if request.method == 'POST':
        # Process the POST data as before
        selected_team_id = request.POST.get('selected_team')
        position_points = request.POST.get('position_points')
        finishes_points = request.POST.get('finishes_points')

        if not (selected_team_id and position_points and finishes_points):
            return JsonResponse({'error': 'Please provide all required fields.'}, status=400)

        # Get the selected team
        selected_team = get_object_or_404(Team, id=selected_team_id)

        # Create a MatchResult instance and set the points
        match_result, created = MatchResult.objects.get_or_create(
            tournament=tournament,
            team=selected_team,
            match_schedule=match_schedule,
            finishes_points=0,
            position_points=0
        )
        match_result.position_points = int(position_points)
        match_result.finishes_points = int(finishes_points)
        match_result.save()

    # Retrieve and sort the data as needed
    teams_data = get_teams_data(tournament, match_schedule, match_groups)

    if request.method == 'POST':
        return JsonResponse({'message': 'Points added successfully.', 'teams_data': teams_data})

    # If it's not a POST request, return the initial page with data
    teams = Team.objects.filter(groups__in=match_groups).distinct()

    context = {
        'teams': teams,
        'teams_data': teams_data,
        'tournament': tournament,
        'match_schedule': match_schedule,
        'match_groups': match_groups,
        'tournament_name': tournament_name,
        'match_number':match_number
    }

    return render(request, 'match/add_points.html', context)

def get_teams_data(tournament, match_schedule, match_groups):
    teams_data = []
    for team in Team.objects.filter(groups__in=match_groups).distinct():
        match_result = MatchResult.objects.filter(
            tournament=tournament,
            team=team,
            match_schedule=match_schedule
        ).first()
        if match_result:
            total_points = match_result.position_points + match_result.finishes_points
        else:
            total_points = 0

        # Assuming team logos are stored in a 'logo_url' field in the Team model
        logo_url = team.logo.url


        teams_data.append({
            'team_id': team.id,
            'team_name': team.name,
            'position_points': match_result.position_points if match_result else 0,
            'finishes_points': match_result.finishes_points if match_result else 0,
            'total_points': total_points,
            'logo_url': logo_url,  # Add the team logo URL here
        })

    teams_data.sort(key=lambda x: (
        -x['total_points'],
        -x['position_points'],
        -x['finishes_points'],
    ))

    return teams_data



def download_team_data_image(request, tournament_name, match_number):
    # Retrieve 'tournament' and 'match_schedule' using their names and values
    tournament = get_object_or_404(Tournament, name=tournament_name)
    match_schedule = get_object_or_404(MatchSchedule, match_number=match_number, tournament=tournament)

    # Fetch and order teams and their match results
    teams_data = get_teams_data(tournament, match_schedule, match_schedule.groups.all())

    # Define image template path, font path, and font settings
    image_path = "template.jpg"
    font_path = "SCHABO-Condensed.otf"
    font_size = 25
    letter_spacing = 16.8

    # Define the image coordinate settings as per the sample code
    coordinates = {
        'team_name_x': 331,
        'team_name_y': 460,  # Initial position for the first team's name (same as sample code)
        'logo_x': 252,  # Initial position for the first team's logo (same as sample code)
        'logo_y':454,
        'boundary_left': 252,
        'boundary_right': 316,
        'boundary_top': 444,
        'boundary_bottom': 498,
        'vertical_spacing': 58,
        'max_logo_width': 50,  # Maximum allowable logo width (same as sample code)
        'max_logo_height': 40,  # Maximum allowable logo height (same as sample code)
    }

    # Create an RGBA image
    image = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(image)

    # Load the font
    font = ImageFont.truetype(font_path, size=font_size)

    for team_data in teams_data:
        # Retrieve the 'team' object using its ID or another unique identifier
        team = get_object_or_404(Team, id=team_data['team_id'])  # You may need to adjust this based on your data

        # Load the team logo
        team_logo = team.logo
        logo = Image.open(team_logo.path).convert("RGBA")  # Convert to RGBA mode

        # Ensure the output format is RGBA
        if logo.mode != 'RGBA':
            logo = logo.convert("RGBA")

        # Calculate the new dimensions to fit within the specified boundary while maintaining aspect ratio
        width, height = logo.size
        aspect_ratio = width / height

        # Check if the logo height is too close to the boundary (adjust the percentage as needed)
        min_allowed_height = coordinates['max_logo_height'] * 0.2
        if height > min_allowed_height:
            if width > coordinates['max_logo_width']:
                width = coordinates['max_logo_width']
                height = int(width / aspect_ratio)
            if height > coordinates['max_logo_height']:
                height = coordinates['max_logo_height']
                width = int(height * aspect_ratio)

        # Resize the logo to fit within the boundary
        logo = logo.resize((width, height), Image.LANCZOS)

        # Calculate the position to center the logo
        x = coordinates['logo_x'] + (coordinates['max_logo_width'] - width) // 2
        y = coordinates['logo_y'] + (coordinates['max_logo_height'] - height) // 2

        # Paste the logo onto the image with transparency at the calculated position
        image.paste(logo, (x, y), logo)

        # Draw team name with letter spacing
        text = f"{team_data['team_name']}"
        draw.text((coordinates['team_name_x'], coordinates['team_name_y']), text, fill="white", font=font, spacing=letter_spacing)

        # Set the coordinates for other elements
        wins_x = 531
        other_elements_coords = (wins_x, coordinates['team_name_y'])  # Wins, TP, PP, FP at the same y-coordinate as the logo

        # Draw other elements like Wins, TP, PP, FP
        elements = [f"{team_data['total_points']}", f"{team_data['position_points']}", f"{team_data['finishes_points']}"]
        for element in elements:
            draw.text(other_elements_coords, element, fill="white", font=font, spacing=letter_spacing)
            other_elements_coords = (other_elements_coords[0] + 150, other_elements_coords[1])  # Adjust x-coordinate for the next element

        # Update the y-coordinate for the next team (58 pixels below the current one)
        coordinates['team_name_y'] += coordinates['vertical_spacing']
        coordinates['logo_y'] += coordinates['vertical_spacing']

    # Create an HttpResponse with image content
    response = HttpResponse(content_type="image/png")
    image.save(response, "PNG", quality=95)  # Maintain clarity with high quality

    # Set a filename for the downloaded image
    response["Content-Disposition"] = 'attachment; filename="team_data_image.png"'

    return response

import base64
from django.core.files.base import ContentFile

def encode_image_as_base64(image_path):
    with open(image_path, "rb") as image_file:
        data = base64.b64encode(image_file.read()).decode("utf-8")
    return data

def preview_team_data_image(request, tournament_name, match_number):
    # Retrieve 'tournament' and 'match_schedule' using their names and values
    tournament = get_object_or_404(Tournament, name=tournament_name)
    match_schedule = get_object_or_404(MatchSchedule, match_number=match_number, tournament=tournament)

    # Fetch and order teams and their match results
    teams_data = get_teams_data(tournament, match_schedule, match_schedule.groups.all())

    # Define image template path, font path, and font settings
    image_path = "template.jpg"
    font_path = "SCHABO-Condensed.otf"
    font_size = 25
    letter_spacing = 16.8

    # Define the image coordinate settings
    coordinates = {
        'team_name_x': 331,
        'finishes_points_x': 538,
        'position_points_x': 646,
        'wins_x': 730,
        'total_points_x': 824,
        'vertical_spacing': 58,
        'team_name_y': 460  # Initial position for the first team's name
    }

    # Create an RGBA image
    image = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(image)

    # Load the font
    font = ImageFont.truetype(font_path, size=font_size)

    for team_data in teams_data:
        # Draw team name with letter spacing
        text = f"{team_data['team_name']}"
        draw.text((coordinates['team_name_x'], coordinates['team_name_y']), text, fill="white", font=font, spacing=letter_spacing)

        # Draw other fields (e.g., position points, finishes points, total points)
        fields = ['position_points', 'finishes_points', 'total_points']
        for field in fields:
            x = coordinates[f'{field}_x']
            y = coordinates['team_name_y']
            text = f"{team_data[field]}"
            draw.text((x, y), text, fill="white", font=font, spacing=letter_spacing)

        # Increment the y-coordinate for vertical spacing
        coordinates['team_name_y'] += coordinates['vertical_spacing']

    # Save the image to a temporary buffer
    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)

    image_data = encode_image_as_base64(image_path)
    context = {
        'tournament_name': tournament_name,
        'match_number': match_number,
        'image_data': image_data,
    }
    return render(request, 'images/preview.html', context)


def create_tournament(request):
    # Implement the logic to create tournaments here
    return render(request, 'create_tournament.html')

# Add this view to your views.py
def delete_team_scores(request, team_id):
    try:
        # Assuming you have a Team model, you can retrieve the team by its ID
        team = Team.objects.get(id=team_id)

        # Delete the team's scores (MatchResult instances)
        MatchResult.objects.filter(team=team).delete()

        # You can return a success message if needed
        return JsonResponse({'success': 'Scores deleted successfully'})
    except Team.DoesNotExist:
        return JsonResponse({'error': 'Team not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def create_tournament(request):
    # Implement the logic to create tournaments here
    return render(request, 'create_tournament.html')


def custom_template_view(request, tournament_name):
    # Number of teams per section
    num_teams_per_section = 8

    # Retrieve team data and sort it based on criteria for the specified tournament
    teams = OverallStandings.objects.filter(tournament__name=tournament_name).order_by(
        '-total_points',
        '-total_position_points',
        '-total_finishes_points',
        '-total_wins'
    )

    # Define image template path, font path, and font settings
    image_path = "download.png"
    font_path = "SCHABO-Condensed.otf"
    font_size = 20
    letter_spacing = 16.8

    # Define the image coordinate settings
    coordinates = {
        'team_name_x': 74,
        'team_name_y_first': 547,  # Y-coordinate for the first team's name
        'team_name_y_spacing': 52,  # Vertical spacing for team names
        'team_name_x_alternate': 428,
        'position_x': 241,  # X-coordinate for position points
        'position_x_alternate': 597,
        'finishes_x': 279,  # X-coordinate for finishes points
        'finishes_x_alternate': 636,
    }

    # Create an RGBA image
    image = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(image)

    # Load the font
    font = ImageFont.truetype(font_path, size=font_size)

    for idx, team in enumerate(teams):
        # Calculate y based on the team's position within the sorted list
        y = coordinates['team_name_y_first'] + (idx % num_teams_per_section) * coordinates['team_name_y_spacing']
        x = coordinates['team_name_x' if idx < num_teams_per_section else 'team_name_x_alternate']

        # Draw team name with letter spacing
        text = f"{team.team.name}"
        draw.text((x, y), text, fill="white", font=font, spacing=letter_spacing)

        # Add position points next to the team name
        position_x = coordinates['position_x' if idx < num_teams_per_section else 'position_x_alternate']
        position_points = f"{team.total_position_points}"
        draw.text((position_x, y), position_points, fill="white", font=font, spacing=letter_spacing)

        # Add finishes points next to the team name
        finishes_x = coordinates['finishes_x' if idx < num_teams_per_section else 'finishes_x_alternate']
        finishes_points = f"{team.total_finishes_points}"
        draw.text((finishes_x, y), finishes_points, fill="white", font=font, spacing=letter_spacing)

    # Create an HttpResponse with image content
    response = HttpResponse(content_type="image/png")
    image.save(response, "PNG", quality=95)  # Maintain clarity with high quality

    # Set a filename for the downloaded image
    response["Content-Disposition"] = 'attachment; filename="team_info.png"'

    return response




