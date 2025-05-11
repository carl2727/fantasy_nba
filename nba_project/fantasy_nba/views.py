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

   
    # Create the initial list of dictionaries with only the columns to display
    initial_data_list = []
    for record in ratings_df.to_dict('records'):
        initial_data_list.append({col: record.get(col) for col in columns_to_extract})
    
    styled_ratings_data = _apply_styles_to_data(initial_data_list, STYLED_COLUMNS)
    
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

    initial_data_list_sorted = []
    for record in sorted_ratings_df.to_dict('records'): # Use the sorted DataFrame here
        initial_data_list_sorted.append({col: record.get(col) for col in columns_to_extract})
    
    styled_sorted_ratings_data = _apply_styles_to_data(initial_data_list_sorted, STYLED_COLUMNS)

    context = {
        'ratings': styled_sorted_ratings_data,
        'column_display_names': final_column_display_names,
        'sort_by': request.session.get('sort_by'),
        'sort_direction': request.session.get('sort_direction'),
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
    """Wraps cell values with {'value': ..., 'css_class': ...} structure."""
    styled_data = []
    for player_row_dict in data_list_of_dicts:
        styled_player_row = {}
        for col_actual_name, value in player_row_dict.items():
            css_class = None
            if col_actual_name in columns_to_style:
                value_for_styling = value             
                css_class = _get_value_based_css_class(value_for_styling)
            styled_player_row[col_actual_name] = {'value': value, 'css_class': css_class}
        styled_data.append(styled_player_row)
    return styled_data

def blog(request):
    return render(request, 'fantasy_nba/blog.html')