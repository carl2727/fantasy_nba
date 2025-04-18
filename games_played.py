import pandas as pd

teams_map = {
    "ATL": 1610612737,
    "BOS": 1610612738,
    "CLE": 1610612739,
    "NOP": 1610612740,
    "CHI": 1610612741,
    "DAL": 1610612742,
    "DEN": 1610612743,
    "GSW": 1610612744,
    "HOU": 1610612745,
    "LAC": 1610612746,
    "LAL": 1610612747,
    "MIA": 1610612748,
    "MIL": 1610612749,
    "MIN": 1610612750,
    "BKN": 1610612751,
    "NYK": 1610612752,
    "ORL": 1610612753,
    "IND": 1610612754,
    "PHI": 1610612755,
    "PHX": 1610612756,
    "POR": 1610612757,
    "SAC": 1610612758,
    "SAS": 1610612759,
    "OKC": 1610612760,
    "TOR": 1610612761,
    "UTA": 1610612762,
    "MEM": 1610612763,
    "WAS": 1610612764,
    "DET": 1610612765,
    "CHA": 1610612766,
}

game_stats_file = "all_player_game_stats_2024_2025.csv"
game_stats = pd.read_csv(game_stats_file)
players_file = "nba_players.csv"
players = pd.read_csv(players_file)

player_team = players[['PERSON_ID', 'TEAM_ID']]
player_team = player_team.rename(columns={'PERSON_ID': 'Player_ID'})
reverse_teams_map = {v: k for k, v in teams_map.items()}
player_team['Team'] = player_team['TEAM_ID'].map(reverse_teams_map)

game_stats['Team'] = game_stats['MATCHUP'].str[:3]
game_stats = game_stats[['SEASON_ID', 'Player_ID', 'Game_ID', 'Team']]

team_games = game_stats.groupby('Game_ID')

team_game_counts = {}

for team in teams_map.keys():
    filtered_games = game_stats[game_stats['Team'] == team]
    unique_games = filtered_games['Game_ID'].nunique()
    team_game_counts[team] = unique_games

player_game_counts = {}
player_availability_score = {}

for player in player_team['Player_ID']:
    filtered_games = game_stats[game_stats['Player_ID'] == player]
    unique_games = filtered_games['Game_ID'].nunique()
    player_game_counts[player] = unique_games
    if not filtered_games.empty:
        team = filtered_games['Team'].values[0]
        team_games = team_game_counts[team]
        player_availability_score[player] = unique_games / team_games
    else:
        player_availability_score[player] = 0




