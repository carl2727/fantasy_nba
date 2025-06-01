# views.py
from django import forms
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect,  get_object_or_404
from django.http import HttpRequest, JsonResponse, Http404
from . import ratings as ratings_data_module # Renamed to avoid conflict with 'ratings' variable
from .models import *
from django.db import transaction
from .forms import MinimalUserCreationForm
import pandas as pd
import logging

# Get an instance of a logger
logger = logging.getLogger(__name__)
COLUMN_DISPLAY_NAMES = {
    'Name': 'Name',
    'PTS_RT': 'PTS',
    'REB_RT': 'REB',
    'AST_RT': 'AST',
    'FGN_RT': 'FG%',
    'FTN_RT': 'FT%',
    'FG3M_RT': '3PTM',
    'BLK_RT': 'BLK',
    'STL_RT': 'STL',
    'TOV_RT': 'TOV',
    'Total_Rating': 'Overall Rating',
    'Total_Available_Rating': 'Performance Rating',
    'Player_ID': 'Player_ID',
}

STYLED_COLUMNS = [
    'PTS_RT', 
    'REB_RT', 
    'AST_RT', 
    'STL_RT', 
    'BLK_RT',
    'FGN_RT',
    'FTN_RT',
    'FG3M_RT',
    'TOV_RT'
]


def _get_default_columns():
    """Returns the default list of columns to display."""

RATING_CHOICES = [
    (key, COLUMN_DISPLAY_NAMES[key].replace('_RT', '')) for key in COLUMN_DISPLAY_NAMES if key not in ['Name', 'Total_Rating', 'Total_Available_Rating']
]

class PuntForm(forms.Form):
    punt_category_1 = forms.ChoiceField(
        choices=[('', '---')] + RATING_CHOICES,
        required=False,
        label='Punt Category 1'
    )
    punt_category_2 = forms.ChoiceField(
        choices=[('', '---')] + RATING_CHOICES,
        required=False,
        label='Punt Category 2'
    )

def punt(request: HttpRequest):
    if request.method == 'POST':
        form = PuntForm(request.POST)
        if form.is_valid():
            punted_categories = [
                form.cleaned_data['punt_category_1'],
                form.cleaned_data['punt_category_2'],
            ]
            punted_categories = [cat for cat in punted_categories if cat]

            request.session['punted_categories'] = punted_categories
            return redirect('show_ratings')

    else:
        form = PuntForm()
        return render(request, 'fantasy_nba/punt.html', {'form': form})

