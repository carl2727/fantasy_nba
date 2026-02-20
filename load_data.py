from nba_api.stats.endpoints import CommonAllPlayers, playergamelog
import pandas as pd
import time
import requests

seasons = ['2025-26']
season_type = 'Regular Season'

all_players = CommonAllPlayers(is_only_current_season=1)
players = all_players.get_data_frames()[0]
player_data = players[['PERSON_ID', 'DISPLAY_FIRST_LAST', 'TEAM_ID', 'TEAM_NAME']]
player_data.to_csv('nba_players.csv', index=False)

all_game_data = []

for season in seasons:
    for player in player_data['PERSON_ID']:
        try:
            data = playergamelog.PlayerGameLog(player_id=player, season=season)
            game_data = data.get_data_frames()[0]
            if not game_data.empty:
                all_game_data.append(game_data)
            print(f"Fetching data for Player ID {player}")
            time.sleep(1)
        except Exception as e:
            print(f"Error fetching data for Player ID {player}: {e}")

if all_game_data:
    combined_game_data = pd.concat(all_game_data, ignore_index=True)
    combined_game_data.to_csv('all_player_game_stats_2025_2026.csv', index=False)
    print("All game data saved to all_player_game_stats_2025_2026.csv")
else:
    print("No game data was fetched.")