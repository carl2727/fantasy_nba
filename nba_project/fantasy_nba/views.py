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
from django.conf import settings # For accessing BASE_DIR
import pandas as pd
import logging
import os

# Get an instance of a logger
logger = logging.getLogger(__name__)
COLUMN_DISPLAY_NAMES = {
    'Name': 'Name',
    'POS': 'POS', # New Position Column
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
    default_cols = [
        'Name', 'PTS_RT', 'REB_RT', 'AST_RT', 'FGN_RT', 'FTN_RT',
        'FG3M_RT', 'BLK_RT', 'STL_RT', 'TOV_RT',
        'Total_Rating', 'Total_Available_Rating'
    ]
    if 'POS' in COLUMN_DISPLAY_NAMES: # Conditionally add POS if defined
        default_cols.insert(1, 'POS') # Insert POS after Name
    return default_cols
    
RATING_CHOICES = [
    (key, COLUMN_DISPLAY_NAMES[key].replace('_RT', '')) for key in COLUMN_DISPLAY_NAMES if key not in ['Name', 'Total_Rating', 'Total_Available_Rating']
]

STATUS_FILTER_CHOICES = [
    ('ALL', 'All Players'),
    ('On Team', 'On Team'),       # Value matches TeamPlayer display name for 'ON_TEAM'
    ('Available', 'Available'),   # Value matches TeamPlayer display name for 'AVAILABLE'
    ('Unavailable', 'Unavailable') # Value matches TeamPlayer display name for 'UNAVAILABLE'
]

if hasattr(settings, 'BASE_DIR'):
    FANTASY_POSITIONS_FILE_PATH = os.path.join(settings.BASE_DIR.parent, 'fantasy_positions.csv')
else:
    logger.error("settings.BASE_DIR is not configured. Cannot determine fantasy_positions.csv path.")
    FANTASY_POSITIONS_FILE_PATH = 'fantasy_positions.csv' 

FANTASY_POSITIONS_DATA_CACHE = {} 

def _load_fantasy_positions_data(file_path=FANTASY_POSITIONS_FILE_PATH):
    """
    Loads fantasy positions from the CSV file.
    Returns a dictionary mapping PERSON_ID to a list of their fantasy positions.
    Uses a simple in-memory cache.
    """
    global FANTASY_POSITIONS_DATA_CACHE
    logger.info(f"Attempting to load fantasy positions from: {file_path}")

    logger.info("Forcing reload of fantasy positions data (cache disabled for debugging).")
    
    player_positions_map = {}
    try:
        if not os.path.exists(file_path):
            logger.error(f"Fantasy positions file not found: {file_path}")
            return {}

        df = pd.read_csv(file_path, dtype={'PERSON_ID': str}) 
        if 'PERSON_ID' not in df.columns or 'FANTASY_POSITION' not in df.columns:
            logger.error(f"Fantasy positions file {file_path} is missing required columns: PERSON_ID or FANTASY_POSITION.")
            return {}

        df['PERSON_ID_NUMERIC'] = pd.to_numeric(df['PERSON_ID'], errors='coerce')
        
        original_count = len(df)
        df.dropna(subset=['PERSON_ID_NUMERIC'], inplace=True)
        converted_count = len(df)
        
        if original_count != converted_count:
            logger.warning(f"{original_count - converted_count} rows in {file_path} had non-numeric or missing PERSON_ID and were dropped.")

        if df.empty:
            logger.warning(f"No valid numeric PERSON_IDs found in {file_path} after conversion. The map will be empty.")
            FANTASY_POSITIONS_DATA_CACHE = {}
            return {}
            
        df['PERSON_ID_INT'] = df['PERSON_ID_NUMERIC'].astype(int)

        player_positions_map = df.groupby('PERSON_ID_INT')['FANTASY_POSITION'].apply(
            lambda x: sorted(list(set(x.astype(str).dropna())))
        ).to_dict()

        # ---- START DETAILED DEBUG for _load_fantasy_positions_data ----
        logger.info(f"DEBUG (_load_fantasy_positions_data): player_positions_map created with {len(player_positions_map)} entries.")
        ids_to_check_in_map_creation = [1628983, 203999, 1630162, 1628369, 1626157] 
        found_in_map_creation = {id_val: player_positions_map.get(id_val) for id_val in ids_to_check_in_map_creation if id_val in player_positions_map}
        
        if found_in_map_creation:
            key_type_example = type(list(found_in_map_creation.keys())[0]) if found_in_map_creation else 'N/A'
            logger.info(f"DEBUG (_load_fantasy_positions_data): Specific IDs FOUND in map (key type: {key_type_example}): {found_in_map_creation}")
        
        map_keys_sample_creation = list(player_positions_map.keys())[:5]
        if map_keys_sample_creation:
            logger.info(f"DEBUG (_load_fantasy_positions_data): Sample of actual keys in map: {map_keys_sample_creation}. Types: {[type(k) for k in map_keys_sample_creation]}")
        # ---- END DETAILED DEBUG for _load_fantasy_positions_data ----

        FANTASY_POSITIONS_DATA_CACHE = player_positions_map 
        logger.info(f"Successfully loaded/reloaded fantasy positions from {file_path}. Map has {len(player_positions_map)} entries.")
    except Exception as e:
        logger.error(f"Error loading fantasy positions from {file_path}: {e}", exc_info=True)
    return player_positions_map

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
        else: 
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
    current_status_filter = request.GET.get('status_filter', 'ALL')
    fantasy_positions_map = _load_fantasy_positions_data()


    final_column_display_names = _get_final_column_display_names(request.session, ratings_data_module.ratings.columns)
    
    user_teams = None
    active_team = None 
    active_team_player_ids = set()
    team_player_statuses_map = {}
    on_team_player_ids = set() 

    if request.user.is_authenticated:
        user_teams = Team.objects.filter(creator=request.user)
        active_team = user_teams.filter(is_active=True).first()
        if active_team:
            team_player_entries = TeamPlayer.objects.filter(team=active_team).select_related('team')
            active_team_player_ids = set(tp.player_id for tp in team_player_entries) 
            team_player_statuses_map = {tp.player_id: tp.status for tp in team_player_entries}
            on_team_player_ids = set(tp.player_id for tp in team_player_entries if tp.status == 'ON_TEAM')


    initial_data_list = []
    for record in ratings_df.to_dict('records'):
        processed_record = {}
        player_id_val = record.get('Player_ID')

        processed_record['Player_ID'] = player_id_val

        is_on_team_flag = False
        if player_id_val is not None:
            try:
                is_on_team_flag = int(float(player_id_val)) in active_team_player_ids
            except (ValueError, TypeError):
                logger.warning(f"Could not convert Player_ID '{player_id_val}' to int for team check in show_ratings.")
        processed_record['is_on_team'] = is_on_team_flag

        current_status_display = 'Available' 
        if active_team and player_id_val is not None:
            try:
                player_id_int = int(float(player_id_val))
                status_code = team_player_statuses_map.get(player_id_int, 'AVAILABLE') 
                current_status_display = dict(TeamPlayer.STATUS_CHOICES).get(status_code, 'Available')
            except (ValueError, TypeError):
                logger.warning(f"Could not convert Player_ID '{player_id_val}' to int for status lookup in show_ratings.")
        processed_record['Status'] = current_status_display

        fantasy_positions_str = "N/A" 
        if player_id_val is not None:
            try:
                player_id_int = int(float(player_id_val)) 

                # ---- START PRE-LOOKUP DEBUG for show_ratings ----
                ids_to_debug_lookup = [1628983, 203999, 1630162] 
                if player_id_int in ids_to_debug_lookup:
                    is_key_present = player_id_int in fantasy_positions_map
                    logger.info(f"PRE-LOOKUP DEBUG (show_ratings) for Player_ID {player_id_int}: Is key in map? {is_key_present}")
                    if is_key_present:
                        logger.info(f"PRE-LOOKUP DEBUG (show_ratings) for Player_ID {player_id_int}: Value in map is {fantasy_positions_map[player_id_int]}")
                    else:
                        logger.info(f"PRE-LOOKUP DEBUG (show_ratings) for Player_ID {player_id_int}: Key NOT in map. Map size: {len(fantasy_positions_map)}. First 20 map keys: {list(fantasy_positions_map.keys())[:20]}")
                # ---- END PRE-LOOKUP DEBUG for show_ratings ----

                positions_list = fantasy_positions_map.get(player_id_int, [])
                
                if positions_list:
                    fantasy_positions_str = ", ".join(positions_list) 
            except (ValueError, TypeError):
                logger.warning(f"Could not process Player_ID '{player_id_val}' for fantasy position lookup in show_ratings.", exc_info=True)
        processed_record['POS'] = fantasy_positions_str
        
        # ---- START POST-LOOKUP DEBUG for show_ratings ----
        if player_id_val is not None:
            player_id_int_for_debug = None
            try:
                player_id_int_for_debug = int(float(player_id_val))
                if player_id_int_for_debug == 1628983: # SGA
                    logger.info(f"POST-LOOKUP DEBUG (show_ratings) for SGA (1628983): processed_record['POS'] set to '{processed_record['POS']}'")
            except (ValueError, TypeError):
                pass 
        # ---- END POST-LOOKUP DEBUG for show_ratings ----

        for col_key in final_column_display_names.keys():
            if col_key not in processed_record: 
                if col_key in record:
                    processed_record[col_key] = record[col_key]
        initial_data_list.append(processed_record)
    
    if current_status_filter != 'ALL':
        initial_data_list = [
            record for record in initial_data_list
            if record.get('Status') == current_status_filter
        ]

    styled_ratings_data = _apply_styles_to_data(initial_data_list, STYLED_COLUMNS)

    (styled_team_averages_dict, num_players_on_team_calc) = _get_styled_team_averages_and_count(
        ratings_df, active_team, final_column_display_names
    )

    if active_team and num_players_on_team_calc > 0 and styled_team_averages_dict:
        team_average_row_for_table = {}
        team_average_row_for_table['Name'] = {'value': active_team.name, 'css_class': None}
        team_average_row_for_table['Player_ID'] = {'value': 'TEAM_AVERAGE_ROW', 'css_class': None} 
        team_average_row_for_table['Status'] = {
            'value': f"Team Avg ({num_players_on_team_calc} Player{'s' if num_players_on_team_calc != 1 else ''})",
            'css_class': None 
        }

        for col_key, styled_value_dict in styled_team_averages_dict.items():
            team_average_row_for_table[col_key] = styled_value_dict
        
        for col_key in final_column_display_names.keys():
            if col_key not in team_average_row_for_table:
                team_average_row_for_table[col_key] = {'value': "N/A", 'css_class': None}

        styled_ratings_data.insert(0, team_average_row_for_table)

    # ---- START PRE-RENDER DEBUG for show_ratings ----
    for styled_player_row in styled_ratings_data:
        if 'Player_ID' in styled_player_row and styled_player_row['Player_ID'].get('value') == 1628983:
            sga_pos_data = styled_player_row.get('POS', {'value': 'POS_KEY_MISSING_IN_STYLED_ROW', 'css_class': None})
            logger.info(f"PRE-RENDER DEBUG (show_ratings) for SGA (1628983): styled_ratings_data['POS'] is {sga_pos_data}")
            break 
    # ---- END PRE-RENDER DEBUG for show_ratings ----
    
    context = {
        'ratings': styled_ratings_data,
        'column_display_names': final_column_display_names,
        'teams': user_teams if request.user.is_authenticated else None, 
        'active_team': active_team,  
        'status_filter_choices': STATUS_FILTER_CHOICES,
        'current_status_filter': current_status_filter,
    }
    return render(request, 'fantasy_nba/show_ratings.html', context)

def _style_single_row_data(data_dict: dict, columns_to_apply_css_to: list):
    styled_row = {}
    for col_actual_name, raw_value in data_dict.items():
        css_class = None
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
        return None, 0 

    team_averages_raw = {}
    cols_for_averaging = [
        key for key in final_column_display_names_map.keys()
        if key not in ['Name', 'Player_ID', 'Status'] and key in ratings_df.columns and pd.api.types.is_numeric_dtype(ratings_df[key])
    ]

    team_ratings_df = ratings_df[ratings_df['Player_ID'].isin(on_team_player_ids)]

    if team_ratings_df.empty and num_players_on_team > 0: 
        return _style_single_row_data({col: None for col in cols_for_averaging}, cols_for_averaging), num_players_on_team

    team_averages_raw = {col: team_ratings_df[col].mean() if col in team_ratings_df else None for col in cols_for_averaging}
    styled_team_averages = _style_single_row_data(team_averages_raw, cols_for_averaging)
    return styled_team_averages, num_players_on_team

def sort_ratings(request: HttpRequest):
    sort_by = request.GET.get('sort_by')
    current_status_filter = request.GET.get('status_filter', 'ALL')
    fantasy_positions_map = _load_fantasy_positions_data()
    ratings_df = ratings_data_module.ratings.copy()

    ascending_flag = False 
    if sort_by == request.session.get('sort_by'):
        if request.session.get('sort_direction') == 'asc':
            request.session['sort_direction'] = 'desc'
            ascending_flag = False 
        else: 
            request.session['sort_direction'] = 'asc'
            ascending_flag = True  
    else:
        request.session['sort_by'] = sort_by
        request.session['sort_direction'] = 'desc'
        ascending_flag = False 

    final_column_display_names = _get_final_column_display_names(request.session, ratings_data_module.ratings.columns)

    if sort_by in ratings_df.columns:
        sorted_ratings_df = ratings_df.sort_values(by=sort_by, ascending=ascending_flag)
    else:
        sorted_ratings_df = ratings_df 
    
    active_team = None 
    active_team_player_ids = set()
    team_player_statuses_map = {}
    on_team_player_ids = set() 

    if request.user.is_authenticated:
        active_team = Team.objects.filter(creator=request.user, is_active=True).first()
        if active_team:
            team_player_entries = TeamPlayer.objects.filter(team=active_team).select_related('team')
            active_team_player_ids = set(tp.player_id for tp in team_player_entries) 
            team_player_statuses_map = {tp.player_id: tp.status for tp in team_player_entries}
            on_team_player_ids = set(tp.player_id for tp in team_player_entries if tp.status == 'ON_TEAM')

    initial_data_list_sorted = []
    for record in sorted_ratings_df.to_dict('records'): 
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

        current_status_display = 'Available' 
        if active_team and player_id_val is not None:
            try:
                player_id_int = int(float(player_id_val))
                status_code = team_player_statuses_map.get(player_id_int, 'AVAILABLE')
                current_status_display = dict(TeamPlayer.STATUS_CHOICES).get(status_code, 'Available')
            except (ValueError, TypeError):
                logger.warning(f"Could not convert Player_ID '{player_id_val}' to int for status lookup in sort_ratings.")
        processed_record['Status'] = current_status_display

        fantasy_positions_str = "N/A" 
        if player_id_val is not None:
            try:
                player_id_int = int(float(player_id_val)) 
                positions_list = fantasy_positions_map.get(player_id_int, [])
                if positions_list:
                    fantasy_positions_str = ", ".join(positions_list) 
            except (ValueError, TypeError):
                logger.warning(f"Could not process Player_ID '{player_id_val}' for fantasy position lookup in sort_ratings.")
        processed_record['POS'] = fantasy_positions_str
        
        # ---- START POST-LOOKUP DEBUG for sort_ratings (similar to show_ratings) ----
        if player_id_val is not None:
            player_id_int_for_debug = None
            try:
                player_id_int_for_debug = int(float(player_id_val))
                if player_id_int_for_debug == 1628983: # SGA
                    logger.info(f"POST-LOOKUP DEBUG (sort_ratings) for SGA (1628983): processed_record['POS'] set to '{processed_record['POS']}'")
            except (ValueError, TypeError):
                pass 
        # ---- END POST-LOOKUP DEBUG for sort_ratings ----

        for col_key in final_column_display_names.keys():
            if col_key not in processed_record: 
                if col_key in record:
                    processed_record[col_key] = record[col_key]
        initial_data_list_sorted.append(processed_record)
    
    if current_status_filter != 'ALL':
        initial_data_list_sorted = [
            record for record in initial_data_list_sorted
            if record.get('Status') == current_status_filter
        ]

    styled_sorted_ratings_data = _apply_styles_to_data(initial_data_list_sorted, STYLED_COLUMNS)

    (styled_team_averages_dict, num_players_on_team_calc) = _get_styled_team_averages_and_count(
        ratings_df, active_team, final_column_display_names 
    )

    if active_team and num_players_on_team_calc > 0 and styled_team_averages_dict:
        team_average_row_for_table = {}
        team_average_row_for_table['Name'] = {'value': active_team.name, 'css_class': None}
        team_average_row_for_table['Player_ID'] = {'value': 'TEAM_AVERAGE_ROW', 'css_class': None} 
        team_average_row_for_table['Status'] = {
            'value': f"Team Avg ({num_players_on_team_calc} Player{'s' if num_players_on_team_calc != 1 else ''})",
            'css_class': None
        }

        for col_key, styled_value_dict in styled_team_averages_dict.items():
            team_average_row_for_table[col_key] = styled_value_dict

        for col_key in final_column_display_names.keys():
            if col_key not in team_average_row_for_table:
                team_average_row_for_table[col_key] = {'value': "N/A", 'css_class': None}

        styled_sorted_ratings_data.insert(0, team_average_row_for_table)
    
    # ---- START PRE-RENDER DEBUG for sort_ratings (similar to show_ratings) ----
    for styled_player_row in styled_sorted_ratings_data:
        if 'Player_ID' in styled_player_row and styled_player_row['Player_ID'].get('value') == 1628983:
            sga_pos_data = styled_player_row.get('POS', {'value': 'POS_KEY_MISSING_IN_STYLED_ROW', 'css_class': None})
            logger.info(f"PRE-RENDER DEBUG (sort_ratings) for SGA (1628983): styled_ratings_data['POS'] is {sga_pos_data}")
            break 
    # ---- END PRE-RENDER DEBUG for sort_ratings ----

    context = {
        'ratings': styled_sorted_ratings_data,
        'column_display_names': final_column_display_names,
        'sort_by': request.session.get('sort_by'),
        'sort_direction': request.session.get('sort_direction'),
        'active_team': active_team, 
        'status_filter_choices': STATUS_FILTER_CHOICES,
        'current_status_filter': current_status_filter,
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
        for col_actual_name, raw_value in player_row_dict.items(): 
            value_to_store = raw_value 

            if col_actual_name == 'Player_ID':
                try:
                    if pd.notna(raw_value):
                        value_to_store = int(float(raw_value))
                    else:
                        value_to_store = None 
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert Player_ID value '{raw_value}' to int during styling.")
                    value_to_store = None 

            css_class = None
            if col_actual_name in columns_to_style:
                value_for_styling = raw_value
                css_class = _get_value_based_css_class(value_for_styling)
            
            styled_player_row[col_actual_name] = {'value': value_to_store, 'css_class': css_class}
        styled_data.append(styled_player_row)
    return styled_data

def breakdown(request):
    return render(request, 'fantasy_nba/breakdown.html')

def login_register(request):
    login_form = AuthenticationForm()
    register_form = MinimalUserCreationForm()  

    if request.method == 'POST':
        if 'login' in request.POST:
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                return redirect('show_ratings')
        elif 'register' in request.POST:
            register_form = MinimalUserCreationForm(request.POST)  
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
        name = request.POST.get('name', '').strip() 
        if name: 
            team = Team.objects.create(name=name, creator=request.user)
            if Team.objects.filter(creator=request.user).count() == 1:
                team.is_active = True
                team.save()
            messages.success(request, f"Team '{name}' created successfully.")
            return redirect('team')
        else:
            messages.error(request, "Team name cannot be empty or consist only of spaces.")
            
    return render(request, 'fantasy_nba/create_team.html') 

@login_required
def team(request):
    teams = Team.objects.filter(creator=request.user)

    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        if team_id:
            Team.objects.filter(creator=request.user).update(is_active=False)
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
            
    active_team = teams.filter(is_active=True).first()
    return render(request, 'fantasy_nba/team.html', {'teams': teams, 'active_team': active_team})

@login_required
def update_player_status(request):
    if request.method == 'POST':
        json_response_data = {'success': False} 
        active_team = Team.objects.filter(creator=request.user, is_active=True).first()
        if not active_team:
            json_response_data['error'] = 'No active team found.'
            return JsonResponse(json_response_data, status=400)

        player_id_str = request.POST.get('player_id')
        new_status = request.POST.get('status') 

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
            pass 
        
        team_player, created = TeamPlayer.objects.update_or_create(
            team=active_team, player_id=player_id,
            defaults={'status': new_status}
        )

        json_response_data['success'] = True
        message = f"Player status updated to {team_player.get_status_display()}."
        if created and new_status == 'AVAILABLE': 
            message = f"Player {player_id} record created with status {team_player.get_status_display()}."
        json_response_data['message'] = message
        json_response_data['new_status_code'] = team_player.status
        json_response_data['new_status_display'] = team_player.get_status_display()

        player_was_on_team = (old_status == 'ON_TEAM')
        player_is_now_on_team = (team_player.status == 'ON_TEAM')
        recalculate_averages = (player_was_on_team != player_is_now_on_team)

        if recalculate_averages:
            ratings_df_copy = ratings_data_module.ratings.copy()
            current_final_column_names = _get_final_column_display_names(request.session, ratings_data_module.ratings.columns)
            
            styled_avg_data, num_on_team = _get_styled_team_averages_and_count(
                ratings_df_copy, active_team, current_final_column_names
            )
            json_response_data['team_averages_data'] = styled_avg_data 
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

        team_player, created = TeamPlayer.objects.get_or_create(
            team=active_team,
            player_id=player_id,
            defaults={'status': 'ON_TEAM'} 
        )
        return JsonResponse({'success': False, 'error': 'This endpoint is deprecated. Use update_player_status.'}, status=405)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

@login_required
def remove_player(request):
    return JsonResponse({'success': False, 'error': 'This endpoint is deprecated. Use update_player_status.'}, status=405)

@login_required
def toggle_availability(request):
    return JsonResponse({'success': False, 'error': 'This endpoint is deprecated. Use update_player_status.'}, status=405)

def logout_view(request):
    logout(request)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
