# fantasy_nba/ratings.py
import pandas as pd
from .games_played import calculate_player_availability_score
from .helpers import normalize
from .weeks import calculate_games_per_week
import itertools
import os
from datetime import datetime

CURRENT_SEASON = "2025-2026"
PREVIOUS_SEASON = "2024-2025"
TOTAL_GAMES_PER_SEASON = 82

# Define columns
categories = ['FGN', 'FTN', 'PTS', 'FG3M', 'REB', 'BLK', 'STL', 'AST', 'TOV']
rating_columns = ['FGN_RT', 'FTN_RT', 'FG3M_RT', 'PTS_RT', 'REB_RT', 'AST_RT', 'BLK_RT', 'STL_RT','TOV_RT']

def extract_team_from_matchup(matchup):
    """
    Extrahiert das Team-Kürzel aus dem MATCHUP String.
    Format: "TEAM @ OPP" oder "TEAM vs. OPP"
    Gibt das erste Team zurück (das spielende Team).
    """
    if pd.isna(matchup):
        return None
    parts = matchup.split()
    return parts[0] if parts else None

def calculate_games_played_per_team(current_season_stats):
    """
    Berechnet die Anzahl der gespielten Spiele pro Team in der aktuellen Saison.
    """
    if current_season_stats.empty:
        return {}
    
    # Extrahiere Team aus MATCHUP Spalte
    if 'MATCHUP' not in current_season_stats.columns:
        return {}
    
    current_season_stats = current_season_stats.copy()
    current_season_stats['TEAM_ID'] = current_season_stats['MATCHUP'].apply(extract_team_from_matchup)
    
    # Zähle einzigartige Spiele pro Team
    games_played = {}
    for team_id in current_season_stats['TEAM_ID'].dropna().unique():
        team_games = current_season_stats[current_season_stats['TEAM_ID'] == team_id]
        unique_games = team_games['Game_ID'].nunique()
        games_played[team_id] = unique_games
    
    return games_played

def calculate_weighting_factor(games_played, team_id):
    """
    Berechnet den Gewichtungsfaktor basierend auf der Anzahl der gespielten Spiele.
    """
    if team_id not in games_played:
        return 1.0  # Falls keine Daten verfügbar, verwende nur vergangene Saison
    
    games = games_played[team_id]
    if games == 0:
        return 1.0  # Keine Spiele gespielt, verwende nur vergangene Saison
    
    # Gewichtungsfaktor: (82 - gespielte Spiele) / 82
    weighting_factor = (TOTAL_GAMES_PER_SEASON - games) / TOTAL_GAMES_PER_SEASON
    return max(0.0, weighting_factor)  # Mindestens 0.0

# Load data
game_stats_files = [
    "data/all_player_game_stats_2025_2026.csv"
]
players_file = "data/nba_players.csv"

# Load and combine game stats from multiple seasons
game_stats_list = []
current_season_stats = None
previous_season_stats = None

for file_path in game_stats_files:
    try:
        season_stats = pd.read_csv(file_path)
        # Add season identifier
        if "2025_2026" in file_path:
            season_stats['Season'] = CURRENT_SEASON
            current_season_stats = season_stats
        game_stats_list.append(season_stats)
        print(f"Successfully loaded {file_path}")
    except FileNotFoundError:
        print(f"File not found: {file_path} - skipping")
    except Exception as e:
        print(f"Error loading {file_path}: {e} - skipping")

if not game_stats_list:
    raise FileNotFoundError("No game stats files could be loaded")

# Combine all seasons for initial processing
game_stats = pd.concat(game_stats_list, ignore_index=True)
players = pd.read_csv(players_file)

# Preprocess data
# Ensure Player_ID is numeric, coercing errors to NaN.
# Then drop rows where Player_ID could not be converted (is NaN).
# Finally, convert the valid Player_IDs to integers.
game_stats['Player_ID'] = pd.to_numeric(game_stats['Player_ID'], errors='coerce')
game_stats.dropna(subset=['Player_ID'], inplace=True)
game_stats['Player_ID'] = game_stats['Player_ID'].astype(int)

# Clean PERSON_ID in the players DataFrame
players['PERSON_ID'] = pd.to_numeric(players['PERSON_ID'], errors='coerce')
players.dropna(subset=['PERSON_ID'], inplace=True)
players['PERSON_ID'] = players['PERSON_ID'].astype(int)

# Drop unnecessary columns, ignoring errors if some are already missing
columns_to_drop_from_game_stats = ['Game_ID', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'VIDEO_AVAILABLE']
game_stats.drop(columns=[col for col in columns_to_drop_from_game_stats if col in game_stats.columns], inplace=True)

# Calculate games played per team in current season
games_played_per_team = {}
if current_season_stats is not None:
    games_played_per_team = calculate_games_played_per_team(current_season_stats)
    print(f"Games played per team: {games_played_per_team}")

# Only use current season data (2025-26)
if current_season_stats is not None:
    game_stats = current_season_stats.groupby('Player_ID', as_index=False)[
        current_season_stats.select_dtypes(include='number').columns
    ].mean()
    print("Using only current season data (2025-26)")
