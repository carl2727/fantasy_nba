# views.py
from django.shortcuts import render
from django.http import HttpRequest
from . import ratings

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

def show_ratings(request: HttpRequest):
    ratings_df = ratings.ratings.copy()
    columns_to_display = list(COLUMN_DISPLAY_NAMES.keys())
    data_to_display = [{col: row[col] for col in columns_to_display if col in row} for row in ratings_df.to_dict('records')]
    context = {
        'ratings': data_to_display,
        'column_display_names': COLUMN_DISPLAY_NAMES,
    }
    return render(request, 'fantasy_nba/show_ratings.html', context)

def sort_ratings(request: HttpRequest):
    sort_by = request.GET.get('sort_by')
    ratings_df = ratings.ratings.copy()
    sort_direction = request.GET.get('sort_direction')
    current_sort_by = request.session.get('sort_by')
    current_sort_direction = request.session.get('sort_direction')

    reverse = False
    if sort_by == current_sort_by and current_sort_direction == 'asc':
        reverse = True
        request.session['sort_direction'] = 'desc'
    else:
        request.session['sort_by'] = sort_by
        request.session['sort_direction'] = 'asc'

    columns_to_display = list(COLUMN_DISPLAY_NAMES.keys())

    if sort_by in ratings_df.columns:
        sorted_ratings_df = ratings_df.sort_values(by=sort_by, ascending=not reverse)
        sorted_ratings = [
            {col: row[col] for col in columns_to_display if col in row}
            for row in sorted_ratings_df.to_dict('records')
        ]
    else:
        sorted_ratings = [
            {col: row[col] for col in columns_to_display if col in row}
            for row in ratings_df.to_dict('records')
        ]

    context = {
        'ratings': sorted_ratings,
        'column_display_names': COLUMN_DISPLAY_NAMES,
        'sort_by': sort_by,
        'sort_direction': request.session.get('sort_direction'),
    }
    return render(request, 'fantasy_nba/show_ratings.html', context)

def blog(request):
    return render(request, 'fantasy_nba/blog.html')