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
    """Returns a default list of column keys for display."""
    # This function's direct operational use in show_ratings is limited
    # as columns_to_extract is dynamically built.
    # Providing a sensible default list of keys.
    return [
        'Name', 'PTS_RT', 'REB_RT', 'AST_RT', 'FGN_RT', 'FTN_RT',
        'FG3M_RT', 'BLK_RT', 'STL_RT', 'TOV_RT',
        'Total_Rating', 'Total_Available_Rating'
    ]
    
RATING_CHOICES = [
    (key, COLUMN_DISPLAY_NAMES[key].replace('_RT', '')) for key in COLUMN_DISPLAY_NAMES if key not in ['Name', 'Total_Rating', 'Total_Available_Rating']
]

def _get_final_column_display_names(session_data, all_rating_columns):
    """
    Determines the final set of column display names, including punt-specific columns.
    `all_rating_columns` is a list/Index of columns available in the base ratings DataFrame.
    """
    final_names = COLUMN_DISPLAY_NAMES.copy()

    punted_categories = session_data.get('punted_categories', [])

    if punted_categories:
        punt_suffix = "_Punt_" + "_".join(sorted([cat.replace('_RT', '') for cat in punted_categories]))
        punt_perf_col_actual_name_candidate = f'Total{punt_suffix}_Available_Rating'
        punt_overall_col_actual_name_candidate = f'Total{punt_suffix}_Rating'

        punted_display_names_list = [COLUMN_DISPLAY_NAMES[cat].replace('_RT', '') for cat in punted_categories]
        punted_cats_formatted_for_display = ""
        if len(punted_display_names_list) == 1:
            punted_cats_formatted_for_display = punted_display_names_list[0]
        elif len(punted_display_names_list) == 2:
            punted_cats_formatted_for_display = f"{punted_display_names_list[0]} & {punted_display_names_list[1]}"
        else: # Fallback
            punted_cats_formatted_for_display = ", ".join(punted_display_names_list)

        if punt_perf_col_actual_name_candidate in all_rating_columns:
            final_names[punt_perf_col_actual_name_candidate] = f"Performance Rating (Punt {punted_cats_formatted_for_display})"

        if punt_overall_col_actual_name_candidate in all_rating_columns:
            final_names[punt_overall_col_actual_name_candidate] = f"Overall Rating (Punt {punted_cats_formatted_for_display})"

    final_names['Status'] = 'Status'
    return final_names

def _extract_columns_for_display(final_column_display_names_map, all_rating_columns):
    """
    From the final_column_display_names_map, returns a list of actual column keys
    that exist in all_rating_columns or are special keys like 'Name', 'Player_ID', 'Status'.
    This ensures we only try to extract/display columns that can be sourced.
    """
    return [key for key in final_column_display_names_map.keys() if key in all_rating_columns or key in ['Name', 'Player_ID', 'Status']]

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
    final_column_display_names = _get_final_column_display_names(request.session, ratings_data_module.ratings.columns)
    # columns_to_extract is implicitly handled by iterating final_column_display_names.keys()
    # and checking existence in `record` during data preparation.

    # Get the active team for the user
    user_teams = None
    active_team = None  # Initialize active_team to None
    active_team_player_ids = set()
    team_player_statuses_map = {}
    on_team_player_ids = set() # Player IDs for those with status 'ON_TEAM'

    if request.user.is_authenticated:
        # Query all teams for the user first
        user_teams = Team.objects.filter(creator=request.user)
        active_team = user_teams.filter(is_active=True).first()
        if active_team:
            # Fetch all player statuses for the active team efficiently
            team_player_entries = TeamPlayer.objects.filter(team=active_team).select_related('team')
            active_team_player_ids = set(tp.player_id for tp in team_player_entries) # All players associated with the team
            team_player_statuses_map = {tp.player_id: tp.status for tp in team_player_entries}
            on_team_player_ids = set(tp.player_id for tp in team_player_entries if tp.status == 'ON_TEAM')


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

    # Get styled team averages and count using the new helper
    (styled_team_averages_dict, num_players_on_team_calc) = _get_styled_team_averages_and_count(
        ratings_df, active_team, final_column_display_names
    )

    # If active team and players exist, prepare the team average row and prepend it
    # num_players_on_team_calc is the reliable count from the helper
    if active_team and num_players_on_team_calc > 0 and styled_team_averages_dict:
        team_average_row_for_table = {}
        # Specific info for the team row
        team_average_row_for_table['Name'] = {'value': active_team.name, 'css_class': None}
        team_average_row_for_table['Player_ID'] = {'value': 'TEAM_AVERAGE_ROW', 'css_class': None} # Special ID
        team_average_row_for_table['Status'] = {
            'value': f"Team Avg ({num_players_on_team_calc} Player{'s' if num_players_on_team_calc != 1 else ''})",
            'css_class': None 
        }

        # Add the calculated and styled averages
        for col_key, styled_value_dict in styled_team_averages_dict.items():
            team_average_row_for_table[col_key] = styled_value_dict
        
        # Ensure all displayable columns have an entry in the team average row
        for col_key in final_column_display_names.keys():
            if col_key not in team_average_row_for_table:
                team_average_row_for_table[col_key] = {'value': "N/A", 'css_class': None}

        styled_ratings_data.insert(0, team_average_row_for_table)

    context = {
        'ratings': styled_ratings_data,
        'column_display_names': final_column_display_names,
        'teams': user_teams if request.user.is_authenticated else None, # Pass all user teams for other parts of UI if needed
        'active_team': active_team,  # Add the active team to the context
        # 'team_averages' and 'num_players_on_team' for the separate table are no longer needed here
        # as the team average row is now part of 'ratings'.
    }
    return render(request, 'fantasy_nba/show_ratings.html', context)

