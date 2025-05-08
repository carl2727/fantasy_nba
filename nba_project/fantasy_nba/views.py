# views.py
from django import forms
from django.shortcuts import render, redirect
from django.http import HttpRequest
from . import ratings
import pandas as pd

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
    'Total_Available_Rating': 'Performance Rating'
}

NON_STYLED_COLUMNS = ['Name', 'Player_ID', 'TEAM_ID']

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
    ratings_df = ratings.ratings.copy()
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
        if punt_perf_col_actual_name_candidate in ratings.ratings.columns:
            punt_perf_col_actual_name = punt_perf_col_actual_name_candidate
            punt_perf_col_display_name = f"Performance Rating (Punt {punted_cats_formatted_for_display})"
            if punt_perf_col_actual_name not in columns_to_extract:
                columns_to_extract.append(punt_perf_col_actual_name)

        # Check and prepare "Overall (Punt...)" column (newly added)
        if punt_overall_col_actual_name_candidate in ratings.ratings.columns:
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

    # Prepare data for styling
    numeric_columns_for_styling = [col for col in columns_to_extract if col not in NON_STYLED_COLUMNS]
    thresholds = _calculate_percentile_thresholds(ratings_df, numeric_columns_for_styling)
    
    # Create the initial list of dictionaries with only the columns to display
    initial_data_list = []
    for record in ratings_df.to_dict('records'):
        initial_data_list.append({col: record.get(col) for col in columns_to_extract})
        
    styled_ratings_data = _apply_styles_to_data(initial_data_list, thresholds, numeric_columns_for_styling)
    
    context = {
        'ratings': styled_ratings_data,
        'column_display_names': final_column_display_names,
    }
    return render(request, 'fantasy_nba/show_ratings.html', context)

def sort_ratings(request: HttpRequest):
    sort_by = request.GET.get('sort_by')
    ratings_df = ratings.ratings.copy()

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

        if punt_perf_col_actual_name_candidate in ratings.ratings.columns:
            punt_perf_col_actual_name = punt_perf_col_actual_name_candidate
            punt_perf_col_display_name = f"Performance Rating (Punt {punted_cats_formatted_for_display})"
            if punt_perf_col_actual_name not in columns_to_extract:
                columns_to_extract.append(punt_perf_col_actual_name)

        if punt_overall_col_actual_name_candidate in ratings.ratings.columns:
            punt_overall_col_actual_name = punt_overall_col_actual_name_candidate
            punt_overall_col_display_name = f"Overall Rating (Punt {punted_cats_formatted_for_display})"
            if punt_overall_col_actual_name not in columns_to_extract:
                columns_to_extract.append(punt_overall_col_actual_name)

    final_column_display_names = COLUMN_DISPLAY_NAMES.copy()
    if punt_perf_col_actual_name and punt_perf_col_display_name:
        final_column_display_names[punt_perf_col_actual_name] = punt_perf_col_display_name
    if punt_overall_col_actual_name and punt_overall_col_display_name:
        final_column_display_names[punt_overall_col_actual_name] = punt_overall_col_display_name

    # Sort the DataFrame
    if sort_by in ratings_df.columns:
        sorted_ratings_df = ratings_df.sort_values(by=sort_by, ascending=ascending_flag)
    else:
        sorted_ratings_df = ratings_df # No sort or use default if sort_by is invalid

    # Prepare data for styling from the (potentially sorted) DataFrame
    numeric_columns_for_styling = [col for col in columns_to_extract if col not in NON_STYLED_COLUMNS]
    # Calculate thresholds based on the original, unsorted DataFrame to ensure consistency
    # or on sorted_ratings_df if percentiles should reflect the current view's sort order (usually not desired for global percentiles).
    # Using ratings.ratings.copy() ensures global percentiles.
    thresholds = _calculate_percentile_thresholds(ratings.ratings.copy(), numeric_columns_for_styling) 

    initial_data_list_sorted = []
    for record in sorted_ratings_df.to_dict('records'): # Use the sorted DataFrame here
        initial_data_list_sorted.append({col: record.get(col) for col in columns_to_extract})

    styled_sorted_ratings_data = _apply_styles_to_data(initial_data_list_sorted, thresholds, numeric_columns_for_styling)

    context = {
        'ratings': styled_sorted_ratings_data,
        'column_display_names': final_column_display_names,
        'sort_by': request.session.get('sort_by'),
        'sort_direction': request.session.get('sort_direction'),
    }
    return render(request, 'fantasy_nba/show_ratings.html', context)

def _get_percentile_css_class(value, thresholds):
    """Determines CSS class based on value and percentile thresholds."""
    if value is None or not isinstance(value, (int, float)):
        return None # Cannot style non-numeric or None values
    
    p10 = thresholds.get('p10')
    p20 = thresholds.get('p20')
    p80 = thresholds.get('p80')
    p90 = thresholds.get('p90')

    if p90 is not None and value >= p90:
        return 'bg-green'
    if p80 is not None and value >= p80: # Implicitly < p90 if p90 was not None or this condition wouldn't be met
        return 'bg-light-green'
    
    if p10 is not None and value <= p10:
        return 'bg-red'
    if p20 is not None and value <= p20: # Implicitly > p10 if p10 was not None or this condition wouldn't be met
        return 'bg-light-red'
        
    return None # Default, no specific color for values in the middle range

def _calculate_percentile_thresholds(ratings_df: pd.DataFrame, numeric_columns: list):
    """Calculates 10th, 20th, 80th, 90th percentiles for given numeric columns."""
    percentile_thresholds = {}
    for col_name in numeric_columns:
        if col_name in ratings_df.columns and pd.api.types.is_numeric_dtype(ratings_df[col_name]):
            # Ensure the column has data to prevent errors with quantile on empty series
            if not ratings_df[col_name].dropna().empty:
                quantiles = ratings_df[col_name].quantile([0.1, 0.2, 0.8, 0.9])
                percentile_thresholds[col_name] = {
                    'p10': quantiles.iloc[0] if not pd.isna(quantiles.iloc[0]) else None,
                    'p20': quantiles.iloc[1] if not pd.isna(quantiles.iloc[1]) else None,
                    'p80': quantiles.iloc[2] if not pd.isna(quantiles.iloc[2]) else None,
                    'p90': quantiles.iloc[3] if not pd.isna(quantiles.iloc[3]) else None,
                }
            else: # Column is empty or all NaN
                percentile_thresholds[col_name] = {} 
        else: # Column not in DataFrame or not numeric
            percentile_thresholds[col_name] = {} 
    return percentile_thresholds

def _apply_styles_to_data(data_list_of_dicts: list, percentile_thresholds: dict, columns_to_style: list):
    """Wraps cell values with {'value': ..., 'css_class': ...} structure."""
    styled_data = []
    for player_row_dict in data_list_of_dicts:
        styled_player_row = {}
        for col_actual_name, value in player_row_dict.items():
            css_class = None
            if col_actual_name in columns_to_style:
                thresholds_for_col = percentile_thresholds.get(col_actual_name, {})
                if thresholds_for_col: # Check if thresholds were calculated
                    css_class = _get_percentile_css_class(value, thresholds_for_col)
            styled_player_row[col_actual_name] = {'value': value, 'css_class': css_class}
        styled_data.append(styled_player_row)
    return styled_data

def blog(request):
    return render(request, 'fantasy_nba/blog.html')