def show_ratings(request: HttpRequest):
    ratings_df = ratings_data_module.ratings.copy()
    # Base columns to display, order is preserved by list()
    columns_to_extract = list(COLUMN_DISPLAY_NAMES.keys()) 
    
    # Initialize variables for punt-specific columns
    punt_perf_col_actual_name = None
    punt_perf_col_display_name = None
    punt_overall_col_actual_name = None
    punt_overall_col_display_name = None

    punted_categories = request.session.get('punted_categories', [])
    if punted_categories:
        # Generate the common part of the punt column name (e.g., "_Punt_AST_STL")
        punt_suffix = "_Punt_" + "_".join(sorted([cat.replace('_RT', '') for cat in punted_categories]))
        
        # Define the actual data column name for "Performance (Punt...)"
        punt_perf_col_actual_name_candidate = f'Total{punt_suffix}_Available_Rating'
        # Define the actual data column name for "Overall (Punt...)"
        punt_overall_col_actual_name_candidate = f'Total{punt_suffix}_Rating'

        # Prepare formatted string for punted categories display
        punted_display_names_list = [COLUMN_DISPLAY_NAMES[cat].replace('_RT', '') for cat in punted_categories]
        if len(punted_display_names_list) == 1:
            punted_cats_formatted_for_display = punted_display_names_list[0]
        elif len(punted_display_names_list) == 2:
            punted_cats_formatted_for_display = f"{punted_display_names_list[0]} & {punted_display_names_list[1]}"
        else: # Fallback, though typically 1 or 2 categories are punted
            punted_cats_formatted_for_display = ", ".join(punted_display_names_list)

        # Check and prepare "Performance (Punt...)" column (already existing logic)
        if punt_perf_col_actual_name_candidate in ratings_data_module.ratings.columns:
            punt_perf_col_actual_name = punt_perf_col_actual_name_candidate
            punt_perf_col_display_name = f"Performance Rating (Punt {punted_cats_formatted_for_display})"
            if punt_perf_col_actual_name not in columns_to_extract:
                columns_to_extract.append(punt_perf_col_actual_name)

        # Check and prepare "Overall (Punt...)" column (newly added)
        if punt_overall_col_actual_name_candidate in ratings_data_module.ratings.columns:
            punt_overall_col_actual_name = punt_overall_col_actual_name_candidate
            punt_overall_col_display_name = f"Overall Rating (Punt {punted_cats_formatted_for_display})"
            if punt_overall_col_actual_name not in columns_to_extract:
                columns_to_extract.append(punt_overall_col_actual_name)

    # Start with base display names and add punt-specific ones
    final_column_display_names = COLUMN_DISPLAY_NAMES.copy()
    if punt_perf_col_actual_name and punt_perf_col_display_name:
        final_column_display_names[punt_perf_col_actual_name] = punt_perf_col_display_name
    
    if punt_overall_col_actual_name and punt_overall_col_display_name:
        final_column_display_names[punt_overall_col_actual_name] = punt_overall_col_display_name
    
    final_column_display_names['Status'] = 'Status' # Add Status column

    # Get the active team for the user
    user_teams = None
    active_team = None  # Initialize active_team to None
    if request.user.is_authenticated:
        # Query all teams for the user first
        user_teams = Team.objects.filter(creator=request.user)
        active_team = user_teams.filter(is_active=True).first()
        if active_team:
            # Fetch all player statuses for the active team efficiently
            team_player_entries = TeamPlayer.objects.filter(team=active_team)
            active_team_player_ids = set(tp.player_id for tp in team_player_entries) # Used for 'is_on_team'
            team_player_statuses_map = {tp.player_id: tp.status for tp in team_player_entries}
        else:
            active_team_player_ids = set()
            team_player_statuses_map = {}

    # Prepare data for styling
    initial_data_list = []
    for record in ratings_df.to_dict('records'):
        processed_record = {}
        player_id_val = record.get('Player_ID')

        # Store Player_ID (it will be styled by _apply_styles_to_data)
        processed_record['Player_ID'] = player_id_val

        # Determine and store is_on_team (it will be styled by _apply_styles_to_data)
        is_on_team_flag = False
        if player_id_val is not None:
            try:
                # Player_ID from pandas might be float, ensure int for comparison
                is_on_team_flag = int(float(player_id_val)) in active_team_player_ids
            except (ValueError, TypeError):
                logger.warning(f"Could not convert Player_ID '{player_id_val}' to int for team check in show_ratings.")
        processed_record['is_on_team'] = is_on_team_flag

        # Add player status
        current_status_display = 'Available' # Default status if not in TeamPlayer or no active team
        if active_team and player_id_val is not None:
            try:
                player_id_int = int(float(player_id_val))
                status_code = team_player_statuses_map.get(player_id_int, 'AVAILABLE') # Default to AVAILABLE if not in map
                current_status_display = dict(TeamPlayer.STATUS_CHOICES).get(status_code, 'Available')
            except (ValueError, TypeError):
                logger.warning(f"Could not convert Player_ID '{player_id_val}' to int for status lookup in show_ratings.")
        processed_record['Status'] = current_status_display

        # Add all other columns defined in final_column_display_names from the original record
        for col_key in final_column_display_names.keys():
            if col_key not in processed_record: # Avoid overwriting Player_ID, is_on_team, Status
                if col_key in record:
                    processed_record[col_key] = record[col_key]
        initial_data_list.append(processed_record)
    
    # The _apply_styles_to_data function will wrap each value, including 'Status'
    styled_ratings_data = _apply_styles_to_data(initial_data_list, STYLED_COLUMNS)

    context = {
        'ratings': styled_ratings_data,
        'column_display_names': final_column_display_names,
        'teams': user_teams if request.user.is_authenticated else None, # Pass all user teams for other parts of UI if needed
        'active_team': active_team,  # Add the active team to the context
    }
    return render(request, 'fantasy_nba/show_ratings.html', context)