def _style_single_row_data(data_dict: dict, columns_to_apply_css_to: list):
    styled_row = {}
    for col_actual_name, raw_value in data_dict.items():
        css_class = None
        # Apply styling only if the column is in the specified list and value is numeric
        if col_actual_name in columns_to_apply_css_to and isinstance(raw_value, (int, float)):
            css_class = _get_value_based_css_class(raw_value)
        
        styled_row[col_actual_name] = {'value': raw_value, 'css_class': css_class}
    return styled_row

def _get_styled_team_averages_and_count(ratings_df, active_team, final_column_display_names_map):
    """
    Calculates and styles team averages for an active team.
    Returns a tuple: (styled_team_averages_dict, num_players_on_team)
    styled_team_averages_dict is like: {'PTS_RT': {'value': 70.5, 'css_class': '...'}, ...}
    Returns (None, 0) if no averages can be calculated or no active team.
    """
    if not active_team:
        return None, 0

    on_team_player_ids = set(
        TeamPlayer.objects.filter(team=active_team, status='ON_TEAM').values_list('player_id', flat=True)
    )
    num_players_on_team = len(on_team_player_ids)

    if num_players_on_team == 0:
        return None, 0 # Return 0 for count, None for averages

    team_averages_raw = {}
    cols_for_averaging = [
        key for key in final_column_display_names_map.keys()
        if key not in ['Name', 'Player_ID', 'Status'] and key in ratings_df.columns and pd.api.types.is_numeric_dtype(ratings_df[key])
    ]

    team_ratings_df = ratings_df[ratings_df['Player_ID'].isin(on_team_player_ids)]

    if team_ratings_df.empty and num_players_on_team > 0: # Players on team, but not in ratings_df
        return _style_single_row_data({col: None for col in cols_for_averaging}, cols_for_averaging), num_players_on_team

    team_averages_raw = {col: team_ratings_df[col].mean() if col in team_ratings_df else None for col in cols_for_averaging}
    styled_team_averages = _style_single_row_data(team_averages_raw, cols_for_averaging)
    return styled_team_averages, num_players_on_team

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

    final_column_display_names = _get_final_column_display_names(request.session, ratings_data_module.ratings.columns)


    # Sort the DataFrame
    if sort_by in ratings_df.columns:
        sorted_ratings_df = ratings_df.sort_values(by=sort_by, ascending=ascending_flag)
    else:
        sorted_ratings_df = ratings_df # No sort or use default if sort_by is invalid
    
    active_team = None 
    active_team_player_ids = set()
    team_player_statuses_map = {}
    on_team_player_ids = set() # Player IDs for those with status 'ON_TEAM'

    if request.user.is_authenticated:
        active_team = Team.objects.filter(creator=request.user, is_active=True).first()
        if active_team:
            # Fetch all player statuses for the active team efficiently
            team_player_entries = TeamPlayer.objects.filter(team=active_team).select_related('team')
            active_team_player_ids = set(tp.player_id for tp in team_player_entries) # All players associated
            team_player_statuses_map = {tp.player_id: tp.status for tp in team_player_entries}
            on_team_player_ids = set(tp.player_id for tp in team_player_entries if tp.status == 'ON_TEAM')

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

    (styled_team_averages_dict, num_players_on_team_calc) = _get_styled_team_averages_and_count(
        ratings_df, active_team, final_column_display_names # Use original ratings_df for source data for averages
    )

    # If active team and players exist, prepare the team average row and prepend it
    if active_team and num_players_on_team_calc > 0 and styled_team_averages_dict:
        team_average_row_for_table = {}
        # Specific info for the team row
        team_average_row_for_table['Name'] = {'value': active_team.name, 'css_class': None}
        team_average_row_for_table['Player_ID'] = {'value': 'TEAM_AVERAGE_ROW', 'css_class': None} # Special ID
        team_average_row_for_table['Status'] = {
            'value': f"Team Avg ({num_players_on_team_calc} Player{'s' if num_players_on_team_calc != 1 else ''})",
            'css_class': None
        }

        # Add the calculated and styled averages
        for col_key, styled_value_dict in styled_team_averages_dict.items():
            team_average_row_for_table[col_key] = styled_value_dict

        # Ensure all displayable columns have an entry in the team average row
        for col_key in final_column_display_names.keys():
            if col_key not in team_average_row_for_table:
                team_average_row_for_table[col_key] = {'value': "N/A", 'css_class': None}

        styled_sorted_ratings_data.insert(0, team_average_row_for_table)

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
        json_response_data = {'success': False} # Initialize response data
        active_team = Team.objects.filter(creator=request.user, is_active=True).first()
        if not active_team:
            json_response_data['error'] = 'No active team found.'
            return JsonResponse(json_response_data, status=400)

        player_id_str = request.POST.get('player_id')
        new_status = request.POST.get('status') # Expected: 'ON_TEAM', 'AVAILABLE', 'UNAVAILABLE'

        if not player_id_str:
            json_response_data['error'] = 'Player ID is required.'
            return JsonResponse(json_response_data, status=400)
        if not new_status or new_status not in [choice[0] for choice in TeamPlayer.STATUS_CHOICES]:
            json_response_data['error'] = 'Invalid status provided.'
            return JsonResponse(json_response_data, status=400)

        try:
            player_id = int(player_id_str)
        except ValueError:
            json_response_data['error'] = 'Invalid Player ID format.'
            return JsonResponse(json_response_data, status=400)

        old_status = None
        try:
            tp_instance = TeamPlayer.objects.get(team=active_team, player_id=player_id)
            old_status = tp_instance.status
        except TeamPlayer.DoesNotExist:
            pass # old_status remains None, player wasn't in TeamPlayer for this team
        
        team_player, created = TeamPlayer.objects.update_or_create(
            team=active_team, player_id=player_id,
            defaults={'status': new_status}
        )

        json_response_data['success'] = True
        message = f"Player status updated to {team_player.get_status_display()}."
        if created and new_status == 'AVAILABLE': # If created with default status, message might be slightly different
            message = f"Player {player_id} record created with status {team_player.get_status_display()}."
        json_response_data['message'] = message
        json_response_data['new_status_code'] = team_player.status
        json_response_data['new_status_display'] = team_player.get_status_display()

        # Check if team composition for averages changed
        player_was_on_team = (old_status == 'ON_TEAM')
        player_is_now_on_team = (team_player.status == 'ON_TEAM')
        recalculate_averages = (player_was_on_team != player_is_now_on_team)

        if recalculate_averages:
            ratings_df_copy = ratings_data_module.ratings.copy()
            current_final_column_names = _get_final_column_display_names(request.session, ratings_data_module.ratings.columns)
            
            styled_avg_data, num_on_team = _get_styled_team_averages_and_count(
                ratings_df_copy, active_team, current_final_column_names
            )
            json_response_data['team_averages_data'] = styled_avg_data # This is the dict of styled values or None
            json_response_data['num_players_on_team'] = num_on_team

        return JsonResponse(json_response_data)

    json_response_data['error'] = 'Invalid request method.'
    return JsonResponse(json_response_data, status=405)


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