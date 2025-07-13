from nba_api.stats.endpoints import CommonAllPlayers, playergamelog
import pandas as pd
import time
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'data'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PLAYERS_CSV_PATH = OUTPUT_DIR / 'nba_players.csv'
GAME_STATS_CSV_PATH = OUTPUT_DIR / 'all_player_game_stats_2024_2025.csv'

seasons = ['2024-25']
season_type = 'Regular Season'

# 1. Load existing data if it exists
if GAME_STATS_CSV_PATH.exists():
    print(f"Loading existing data from {GAME_STATS_CSV_PATH}...")
    try:
        existing_df = pd.read_csv(GAME_STATS_CSV_PATH, dtype={'Player_ID': str, 'Game_ID': str})
        # 2. Create a set of existing (Player_ID, Game_ID) tuples for fast lookups
        existing_games = set(zip(existing_df['Player_ID'], existing_df['Game_ID']))
        print(f"Found {len(existing_games)} existing game records.")
    except pd.errors.EmptyDataError:
        print("Existing CSV is empty. Starting fresh.")
        existing_df = pd.DataFrame()
        existing_games = set()
else:
    print("No existing game stats file found. Starting fresh.")
    existing_df = pd.DataFrame()
    existing_games = set()

# 3. Fetch all active players
all_players = CommonAllPlayers(is_only_current_season=1, season=seasons[0])
players = all_players.get_data_frames()[0]
player_data = players[['PERSON_ID', 'DISPLAY_FIRST_LAST', 'TEAM_ID', 'TEAM_NAME']]
player_data.to_csv(PLAYERS_CSV_PATH, index=False)
print(f"Found {len(player_data)} active players for the season.")

new_game_data_list = []

# 4. Iterate through players, fetch their logs, and filter for new games
for season in seasons:
    for player in player_data.itertuples(index=False):
        player_id = str(player.PERSON_ID)
        player_name = player.DISPLAY_FIRST_LAST
        try:
            print(f"Fetching data for Player ID {player_id} ({player_name})...")
            gamelog_data = playergamelog.PlayerGameLog(player_id=player_id, season=season, season_type_all_star=season_type)
            game_data_df = gamelog_data.get_data_frames()[0]
            
            if not game_data_df.empty:
                game_data_df['Player_ID'] = game_data_df['Player_ID'].astype(str)
                game_data_
        except Exception as e:
            print(f"Error fetching data for Player ID {player}: {e}")

if all_game_data:
    combined_game_data = pd.concat(all_game_data, ignore_index=True)
    combined_game_data.to_csv(GAME_STATS_CSV_PATH, index=False)
    print(f"All game data saved to {GAME_STATS_CSV_PATH}")
else:
    print("No game data was fetched.")