def sort_ratings(request: HttpRequest):
    sort_by = request.GET.get('sort_by')
    ratings_df = ratings_data_module.ratings.copy()

    # Determine sort order
    ascending_flag = False # Default to descending for a new column
    if sort_by == request.session.get('sort_by'):
        # Same column, toggle direction
        if request.session.get('sort_direction') == 'asc':
            request.session['sort_direction'] = 'desc'
            ascending_flag = False # Sort descending
        else: # Was 'desc' or None
            request.session['sort_direction'] = 'asc'
            ascending_flag = True  # Sort ascending
    else:
        # New column, default to descending
        request.session['sort_by'] = sort_by
        request.session['sort_direction'] = 'desc'
        ascending_flag = False # Sort descending

    # Prepare list of columns to display and their display names, including punt columns
    columns_to_extract = list(COLUMN_DISPLAY_NAMES.keys())
    punt_perf_col_actual_name = None
    punt_perf_col_display_name = None
    punt_overall_col_actual_name = None
    punt_overall_col_display_name = None

    punted_categories = request.session.get('punted_categories', [])
    if punted_categories:
        punt_suffix = "_Punt_" + "_".join(sorted([cat.replace('_RT', '') for cat in punted_categories]))
        punt_perf_col_actual_name_candidate = f'Total{punt_suffix}_Available_Rating'
        punt_overall_col_actual_name_candidate = f'Total{punt_suffix}_Rating'

        # Prepare formatted string for punted categories display
        punted_display_names_list = [COLUMN_DISPLAY_NAMES[cat].replace('_RT', '') for cat in punted_categories]
        if len(punted_display_names_list) == 1:
            punted_cats_formatted_for_display = punted_display_names_list[0]
        elif len(punted_display_names_list) == 2:
            punted_cats_formatted_for_display = f"{punted_display_names_list[0]} & {punted_display_names_list[1]}"
        else: # Fallback
            punted_cats_formatted_for_display = ", ".join(punted_display_names_list)

        if punt_perf_col_actual_name_candidate in ratings_data_module.ratings.columns:
            punt_perf_col_actual_name = punt_perf_col_actual_name_candidate
            punt_perf_col_display_name = f"Performance Rating (Punt {punted_cats_formatted_for_display})"
            if punt_perf_col_actual_name not in columns_to_extract:
                columns_to_extract.append(punt_perf_col_actual_name)

        if punt_overall_col_actual_name_candidate in ratings_data_module.ratings.columns:
            punt_overall_col_actual_name = punt_overall_col_actual_name_candidate
            punt_overall_col_display_name = f"Overall Rating (Punt {punted_cats_formatted_for_display})"
            if punt_overall_col_actual_name not in columns_to_extract:
                columns_to_extract.append(punt_overall_col_actual_name)

    final_column_display_names = COLUMN_DISPLAY_NAMES.copy()
    if punt_perf_col_actual_name and punt_perf_col_display_name:
        final_column_display_names[punt_perf_col_actual_name] = punt_perf_col_display_name
    if punt_overall_col_actual_name and punt_overall_col_display_name:
        final_column_display_names[punt_overall_col_actual_name] = punt_overall_col_display_name
    
    final_column_display_names['Status'] = 'Status' # Add Status column

    # Sort the DataFrame
    if sort_by in ratings_df.columns:
        sorted_ratings_df = ratings_df.sort_values(by=sort_by, ascending=ascending_flag)
    else:
        sorted_ratings_df = ratings_df # No sort or use default if sort_by is invalid
    
    active_team = None # Initialize active_team
    if request.user.is_authenticated:
        active_team = Team.objects.filter(creator=request.user, is_active=True).first()
        if active_team:
            # Fetch all player statuses for the active team efficiently
            team_player_entries = TeamPlayer.objects.filter(team=active_team)
            active_team_player_ids = set(tp.player_id for tp in team_player_entries) # Used for 'is_on_team'
            team_player_statuses_map = {tp.player_id: tp.status for tp in team_player_entries}
        else:
            active_team_player_ids = set()
            team_player_statuses_map = {}

    initial_data_list_sorted = []
    for record in sorted_ratings_df.to_dict('records'): # Use the sorted DataFrame here
        processed_record = {}
        player_id_val = record.get('Player_ID')

        processed_record['Player_ID'] = player_id_val

        is_on_team_flag = False
        if player_id_val is not None:
            try:
                is_on_team_flag = int(float(player_id_val)) in active_team_player_ids
            except (ValueError, TypeError):
                logger.warning(f"Could not convert Player_ID '{player_id_val}' to int for team check in sort_ratings.")
        processed_record['is_on_team'] = is_on_team_flag

        # Add player status
        current_status_display = 'Available' # Default status
        if active_team and player_id_val is not None:
            try:
                player_id_int = int(float(player_id_val))
                status_code = team_player_statuses_map.get(player_id_int, 'AVAILABLE')
                current_status_display = dict(TeamPlayer.STATUS_CHOICES).get(status_code, 'Available')
            except (ValueError, TypeError):
                logger.warning(f"Could not convert Player_ID '{player_id_val}' to int for status lookup in sort_ratings.")
        processed_record['Status'] = current_status_display

        # Add all other columns defined in final_column_display_names from the original record
        for col_key in final_column_display_names.keys():
            if col_key not in processed_record: # Avoid overwriting
                if col_key in record:
                    processed_record[col_key] = record[col_key]
        initial_data_list_sorted.append(processed_record)
    
    styled_sorted_ratings_data = _apply_styles_to_data(initial_data_list_sorted, STYLED_COLUMNS)

    context = {
        'ratings': styled_sorted_ratings_data,
        'column_display_names': final_column_display_names,
        'sort_by': request.session.get('sort_by'),
        'sort_direction': request.session.get('sort_direction'),
        'active_team': active_team, # Pass active_team for template logic
    }
    return render(request, 'fantasy_nba/show_ratings.html', context)

