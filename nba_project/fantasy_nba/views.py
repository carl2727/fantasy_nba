from django.shortcuts import render
from . import ratings

def show_ratings(request):
    ratings_df = ratings.ratings.copy()
    column_display_names = {
        'Name': 'Name',
        'PTS_RT': 'PTS',
        'REB_RT': 'REB',
        'AST_RT': 'AST',
        'FG%_RT': 'FG%',
        'FT%_RT': 'FT%',
        'FG3M_RT': '3PTM',
        'BLK_RT': 'BLK',
        'TOV_RT': 'TOV',
        'Total_Rating': 'Overall Rating',
        'Total_Available_Rating': 'Performance Rating'
    }
    columns_to_display = list(column_display_names.keys())
    data_to_display = [{col: row[col] for col in columns_to_display if col in row} for row in ratings_df.to_dict('records')]
    context = {
        'ratings': data_to_display,
        'columns': columns_to_display,
        'column_display_names': column_display_names
    }
    return render(request, 'fantasy_nba/show_ratings.html', context)

def sort_ratings(request):
    sort_by = request.GET.get('sort_by')
    ratings_df = ratings.ratings

    if sort_by in ratings_df.columns:
        sorted_ratings = ratings_df.sort_values(by=sort_by).to_dict('records')
        columns = ratings_df.columns.tolist()
        return render(request, 'fantasy_nba/ratings_table_rows.html', {'ratings': sorted_ratings, 'columns': columns})
    else:
        return render(request, 'fantasy_nba/ratings_table_rows.html', {'ratings': ratings_df.to_dict('records'), 'columns': ratings_df.columns.tolist()})
    
def blog(request):
    return render(request, 'fantasy_nba/blog.html')