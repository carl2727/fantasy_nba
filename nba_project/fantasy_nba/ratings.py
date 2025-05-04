# fantasy_nba/ratings.py
import pandas as pd
from .games_played import calculate_player_availability_score
from .helpers import normalize
from .weeks import calculate_games_per_week

# Define columns
categories = ['FGN', 'FTN', 'PTS', 'FG3M', 'REB', 'BLK', 'STL', 'AST', 'TOV']
rating_columns = ['FGN_RT', 'FTN_RT', 'FG3M_RT', 'PTS_RT', 'REB_RT', 'AST_RT', 'BLK_RT', 'STL_RT','TOV_RT']

# Load data
game_stats_file = "data/all_player_game_stats_2024_2025.csv"
players_file = "data/nba_players.csv"
game_stats = pd.read_csv(game_stats_file)
players = pd.read_csv(players_file)

# Preprocess data
game_stats.drop(columns=['Game_ID', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'VIDEO_AVAILABLE'], inplace=True)
numeric_columns = game_stats.select_dtypes(include='number').columns
game_stats = game_stats.groupby('Player_ID', as_index=False)[numeric_columns].mean().reset_index()
player_availability_score = calculate_player_availability_score()

stats = pd.merge(
    game_stats,
    players[['PERSON_ID', 'DISPLAY_FIRST_LAST', 'TEAM_ID']],
    left_on='Player_ID',
    right_on='PERSON_ID',
    how='left'
)

stats.rename(columns={'DISPLAY_FIRST_LAST': 'Name'}, inplace=True)
stats.drop(columns=['PERSON_ID'])

def calc_fgn_ftn(stats):
    stats['FGPM'] = stats['FGM'] - (stats['FGA'] - stats['FGM'])
    stats['FGN'] = stats['FGPM'] - stats['FGPM'].min()
    stats['FTPM'] = stats['FTM'] - (stats['FTA'] - stats['FTM'])
    stats['FTN'] = stats['FTPM'] - stats['FTPM'].min()
    
    # Debug: Print the DataFrame after adding the columns
    print("Stats DataFrame inside calc_fgn_ftn:")
    print(stats.head())
    return stats

# Calculate ratings 
stats = calc_fgn_ftn(stats)
for cat in categories:
    stats[cat + '_RT'] = normalize(stats[cat])

stats['TOV_RT'] = stats['TOV_RT'] * (-1)

ratings = stats[['Name', 'Player_ID', 'TEAM_ID', 'FGN_RT', 'FTN_RT', 'FG3M_RT', 'PTS_RT', 'REB_RT', 'AST_RT', 'BLK_RT', 'STL_RT', 'TOV_RT']]

ratings.loc[:, 'Total_Rating'] = ratings[rating_columns].sum(axis=1)
ratings.loc[:, 'Total_Rating'] = normalize(ratings['Total_Rating'])

ratings.loc[:, 'Total_Available_Rating'] = ratings.apply(
    lambda row: row['Total_Rating'] * player_availability_score.get(row['Player_ID'], 0),
    axis=1
)
ratings.loc[:, 'Total_Available_Rating'] = normalize(ratings['Total_Available_Rating'])

# Weekly ratings
schedule_file = "data/regular_season_schedule_2024-2025.csv"
games_per_week, max_games_per_week = calculate_games_per_week(schedule_file)

weekly_ratings = ratings[['Player_ID', 'Name', 'TEAM_ID', 'Total_Rating', 'Total_Available_Rating']]
for player in weekly_ratings['Player_ID']:
    team_id = weekly_ratings.loc[weekly_ratings['Player_ID'] == player, 'TEAM_ID'].values[0]
    if team_id not in games_per_week:
        continue
    for week in games_per_week[team_id].keys():
        week_rating = (games_per_week[team_id][week] / max_games_per_week[week])
        col = 'Rating_Week_' + str(week)
        if col not in weekly_ratings.columns:
            weekly_ratings.loc[:, col] = weekly_ratings['Total_Rating'] * week_rating
    
for col in weekly_ratings.columns:
    if col.startswith('Rating_Week_'):
        weekly_ratings.loc[:, col] = normalize(weekly_ratings[col])
        
# Punt Ratings
def punt_rating(punt_cats):
    cats = rating_columns - punt_cats
    print(f" categories: {cats}")




# Selecting relevant players
ratings.sort_values('Total_Rating', ascending=False, inplace=True)
player_selection = ratings['Player_ID'].head(200).tolist()

# Save data
weekly_ratings.sort_values('Total_Available_Rating', ascending=False, inplace=True)
weekly_ratings.to_csv('data/weekly_ratings.csv', index=False)
ratings.sort_values('Total_Available_Rating', ascending=False, inplace=True)
ratings.to_csv('data/ratings.csv', index=False)