def _get_value_based_css_class(value):
    """Determines CSS class based on fixed value thresholds.
    Assumes value is on a 0-100 scale where higher is better."""
    if value is None or not isinstance(value, (int, float)):
        return None

    if value > 85:
        return 'bg-dark-green'
    elif value > 70:
        return 'bg-green'
    elif value > 55:
        return 'bg-light-green'
    elif value < 15:
        return 'bg-dark-red'
    elif value < 30:
        return 'bg-red'
    elif value < 45:
        return 'bg-light-red'
    elif value >= 45 and value <= 55:
        return 'bg-grey'
        
    return None


def _apply_styles_to_data(data_list_of_dicts: list, columns_to_style: list):
    styled_data = []
    for player_row_dict in data_list_of_dicts:
        styled_player_row = {}
        # Ensure 'is_on_team' and 'Player_ID' are processed and included
        # even if not in STYLED_COLUMNS, they will get a default {'value': ..., 'css_class': None}
        # The Player_ID specific logic below handles its conversion.
        # The is_on_team flag will be wrapped like any other non-styled column.
        for col_actual_name, raw_value in player_row_dict.items(): # Changed 'value' to 'raw_value' for clarity
            value_to_store = raw_value # This will be the value stored in the dict for the template

            if col_actual_name == 'Player_ID':
                logger.debug(f"Styling Player_ID: Original value from player_row_dict is '{raw_value}', type: {type(raw_value)}")
                try:
                    # Attempt to convert to int.
                    # Convert to float first to handle cases like "123.0" or 123.0, then to int.
                    if pd.notna(raw_value):
                        value_to_store = int(float(raw_value))
                    else:
                        value_to_store = None # Handle actual missing IDs if they occur
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert Player_ID value '{raw_value}' to int during styling.")
                    value_to_store = None # Or some other indicator of an invalid ID

            css_class = None
            if col_actual_name in columns_to_style:
                # value_for_styling should use the raw_value if styling depends on original float precision
                value_for_styling = raw_value
                css_class = _get_value_based_css_class(value_for_styling)
            
            # For columns not in columns_to_style (like 'Name', 'is_on_team', or unstyled Player_ID),
            # css_class remains None.
            styled_player_row[col_actual_name] = {'value': value_to_store, 'css_class': css_class}
        styled_data.append(styled_player_row)
    return styled_data