else:
    # Fallback to any available data
    numeric_columns = game_stats.select_dtypes(include='number').columns
    game_stats = game_stats.groupby(['Player_ID', 'Season'], as_index=False)[numeric_columns].mean()
    game_stats = game_stats.groupby('Player_ID', as_index=False)[numeric_columns].mean()
    print("Fallback: Using combined season data")
player_availability_score = calculate_player_availability_score()

stats = pd.merge(
    game_stats,
    players[['PERSON_ID', 'DISPLAY_FIRST_LAST', 'TEAM_ID']],
    left_on='Player_ID',
    right_on='PERSON_ID',
    how='left'
)

stats.rename(columns={'DISPLAY_FIRST_LAST': 'Name'}, inplace=True)
if 'PERSON_ID' in stats.columns: # Drop PERSON_ID only if it exists after the merge
    stats.drop(columns=['PERSON_ID'], inplace=True)

# Check if there are any players with missing names
missing_names = stats[stats['Name'].isna()]
if not missing_names.empty:
    print(f"WARNING: {len(missing_names)} players with missing names (Player IDs: {missing_names['Player_ID'].unique().tolist()[:10]})")
print(f"Total players loaded: {stats['Player_ID'].nunique()}")

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

stats['TOV_RT'] = stats['TOV_RT'] * (-1) + 100

ratings = stats[['Name', 'Player_ID', 'TEAM_ID', 'FGN_RT', 'FTN_RT', 'FG3M_RT', 'PTS_RT', 'REB_RT', 'AST_RT', 'BLK_RT', 'STL_RT', 'TOV_RT']].copy()

ratings['Total_Rating'] = ratings[rating_columns].sum(axis=1)
ratings['Total_Rating'] = normalize(ratings['Total_Rating'])

ratings['Total_Available_Rating'] = ratings.apply(
    lambda row: row['Total_Rating'] * player_availability_score.get(row['Player_ID'], 0),
    axis=1
)
ratings['Total_Available_Rating'] = normalize(ratings['Total_Available_Rating'])

# Combined Rating
ratings['Combined_Rating'] = (ratings['Total_Rating'] + ratings['Total_Available_Rating']) / 2
ratings['Combined_Rating'] = normalize(ratings['Combined_Rating'])

# Weekly ratings
schedule_files = [
    "data/regular_season_schedule_2024-2025.csv",
    "data/regular_season_schedule_2025-2026.csv"
]

# Try to load the most recent schedule file that exists
schedule_file = None
for file_path in reversed(schedule_files):  # Try 2025-2026 first, then 2024-2025
    try:
        games_per_week, max_games_per_week = calculate_games_per_week(file_path)
        schedule_file = file_path
        print(f"Using schedule file: {file_path}")
        break
    except FileNotFoundError:
        print(f"Schedule file not found: {file_path} - trying next")
    except Exception as e:
        print(f"Error loading schedule file {file_path}: {e} - trying next")

if schedule_file is None:
    print("Warning: No valid schedule file found. Weekly ratings will not be calculated.")
    games_per_week = {}
    max_games_per_week = {}

weekly_ratings = ratings[['Player_ID', 'Name', 'TEAM_ID', 'Total_Rating', 'Total_Available_Rating']].copy()
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
punt_combos = []
for i in range(1, 3):
    for combo in itertools.combinations(rating_columns, i):
        punt_combos.append(list(combo))

print("Punt Combos:", punt_combos)

# Build all punt rating columns efficiently to avoid fragmentation
punt_rating_cols = {}
for punted_categories in punt_combos:
    remain_cols = [col for col in rating_columns if col not in punted_categories]
    if remain_cols:
        punt_name = "_Punt_" + "_".join(sorted([cat.replace('_RT', '') for cat in punted_categories]))
        
        # Calculate Total Rating
        total_rating = ratings[remain_cols].sum(axis=1)
        punt_rating_cols[f'Total{punt_name}_Rating'] = normalize(total_rating)
        
        # Calculate Available Rating
        available_rating = ratings.apply(
            lambda row: punt_rating_cols[f'Total{punt_name}_Rating'][row.name] * player_availability_score.get(row['Player_ID'], 0),
            axis=1
        )
        punt_rating_cols[f'Total{punt_name}_Available_Rating'] = normalize(available_rating)
        
        # Calculate Combined Rating
        combined_rating = (punt_rating_cols[f'Total{punt_name}_Rating'] + punt_rating_cols[f'Total{punt_name}_Available_Rating']) / 2
        punt_rating_cols[f'Total{punt_name}_Combined_Rating'] = normalize(combined_rating)
    else:
        print(f"Warning: All rating columns are punted in {punted_categories}. Skipping.")

# Add all punt rating columns at once
ratings = pd.concat([ratings, pd.DataFrame(punt_rating_cols, index=ratings.index)], axis=1)


# Selecting relevant players
ratings = ratings.sort_values('Total_Rating', ascending=False)
player_selection = ratings['Player_ID'].head(200).tolist()

# Save data
weekly_ratings = weekly_ratings.sort_values('Total_Available_Rating', ascending=False)
weekly_ratings.to_csv('data/weekly_ratings.csv', index=False)
ratings = ratings.sort_values('Total_Available_Rating', ascending=False)
ratings.to_csv('data/ratings.csv', index=False)