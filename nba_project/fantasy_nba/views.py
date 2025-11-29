# views.py
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpRequest, JsonResponse, Http404
from . import ratings as ratings_data_module
from .models import Team, TeamPlayer, DraftPick
from django.db import transaction
from .forms import MinimalUserCreationForm, TeamNameForm
from django.conf import settings
import pandas as pd
import logging
import os

# Get an instance of a logger
logger = logging.getLogger(__name__)
COLUMN_DISPLAY_NAMES = {
    'Name': 'Name',
    'POS': 'POS',
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
    'Combined_Rating': 'Combined Rating',
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

DESIRED_POSITIONS_ORDER = ['PG', 'SG', 'G', 'SF', 'PF', 'F', 'C', 'C']
CORE_POSITIONS_ROSTER_NEEDS = {'PG': 1, 'SG': 1, 'SF': 1, 'PF': 1, 'C': 2}

def _get_default_columns():
    """Returns a default list of column keys for display."""
    # This function's direct operational use in show_ratings is limited
    # as columns_to_extract is dynamically built.
    # Providing a sensible default list of keys.
    default_cols = [
        'Name', 'PTS_RT', 'REB_RT', 'AST_RT', 'FGN_RT', 'FTN_RT',
        'FG3M_RT', 'BLK_RT', 'STL_RT', 'TOV_RT',
        'Total_Rating', 'Total_Available_Rating', 'Combined_Rating'
    ]
    if 'POS' in COLUMN_DISPLAY_NAMES: # Conditionally add POS if defined
        default_cols.insert(1, 'POS') # Insert POS after Name
    return default_cols
    
RATING_CHOICES = [
    (key, COLUMN_DISPLAY_NAMES[key].replace('_RT', ''))
    for key in COLUMN_DISPLAY_NAMES
    if key not in ['Name', 'Total_Rating', 'Total_Available_Rating', 'Combined_Rating', 'Player_ID']
]

STATUS_FILTER_CHOICES = [
    ('ALL', 'All Players'),
    ('On Team', 'On Team'),       # Value matches TeamPlayer display name for 'ON_TEAM'
    ('Available', 'Available'),   # Value matches TeamPlayer display name for 'AVAILABLE'
    ('Unavailable', 'Unavailable'), # Value matches TeamPlayer display name for 'UNAVAILABLE'
    ('Injured', 'Injured'),        # New filter for injured players
    ('Healthy', 'Healthy')         # New filter for healthy players
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
    
    if FANTASY_POSITIONS_DATA_CACHE: # Check if cache is populated
        logger.info(f"Using cached fantasy positions data. Map has {len(FANTASY_POSITIONS_DATA_CACHE)} entries.")
        return FANTASY_POSITIONS_DATA_CACHE

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
            
        df['PERSON_ID_INT'] = df['PERSON_ID_NUMERIC'].astype(int) # Ensure it's int for consistent key type

        player_positions_map = df.groupby('PERSON_ID_INT')['FANTASY_POSITION'].apply(lambda x: sorted(list(set(x.astype(str).dropna())))).to_dict()

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

    # Remove punted categories from display
    for category in punted_categories:
        if category in final_names:
            del final_names[category]

    if punted_categories:
        punt_suffix = "_Punt_" + "_".join(sorted([cat.replace('_RT', '') for cat in punted_categories]))
        punt_perf_col_actual_name_candidate = f'Total{punt_suffix}_Available_Rating'
        punt_overall_col_actual_name_candidate = f'Total{punt_suffix}_Rating'
        punt_combined_col_actual_name_candidate = f'Total{punt_suffix}_Combined_Rating'

        # Check if punt-specific ratings exist and replace the standard ratings
        if punt_perf_col_actual_name_candidate in all_rating_columns:
            # Replace the standard Performance Rating with the punt-specific one
            final_names[punt_perf_col_actual_name_candidate] = "Performance Rating"
            # Remove the standard Performance Rating from display
            if 'Total_Available_Rating' in final_names:
                del final_names['Total_Available_Rating']

        if punt_overall_col_actual_name_candidate in all_rating_columns:
            # Replace the standard Overall Rating with the punt-specific one
            final_names[punt_overall_col_actual_name_candidate] = "Overall Rating"
            # Remove the standard Overall Rating from display
            if 'Total_Rating' in final_names:
                del final_names['Total_Rating']
        
        if punt_combined_col_actual_name_candidate in all_rating_columns:
            # Replace the standard Combined Rating with the punt-specific one
            final_names[punt_combined_col_actual_name_candidate] = "Combined Rating"
            if 'Combined_Rating' in final_names:
                del final_names['Combined_Rating']

    final_names['Status'] = 'Status'
    return final_names

def _extract_columns_for_display(final_column_display_names_map, all_rating_columns):
    """
    From the final_column_display_names_map, returns a list of actual column keys
    that exist in all_rating_columns or are special keys like 'Name', 'Player_ID', 'Status'.
    This ensures we only try to extract/display columns that can be sourced.
    """
    return [key for key in final_column_display_names_map.keys() if key in all_rating_columns or key in ['Name', 'Player_ID', 'Status']]

class SettingsForm(forms.Form):
    enable_heatmap = forms.BooleanField(
        required=False,
        label='Heatmap'
    )
    enable_tier_colors = forms.BooleanField(
        required=False,
        label='Tier Colors'
    )

class PuntForm(forms.Form):
    punt_category_1 = forms.ChoiceField(
        choices=[('', '-')] + RATING_CHOICES,
        required=False,
        label='Punt Category 1'
    )
    punt_category_2 = forms.ChoiceField(
        choices=[('', '-')] + RATING_CHOICES,
        required=False,
        label='Punt Category 2'
    )

def punt(request: HttpRequest):
    if request.method == 'POST':
        if 'save_punt' in request.POST:
            punt_form = PuntForm(request.POST)
            settings_form = SettingsForm(initial={
                'enable_heatmap': request.session.get('enable_heatmap', False),
                'enable_tier_colors': request.session.get('enable_tier_colors', False)
            })
            if punt_form.is_valid():
                punted_categories = [
                    punt_form.cleaned_data['punt_category_1'],
                    punt_form.cleaned_data['punt_category_2'],
                ]
                punted_categories = [cat for cat in punted_categories if cat]
                request.session['punted_categories'] = punted_categories
                return redirect('show_ratings')
        elif 'save_settings' in request.POST:
            settings_form = SettingsForm(request.POST)
            punt_form = PuntForm(initial={
                'punt_category_1': request.session.get('punted_categories', ['',''])[0] if request.session.get('punted_categories') else '',
                'punt_category_2': request.session.get('punted_categories', ['',''])[1] if len(request.session.get('punted_categories', [])) > 1 else '',
            })
            if settings_form.is_valid():
                request.session['enable_heatmap'] = settings_form.cleaned_data.get('enable_heatmap', False)
                request.session['enable_tier_colors'] = settings_form.cleaned_data.get('enable_tier_colors', False)
                return redirect('show_ratings')
    else:
        punted = request.session.get('punted_categories', [])
        punt_form = PuntForm(initial={
            'punt_category_1': punted[0] if len(punted) > 0 else '',
            'punt_category_2': punted[1] if len(punted) > 1 else '',
        })
        settings_form = SettingsForm(initial={
            'enable_heatmap': request.session.get('enable_heatmap', False),
            'enable_tier_colors': request.session.get('enable_tier_colors', False)
        })
    return render(request, 'fantasy_nba/punt.html', {'form': punt_form, 'settings_form': settings_form})

def _get_team_position_coverage(active_team, fantasy_positions_map):
    """
    Calculates the fantasy position coverage for the active team.
    Returns a string detailing covered and missing positions.
    """
    if not active_team:
        return "No active team selected." # Should not happen if called correctly

    on_team_player_ids_str = list(
        TeamPlayer.objects.filter(team=active_team, status='ON_TEAM').values_list('player_id', flat=True)
    )

    if not on_team_player_ids_str:
        return "PG, SG, G, SF, PF, F, C, C"

    players_on_team_with_pos = []
    for player_id in on_team_player_ids_str:
        # Ensure player_id is an int for lookup, as fantasy_positions_map uses int keys
        try:
            pid_int = int(float(player_id))
            positions = fantasy_positions_map.get(pid_int, [])
            if positions: # Only consider players with known positions
                players_on_team_with_pos.append({'id': pid_int, 'fantasy_pos': positions})
        except (ValueError, TypeError):
            logger.warning(f"Could not process player_id {player_id} for position coverage due to conversion error.")
            continue


    # Sort players: those with fewer positions get assignment priority for their specific slots
    sorted_players = sorted(players_on_team_with_pos, key=lambda p: len(p['fantasy_pos']))

    filled_core_slots_count = {'PG': 0, 'SG': 0, 'SF': 0, 'PF': 0, 'C': 0}
    # To track which specific player filled which slot (optional, mainly for complex tie-breaking or detailed display)
    # player_slot_assignments = {} # Example: {player_id: 'PG', player_id2: 'C1'}

    # Make a copy of sorted_players to remove players once assigned
    available_players = list(sorted_players)


    # Pass 1: Assign players to their exact core positions
    for player_data in list(available_players): # Iterate over a copy for safe removal
        player_id = player_data['id']
        player_positions = player_data['fantasy_pos']
        
        assigned_this_player = False
        # Prioritize single-position players or exact matches for multi-position players
        for pos in player_positions:
            if pos in CORE_POSITIONS_ROSTER_NEEDS: # PG, SG, SF, PF, C
                if filled_core_slots_count[pos] < CORE_POSITIONS_ROSTER_NEEDS[pos]:
                    filled_core_slots_count[pos] += 1
                    # player_slot_assignments[player_id] = pos # Or a more specific slot like C1/C2
                    available_players.remove(player_data)
                    assigned_this_player = True
                    break # Player assigned, move to next player
        if assigned_this_player:
            continue

    # Note: The above logic is a greedy approach. For more optimal filling,
    # especially with multi-position players, a more complex assignment algorithm
    # (like bipartite matching or flow networks) could be used, but this
    # should be a good heuristic for typical fantasy scenarios.
    # The current sorting helps by trying to fill specific needs first.

    # Determine coverage for each core and derived position
    pg_covered = filled_core_slots_count['PG'] >= CORE_POSITIONS_ROSTER_NEEDS['PG']
    sg_covered = filled_core_slots_count['SG'] >= CORE_POSITIONS_ROSTER_NEEDS['SG']
    sf_covered = filled_core_slots_count['SF'] >= CORE_POSITIONS_ROSTER_NEEDS['SF']
    pf_covered = filled_core_slots_count['PF'] >= CORE_POSITIONS_ROSTER_NEEDS['PF']

    g_covered = pg_covered or sg_covered
    f_covered = sf_covered or pf_covered

    for slot in DESIRED_POSITIONS_ORDER:
        status = "missing"
        if slot == 'PG':
            if pg_covered: status = "covered" # Not used in new format, but shows logic
        elif slot == 'SG':
            if sg_covered: status = "covered" # Not used
        elif slot == 'G':
            if g_covered: status = "covered" # Not used
        elif slot == 'SF':
            if sf_covered: status = "covered" # Not used
        elif slot == 'PF':
            if pf_covered: status = "covered" # Not used
        elif slot == 'F':
            if f_covered: status = "covered" # Not used
        elif slot == 'C': # This will be called twice for the two 'C' slots
            # Logic for C handled below in missing_display_parts
            pass
        
    # Build the "Missing Positions" string
    missing_display_parts = []
    c_slots_in_desired_order_accounted_for = 0 # To track how many 'C' slots from DESIRED_POSITIONS_ORDER we've checked

    for slot_type in DESIRED_POSITIONS_ORDER:
        is_this_slot_type_missing = True 
        if slot_type == 'PG' and pg_covered: is_this_slot_type_missing = False
        elif slot_type == 'SG' and sg_covered: is_this_slot_type_missing = False
        elif slot_type == 'G' and g_covered: is_this_slot_type_missing = False
        elif slot_type == 'SF' and sf_covered: is_this_slot_type_missing = False
        elif slot_type == 'PF' and pf_covered: is_this_slot_type_missing = False
        elif slot_type == 'F' and f_covered: is_this_slot_type_missing = False
        elif slot_type == 'C':
            c_slots_in_desired_order_accounted_for += 1
            if filled_core_slots_count['C'] >= c_slots_in_desired_order_accounted_for:
                is_this_slot_type_missing = False
            
        if is_this_slot_type_missing:
            missing_display_parts.append(slot_type)

    if not on_team_player_ids_str: # Corrected variable name
        return f"{', '.join(DESIRED_POSITIONS_ORDER)}"
    if not missing_display_parts:
        return "All positions covered."
    else:
        return f"{', '.join(missing_display_parts)}"

def _ensure_and_get_draft_picks(team, ratings_df):
    """
    Ensures draft picks exist for a team and returns them as a DataFrame.
    If they don't exist, creates them based on Total_Rating.
    """
    if not team:
        return pd.DataFrame(columns=['player_id', 'pick_number'])

    if not DraftPick.objects.filter(team=team).exists():
        # Sort players by Total_Rating descending to establish initial draft order
        sorted_df = ratings_df.sort_values(by='Total_Rating', ascending=False)
        draft_picks_to_create = []
        for i, row in enumerate(sorted_df.itertuples(), 1):
            player_id = getattr(row, 'Player_ID', None)
            if player_id is not None:
                try:
                    player_id_str = str(int(float(player_id)))
                    draft_picks_to_create.append(
                        DraftPick(team=team, player_id=player_id_str, pick_number=int(i))
                    )
                except (ValueError, TypeError):
                    logger.warning(f"Could not process Player_ID '{player_id}' for draft pick creation.")
        if draft_picks_to_create:
            DraftPick.objects.bulk_create(draft_picks_to_create)

    return pd.DataFrame.from_records(DraftPick.objects.filter(team=team).values('player_id', 'pick_number'))
def _ensure_draft_picks_exist(team, ratings_df):
    """
    Checks if draft picks exist for a team. If not, creates them based on Total_Rating.
    """
    if not team or DraftPick.objects.filter(team=team).exists():
        return

    # Sort players by Total_Rating descending to establish initial draft order
    sorted_df = ratings_df.sort_values(by='Total_Rating', ascending=False)

    draft_picks_to_create = []
    for i, row in enumerate(sorted_df.itertuples(), 1):
        player_id = getattr(row, 'Player_ID', None)
        if player_id is not None:
            try:
                # Ensure player_id is consistently stored, e.g., as a string of an int
                player_id_str = str(int(float(player_id)))
                draft_picks_to_create.append(
                    DraftPick(team=team, player_id=player_id_str, pick_number=i)
                )
            except (ValueError, TypeError):
                logger.warning(f"Could not process Player_ID '{player_id}' for draft pick creation.")

    if draft_picks_to_create:
        DraftPick.objects.bulk_create(draft_picks_to_create)

def _get_punt_categories_string(session_data):
    """
    Generates a string showing the punt categories if any are set.
    Returns a formatted string like "Punt categories: STL, BLK" or None if no punt categories.
    """
    punted_categories = session_data.get('punted_categories', [])
    
    if not punted_categories:
        return None
    
    # Convert category codes to display names
    punted_display_names = []
    for cat in punted_categories:
        if cat in COLUMN_DISPLAY_NAMES:
            display_name = COLUMN_DISPLAY_NAMES[cat].replace('_RT', '')
            punted_display_names.append(display_name)
    
    if len(punted_display_names) == 1:
        return f"Punt categories: {punted_display_names[0]}"
    elif len(punted_display_names) == 2:
        return f"Punt categories: {punted_display_names[0]}, {punted_display_names[1]}"
    else:
        return f"Punt categories: {', '.join(punted_display_names)}"

def show_ratings(request: HttpRequest):
    # ... (existing code for ratings_df, current_status_filter, fantasy_positions_map, sorting) ...
    ratings_df = ratings_data_module.ratings.copy()
    current_status_filter = request.GET.get('status_filter', 'ALL')
    fantasy_positions_map = _load_fantasy_positions_data()
    
    # --- Sorting Logic ---
    sort_by_param = request.GET.get('sort_by')
    toggle_param = request.GET.get('toggle')
    
    # Load draft picks early if there's an active team, to allow sorting by Draft_Pos
    active_team_for_draft = Team.objects.filter(creator=request.user, is_active=True).first() if request.user.is_authenticated else None
    if active_team_for_draft:
        draft_picks_df = _ensure_and_get_draft_picks(active_team_for_draft, ratings_df)
        if not draft_picks_df.empty:
            # Convert player_id to match the type in ratings_df for merging
            draft_picks_df['player_id'] = pd.to_numeric(draft_picks_df['player_id'], errors='coerce')
            ratings_df = pd.merge(
                ratings_df,
                draft_picks_df.rename(columns={'player_id': 'Player_ID', 'pick_number': 'Draft_Pos'}),
                on='Player_ID',
                how='left'
            )

    active_sort_column = request.session.get('show_ratings_sort_by', None)
    active_sort_direction = request.session.get('show_ratings_sort_direction', 'desc') 

    # Only toggle or change sort settings when user clicked a header (toggle=1)
    if sort_by_param and toggle_param == '1':
        # Special case for Draft_Pos which is only available with an active team
        if sort_by_param == 'Draft_Pos' and not active_team_for_draft:
            pass # Do not sort by Draft_Pos if there is no active team
        elif active_sort_column == sort_by_param:
            current_sort_direction = 'asc' if active_sort_direction == 'desc' else 'desc'
        else:
            current_sort_direction = 'desc'

        request.session['show_ratings_sort_by'] = sort_by_param
        request.session['show_ratings_sort_direction'] = current_sort_direction

        active_sort_column = sort_by_param
        active_sort_direction = current_sort_direction

    if active_sort_column and active_sort_column in ratings_df.columns and (sort_by_param or request.session.get('show_ratings_sort_by')):
        # For Draft_Pos, lower number is better, so 'desc' should be ascending sort.
        if active_sort_column == 'Draft_Pos':
            ascending_flag = (active_sort_direction == 'desc')
        else: # For all other columns, 'asc' means ascending.
            ascending_flag = (active_sort_direction == 'asc')
        if ratings_df[active_sort_column].dtype == 'object':
            if active_sort_column == 'Name':
                 ratings_df = ratings_df.sort_values(
                    by=active_sort_column, 
                    ascending=ascending_flag, 
                    na_position='last',
                    key=lambda col: col.astype(str).str.lower() 
                )
            else:
                ratings_df = ratings_df.sort_values(by=active_sort_column, ascending=ascending_flag, na_position='last')
        else: 
            ratings_df = ratings_df.sort_values(by=active_sort_column, ascending=ascending_flag)
    # --- End of Sorting Logic ---
    
    final_column_display_names = _get_final_column_display_names(request.session, ratings_data_module.ratings.columns)
    user_teams = None
    active_team = None 
    active_team_player_ids = set()
    team_player_statuses_map = {}
    on_team_player_ids = set()
    draft_picks_map = {}
    team_coverage_string = "No active team or no players on team."


    if request.user.is_authenticated:
        user_teams = Team.objects.filter(creator=request.user)
        active_team = user_teams.filter(is_active=True).first()
        if active_team:
            team_player_entries = TeamPlayer.objects.filter(team=active_team).select_related('team')
            active_team_player_ids = set(str(tp.player_id) for tp in team_player_entries)
            team_player_statuses_map = {tp.player_id: tp.status for tp in team_player_entries}
            on_team_player_ids = set(str(tp.player_id) for tp in team_player_entries if tp.status == 'ON_TEAM')
            team_coverage_string = _get_team_position_coverage(active_team, fantasy_positions_map)


    final_column_display_names['Draft_Pos'] = 'Draft Pos'

    # Reorder columns to put Draft_Pos first (if active team exists)
    if active_team:
        ordered_columns = {}
        # Add Draft_Pos first
        if 'Draft_Pos' in final_column_display_names:
            ordered_columns['Draft_Pos'] = final_column_display_names['Draft_Pos']
        # Add all other columns
        for key, value in final_column_display_names.items():
            if key != 'Draft_Pos':
                ordered_columns[key] = value
        final_column_display_names = ordered_columns

    # Generate punt categories string
    punt_categories_string = _get_punt_categories_string(request.session)

    initial_data_list = []
    for record in ratings_df.to_dict('records'):
        processed_record = {}
        player_id_val = record.get('Player_ID')
        player_id_str = None
        if player_id_val is not None:
            try:
                player_id_str = str(int(float(player_id_val)))
            except (ValueError, TypeError):
                pass
        processed_record['Player_ID'] = player_id_str

        is_on_team_flag = player_id_str in active_team_player_ids if player_id_str else False
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

        # Add draft position - ensure it's an integer
        if 'Draft_Pos' in record and record['Draft_Pos'] is not None:
            try:
                processed_record['Draft_Pos'] = int(float(record['Draft_Pos']))
            except (ValueError, TypeError):
                processed_record['Draft_Pos'] = None
        else:
            processed_record['Draft_Pos'] = None

        fantasy_positions_str = "N/A" 
        if player_id_val is not None:
            try:
                player_id_int = int(float(player_id_val)) 
                positions_list = fantasy_positions_map.get(player_id_int, [])
                if positions_list:
                    fantasy_positions_str = ", ".join(positions_list) 
            except (ValueError, TypeError):
                logger.warning(f"Could not process Player_ID '{player_id_val}' for fantasy position lookup in show_ratings.", exc_info=True)
        processed_record['POS'] = fantasy_positions_str
        
        for col_key in final_column_display_names.keys():
            if col_key not in processed_record: 
                if col_key in record:
                    processed_record[col_key] = record[col_key]
        initial_data_list.append(processed_record)
    
    if current_status_filter != 'ALL':
        if current_status_filter == 'Injured':
            # Filter for injured players using session data
            injured_player_ids = [str(pid) for pid in request.session.get('injured_player_ids', [])]
            initial_data_list = [
                record for record in initial_data_list
                if str(record.get('Player_ID', '')) in injured_player_ids
            ]
        elif current_status_filter == 'Healthy':
            # Filter for healthy players using session data
            injured_player_ids = [str(pid) for pid in request.session.get('injured_player_ids', [])]
            initial_data_list = [
                record for record in initial_data_list
                if str(record.get('Player_ID', '')) not in injured_player_ids
            ]
        else:
            initial_data_list = [
                record for record in initial_data_list
                if record.get('Status') == current_status_filter
            ]

    styled_ratings_data = _apply_styles_to_data(
        initial_data_list, 
        STYLED_COLUMNS, 
        enable_heatmap=request.session.get('enable_heatmap', False),
        enable_tier_colors=request.session.get('enable_tier_colors', False))

    (styled_team_averages_dict, num_players_on_team_calc) = _get_styled_team_averages_and_count(
        ratings_data_module.ratings.copy(), active_team, final_column_display_names
    )

    if active_team and num_players_on_team_calc > 0 and styled_team_averages_dict:
        team_average_row_for_table = {}
        team_average_row_for_table['Name'] = {'value': active_team.name, 'css_class': None}
        team_average_row_for_table['Player_ID'] = {'value': 'TEAM_AVERAGE_ROW', 'css_class': None} 
        team_average_row_for_table['Status'] = {
            'value': f"Team Avg ({num_players_on_team_calc} Player{'s' if num_players_on_team_calc != 1 else ''})",
            'css_class': None 
        }
        team_average_row_for_table['Draft_Pos'] = {'value': '', 'css_class': None}
        # For point 2: Ensure POS cell is empty for team average row
        if 'POS' in final_column_display_names:
            team_average_row_for_table['POS'] = {'value': '', 'css_class': None}

        for col_key, styled_value_dict in styled_team_averages_dict.items():
            team_average_row_for_table[col_key] = styled_value_dict
        
        # Fill any remaining columns that weren't part of averages or explicitly set
        for col_key in final_column_display_names.keys():
            if col_key not in team_average_row_for_table:
                team_average_row_for_table[col_key] = {'value': "N/A", 'css_class': None}

        styled_ratings_data.insert(0, team_average_row_for_table)

    # Read highlighted players from session (session-persistent per user)
    highlighted_player_ids = [str(pid) for pid in request.session.get('highlighted_player_ids', [])]
    
    # Read injured players from session (session-persistent per user)
    injured_player_ids = [str(pid) for pid in request.session.get('injured_player_ids', [])]
    
    # Read categories visibility from session
    show_categories = request.session.get('show_categories', True)
    
    # Define which columns are category columns (can be toggled) - only statistical categories, not ratings
    category_columns = [col for col in final_column_display_names.keys() 
                      if col not in ['Name', 'POS', 'Status', 'Draft_Pos', 'Player_ID', 'Total_Rating', 'Total_Available_Rating'] 
                      and not col.endswith(('_Rating', '_Available_Rating', '_Combined_Rating'))]

    context = {
        'ratings': styled_ratings_data,
        'column_display_names': final_column_display_names,
        'teams': user_teams if request.user.is_authenticated else None, 
        'active_team': active_team,  
        'status_filter_choices': STATUS_FILTER_CHOICES,
        'current_status_filter': current_status_filter,
        'sort_by': active_sort_column,
        'sort_direction': active_sort_direction,
        'team_coverage_string': team_coverage_string, # Add to context
        'punt_categories_string': punt_categories_string, # Add punt categories to context
        'enable_heatmap': request.session.get('enable_heatmap', False),
        'enable_tier_colors': request.session.get('enable_tier_colors', False),
        'highlighted_player_ids': highlighted_player_ids,
        'injured_player_ids': injured_player_ids,
        'show_categories': show_categories,
        'category_columns': category_columns,
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
    
    # If team_ratings_df is empty but there are players (e.g., players with no stats), style with None
    if team_ratings_df.empty and num_players_on_team > 0: 
        return _style_single_row_data({col: None for col in cols_for_averaging}, cols_for_averaging), num_players_on_team

    team_averages_raw = {col: team_ratings_df[col].mean() if col in team_ratings_df else None for col in cols_for_averaging}
    # For point 4: Modify the call to _style_single_row_data to use STYLED_COLUMNS
    # This ensures only base stat columns get color-coding for the team average row.
    styled_team_averages = _style_single_row_data(team_averages_raw, STYLED_COLUMNS)
    return styled_team_averages, num_players_on_team

def _get_value_based_css_class(value, is_rating_column=False):
    """Determines CSS class based on fixed value thresholds.
    Assumes value is on a 0-100 scale where higher is better.
    If is_rating_column=True, uses the new rating color scheme."""
    if value is None or not isinstance(value, (int, float)):
        return None

    if is_rating_column:
        # New rating color scheme
        if value < 50: # Light Grey
            return 'bg-light-grey'
        elif value < 55: # Grey
            return 'bg-grey'
        elif value < 60: # Dark Grey
            return 'bg-dark-grey'
        elif value < 65: # Green
            return 'bg-green'
        elif value < 70: # Blue
            return 'bg-blue'
        elif value < 75: # Yellow
            return 'bg-yellow'
        elif value < 85: # Orange
            return 'bg-orange'
        elif value < 90: # Pink
            return 'bg-pink'
        else: # 90+
            return 'bg-purple'
    else:
        # Original heatmap colors for statistical categories
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


def _apply_styles_to_data(data_list_of_dicts: list, columns_to_style: list, enable_heatmap=False, enable_tier_colors=False):
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
            if enable_heatmap and col_actual_name in columns_to_style:
                value_for_styling = raw_value
                css_class = _get_value_based_css_class(value_for_styling)
            elif enable_tier_colors and col_actual_name.endswith(('_Rating', '_Available_Rating', '_Combined_Rating')):
                # Apply rating heatmap to rating columns
                value_for_styling = raw_value
                css_class = _get_value_based_css_class(value_for_styling, is_rating_column=True)
            
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
    active_team = teams.filter(is_active=True).first()

    team_roster_data = []
    team_averages = None
    team_coverage_string = "No active team selected."
    num_players_on_team = 0
    final_column_display_names = _get_final_column_display_names(request.session, ratings_data_module.ratings.columns)

    if active_team:
        on_team_player_ids = list(TeamPlayer.objects.filter(team=active_team, status='ON_TEAM').values_list('player_id', flat=True))
        num_players_on_team = len(on_team_player_ids)

        ratings_df = ratings_data_module.ratings.copy()
        fantasy_positions_map = _load_fantasy_positions_data()

        if num_players_on_team > 0:
            team_roster_df = ratings_df[ratings_df['Player_ID'].isin(on_team_player_ids)]
            roster_list = []
            for record in team_roster_df.to_dict('records'):
                player_id_val = record.get('Player_ID')
                try:
                    pid_int = int(float(player_id_val))
                    positions = fantasy_positions_map.get(pid_int, [])
                    record['POS'] = ", ".join(positions) if positions else "N/A"
                except (ValueError, TypeError):
                    record['POS'] = "N/A"
                roster_list.append(record)
            
            team_roster_data = _apply_styles_to_data(
                roster_list, 
                STYLED_COLUMNS, 
                enable_heatmap=request.session.get('enable_heatmap', False),
                enable_tier_colors=request.session.get('enable_tier_colors', False))
            team_averages, _ = _get_styled_team_averages_and_count(ratings_df, active_team, final_column_display_names)

        team_coverage_string = _get_team_position_coverage(active_team, fantasy_positions_map)

    context = {
        'teams': teams,
        'active_team': active_team,
        'team_roster': team_roster_data,
        'team_averages': team_averages,
        'team_coverage_string': team_coverage_string,
        'num_players_on_team': num_players_on_team,
        'column_display_names': final_column_display_names,
    }
    return render(request, 'fantasy_nba/team.html', context)

@login_required
def delete_team(request, team_id):
    """
    Handles the deletion of a team.
    """
    team_to_delete = get_object_or_404(Team, team_id=team_id, creator=request.user)

    if team_to_delete.is_active:
        messages.error(request, "You cannot delete an active team. Please activate another team first.")
        return redirect('team')

    if request.method == 'POST':
        team_name = team_to_delete.name
        team_to_delete.delete()
        messages.success(request, f"Team '{team_name}' has been deleted.")
    
    return redirect('team')

@login_required
def edit_team(request, team_id):
    """
    Handles editing a team's name.
    """
    team_to_edit = get_object_or_404(Team, team_id=team_id, creator=request.user)
    
    if request.method == 'POST':
        form = TeamNameForm(request.POST, instance=team_to_edit)
        if form.is_valid():
            form.save()
            messages.success(request, f"Team name updated to '{team_to_edit.name}'.")
            return redirect('team')
    else:
        form = TeamNameForm(instance=team_to_edit)

    return render(request, 'fantasy_nba/edit_team.html', {'form': form, 'team': team_to_edit})

@login_required
def activate_team(request, team_id):
    """
    Handles activating a team.
    """
    team_to_activate = get_object_or_404(Team, team_id=team_id, creator=request.user)
    
    # Deactivate all other teams
    Team.objects.filter(creator=request.user).update(is_active=False)
    
    # Activate the selected team
    team_to_activate.is_active = True
    team_to_activate.save()
    
    messages.success(request, f"Team '{team_to_activate.name}' is now active.")
    return redirect('team')


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
        recalculate_averages_and_coverage = (player_was_on_team != player_is_now_on_team) or (created and player_is_now_on_team)


        if recalculate_averages_and_coverage:
            ratings_df_copy = ratings_data_module.ratings.copy()
            current_final_column_names = _get_final_column_display_names(request.session, ratings_data_module.ratings.columns)
            
            styled_avg_data, num_on_team = _get_styled_team_averages_and_count(
                ratings_df_copy, active_team, current_final_column_names
            )
            json_response_data['team_averages_data'] = styled_avg_data 
            json_response_data['num_players_on_team'] = num_on_team

            # Recalculate and add position coverage
            fantasy_positions_map = _load_fantasy_positions_data()
            team_coverage_string = _get_team_position_coverage(active_team, fantasy_positions_map)
            json_response_data['team_coverage_string'] = team_coverage_string


        return JsonResponse(json_response_data)

    json_response_data['error'] = 'Invalid request method.'
    return JsonResponse(json_response_data, status=405)

@login_required
def toggle_highlight(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

    player_id = request.POST.get('player_id')
    if not player_id:
        return JsonResponse({'success': False, 'error': 'Missing player_id.'}, status=400)

    # Use session to store highlighted players as a set-like list of strings
    highlighted = set(str(pid) for pid in request.session.get('highlighted_player_ids', []))
    player_id_str = str(player_id)
    if player_id_str in highlighted:
        highlighted.remove(player_id_str)
        highlighted_now = False
    else:
        highlighted.add(player_id_str)
        highlighted_now = True

    request.session['highlighted_player_ids'] = list(highlighted)
    request.session.modified = True

    return JsonResponse({'success': True, 'highlighted': highlighted_now})

@login_required
def toggle_injured(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

    player_id = request.POST.get('player_id')
    if not player_id:
        return JsonResponse({'success': False, 'error': 'Missing player_id.'}, status=400)

    # Use session to store injured players as a set-like list of strings
    injured = set(str(pid) for pid in request.session.get('injured_player_ids', []))
    player_id_str = str(player_id)
    if player_id_str in injured:
        injured.remove(player_id_str)
        injured_now = False
    else:
        injured.add(player_id_str)
        injured_now = True

    request.session['injured_player_ids'] = list(injured)
    request.session.modified = True

    return JsonResponse({'success': True, 'injured': injured_now})

@login_required
def set_draft_order(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

    active_team = Team.objects.filter(creator=request.user, is_active=True).first()
    if not active_team:
        return JsonResponse({'success': False, 'error': 'No active team found.'}, status=400)

    # Get the visible player order from the request
    player_order = request.POST.getlist('player_order[]')
    if not player_order:
        return JsonResponse({'success': False, 'error': 'No player order provided.'}, status=400)

    try:
        with transaction.atomic():
            # Clear existing draft picks for this team
            DraftPick.objects.filter(team=active_team).delete()
            
            # Create new draft picks based on visible order
            draft_picks_to_create = []
            for i, player_id_str in enumerate(player_order, 1):
                if player_id_str and player_id_str != 'TEAM_AVERAGE_ROW':
                    try:
                        # Validate player_id exists in ratings
                        player_id_int = int(float(player_id_str))
                        # Check if player exists in ratings data
                        ratings_df = ratings_data_module.ratings.copy()
                        if player_id_int in ratings_df['Player_ID'].values:
                            draft_picks_to_create.append(
                                DraftPick(team=active_team, player_id=str(player_id_int), pick_number=int(i))
                            )
                    except (ValueError, TypeError):
                        logger.warning(f"Could not process Player_ID '{player_id_str}' for draft order.")
                        continue
            
            if draft_picks_to_create:
                DraftPick.objects.bulk_create(draft_picks_to_create)
                
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': True, 'message': f'Draft order set for {len(draft_picks_to_create)} players.'})

@login_required
def toggle_categories(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

    # Toggle categories visibility
    current_show_categories = request.session.get('show_categories', True)
    new_show_categories = not current_show_categories
    request.session['show_categories'] = new_show_categories
    request.session.modified = True

    return JsonResponse({'success': True, 'show_categories': new_show_categories})

@login_required
def move_draft_pick(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)

    active_team = Team.objects.filter(creator=request.user, is_active=True).first()
    if not active_team:
        return JsonResponse({'success': False, 'error': 'No active team found.'}, status=400)

    player_id = request.POST.get('player_id')
    direction = request.POST.get('direction')
    set_position = request.POST.get('set_position')

    if not player_id:
        return JsonResponse({'success': False, 'error': 'Missing player_id.'}, status=400)

    # Handle direct position setting
    if set_position is not None:
        try:
            target_pick_number = int(set_position)
            if target_pick_number < 1:
                return JsonResponse({'success': False, 'error': 'Position must be at least 1.'}, status=400)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid position number.'}, status=400)
    elif not direction or direction not in ['up', 'down']:
        return JsonResponse({'success': False, 'error': 'Invalid parameters.'}, status=400)

    try:
        with transaction.atomic():
            # Get the pick for the current player
            current_pick = DraftPick.objects.select_for_update().get(team=active_team, player_id=player_id)
            current_pick_number = current_pick.pick_number

            # Determine the target pick number
            if set_position is not None:
                target_pick_number = int(set_position)
            elif direction == 'up':
                target_pick_number = current_pick_number - 1
                if target_pick_number < 1:
                    return JsonResponse({'success': False, 'error': 'Already at the top.'}, status=400)
            else: # direction == 'down'
                target_pick_number = current_pick_number + 1

            # Get the pick to swap with
            other_pick = DraftPick.objects.select_for_update().get(team=active_team, pick_number=target_pick_number)

            # To avoid a UNIQUE constraint violation, we perform a three-step swap.
            # 1. Temporarily move the 'other' pick to a non-existent pick number.
            #    A value of 0 or a negative number is safe as pick numbers are positive.
            placeholder_pick_number = 0
            other_pick.pick_number = placeholder_pick_number
            other_pick.save()

            # 2. Now that the original pick number of 'other_pick' is free, move 'current_pick' to it.
            current_pick.pick_number = target_pick_number
            current_pick.save()

            # 3. Finally, update 'other_pick' from the placeholder to the original pick number of 'current_pick'.
            other_pick.pick_number = current_pick_number
            other_pick.save()
    except DraftPick.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Draft pick not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': True, 'message': 'Draft position updated.'})

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
    messages.info(request, "You have been successfully logged out.")
    return redirect('login_register')