def breakdown(request):
    return render(request, 'fantasy_nba/breakdown.html')

def login_register(request):
    login_form = AuthenticationForm()
    register_form = MinimalUserCreationForm()  # Use your custom form

    if request.method == 'POST':
        if 'login' in request.POST:
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                return redirect('show_ratings')
        elif 'register' in request.POST:
            register_form = MinimalUserCreationForm(request.POST)  # Use your custom form
            if register_form.is_valid():
                user = register_form.save()
                login(request, user)
                return redirect('show_ratings')

    return render(request, 'fantasy_nba/login_register.html', {
        'login_form': login_form,
        'register_form': register_form,
    })
    
    
@login_required
def create_team(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip() # Get name and strip whitespace
        if name: # Check if name is non-empty after stripping
            team = Team.objects.create(name=name, creator=request.user)
            # If this is the user's first team, set it as active
            if Team.objects.filter(creator=request.user).count() == 1:
                team.is_active = True
                team.save()
            messages.success(request, f"Team '{name}' created successfully.")
            return redirect('team')
        else:
            # Name was empty or just whitespace
            messages.error(request, "Team name cannot be empty or consist only of spaces.")
            # Fall through to render the form again, messages will be displayed

    return render(request, 'fantasy_nba/create_team.html') # For GET or if POST had an empty/invalid name

@login_required
def team(request):
    teams = Team.objects.filter(creator=request.user)

    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        if team_id:
            # Deactivate all teams for the user
            Team.objects.filter(creator=request.user).update(is_active=False)
            # Activate the selected team
            try:
                team_to_activate = get_object_or_404(Team, team_id=team_id, creator=request.user)
                team_to_activate.is_active = True
                team_to_activate.save()
                messages.success(request, f"Team '{team_to_activate.name}' is now active.")
            except Http404:
                messages.error(request, "Failed to activate team. Team not found.")
            return redirect('team')
        else:
            messages.error(request, "No team selected to activate.")
            # Fall through to render the page again if team_id was missing in POST

    # For GET requests, or POSTs that didn't redirect (e.g. invalid POST)
    # 'teams' is already fetched at the beginning of the function.
    active_team = teams.filter(is_active=True).first()
    return render(request, 'fantasy_nba/team.html', {'teams': teams, 'active_team': active_team})

@login_required
def update_player_status(request):
    if request.method == 'POST':
        active_team = Team.objects.filter(creator=request.user, is_active=True).first()
        if not active_team:
            return JsonResponse({'success': False, 'error': 'No active team found.'}, status=400)

        player_id_str = request.POST.get('player_id')
        new_status = request.POST.get('status') # Expected: 'ON_TEAM', 'AVAILABLE', 'UNAVAILABLE'

        if not player_id_str:
            return JsonResponse({'success': False, 'error': 'Player ID is required.'}, status=400)
        if not new_status or new_status not in [choice[0] for choice in TeamPlayer.STATUS_CHOICES]:
            return JsonResponse({'success': False, 'error': 'Invalid status provided.'}, status=400)

        try:
            player_id = int(player_id_str)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid Player ID format.'}, status=400)

        team_player, created = TeamPlayer.objects.update_or_create(
            team=active_team, player_id=player_id,
            defaults={'status': new_status}
        )
        message = f"Player status updated to {team_player.get_status_display()}."
        if created and new_status == 'AVAILABLE': # If created with default status, message might be slightly different
            message = f"Player {player_id} record created with status {team_player.get_status_display()}."
        
        return JsonResponse({'success': True, 'message': message, 'new_status_code': team_player.status, 'new_status_display': team_player.get_status_display()})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@login_required
def add_player(request):
    if request.method == 'POST':
        active_team = Team.objects.filter(creator=request.user, is_active=True).first()
        if not active_team:
            return JsonResponse({'success': False, 'error': 'No active team found. Please select or create an active team.'}, status=400)

        player_id_str = request.POST.get('player_id')
        if not player_id_str:
            return JsonResponse({'success': False, 'error': 'Player ID is required.'}, status=400)

        try:
            player_id = int(player_id_str)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid Player ID format.'}, status=400)

        # This view is now superseded by update_player_status.
        # Default status is 'AVAILABLE' in the model.
        team_player, created = TeamPlayer.objects.get_or_create(
            team=active_team,
            player_id=player_id,
            defaults={'status': 'ON_TEAM'} # Or handle via update_player_status
        )
        # return JsonResponse({'success': True, 'created': created, 'message': 'Player added to team.' if created else 'Player already in team.'})
        return JsonResponse({'success': False, 'error': 'This endpoint is deprecated. Use update_player_status.'}, status=405)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

@login_required
def remove_player(request):
    # This view is now superseded by update_player_status (by setting status to AVAILABLE or UNAVAILABLE).
    # if request.method == 'POST':
    #     active_team = Team.objects.filter(creator=request.user, is_active=True).first()
    #     if not active_team:
    #         return JsonResponse({'success': False, 'error': 'No active team found.'}, status=400)

    #     player_id_str = request.POST.get('player_id')
    #     if not player_id_str:
    #         return JsonResponse({'success': False, 'error': 'Player ID is required.'}, status=400)

    #     try:
    #         player_id = int(player_id_str)
    #         # To "remove", set status to AVAILABLE
    #         tp, updated = TeamPlayer.objects.update_or_create(
    #             team=active_team, player_id=player_id,
    #             defaults={'status': 'AVAILABLE'}
    #         )
    #         return JsonResponse({'success': True, 'message': 'Player status set to Available.'})
    #     except ValueError:
    #         return JsonResponse({'success': False, 'error': 'Invalid Player ID format.'}, status=400)
    return JsonResponse({'success': False, 'error': 'This endpoint is deprecated. Use update_player_status.'}, status=405)

@login_required
def toggle_availability(request):
    # This view is superseded by update_player_status.
    # The 'is_available' field is no longer on TeamPlayer model, replaced by 'status'.
    # if request.method == 'POST':
        # ...
        # try:
            # player_id = int(player_id_str)
            # tp = get_object_or_404(TeamPlayer, team=active_team, player_id=player_id)
            # # Logic to toggle between AVAILABLE and UNAVAILABLE, or ON_TEAM
            # # This is complex with three states and better handled by explicit status setting.
            # return JsonResponse({'success': True, ...})
    return JsonResponse({'success': False, 'error': 'This endpoint is deprecated. Use update_player_status.'}, status=405)

def logout_view(request):
    logout(request)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)