# fantasy_nba/games_played.py
import pandas as pd

def calculate_player_availability_score():
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

    game_stats_file = "data/all_player_game_stats_2025_2026.csv"
    game_stats = pd.read_csv(game_stats_file)
    players_file = "data/nba_players.csv"
    players_df = pd.read_csv(players_file) # Renamed to avoid conflict with outer scope 'players' if any

    # Clean PERSON_ID in players_df
    players_df['PERSON_ID'] = pd.to_numeric(players_df['PERSON_ID'], errors='coerce')
    players_df.dropna(subset=['PERSON_ID'], inplace=True)
    players_df['PERSON_ID'] = players_df['PERSON_ID'].astype(int)

    # Clean Player_ID in game_stats
    game_stats['Player_ID'] = pd.to_numeric(game_stats['Player_ID'], errors='coerce')
    game_stats.dropna(subset=['Player_ID'], inplace=True)
    game_stats['Player_ID'] = game_stats['Player_ID'].astype(int)

    player_team = players_df[['PERSON_ID', 'TEAM_ID']]
    player_team = player_team.rename(columns={'PERSON_ID': 'Player_ID'})
    reverse_teams_map = {v: k for k, v in teams_map.items()}
    player_team['Team'] = player_team['TEAM_ID'].map(reverse_teams_map)

    # Ensure 'MATCHUP' column exists before trying to access it
    if 'MATCHUP' in game_stats.columns:
        game_stats['Team_Abbr_From_Matchup'] = game_stats['MATCHUP'].str[:3]
        # Select necessary columns, using the new temp column if 'Team' isn't directly available
        # This assumes 'Team' column might not be in the CSV or needs to be derived.
        # If 'Team' is reliably in game_stats CSV, this can be simplified.
        game_stats_for_teams = game_stats[['Player_ID', 'Game_ID', 'Team_Abbr_From_Matchup']].rename(columns={'Team_Abbr_From_Matchup': 'Team'})
    else:
        # Fallback or error if MATCHUP is essential and missing
        print("Warning: 'MATCHUP' column not found in game_stats. Team game counts might be inaccurate.")
        # Create a dummy 'Team' column if absolutely necessary for schema, or handle error
        game_stats_for_teams = game_stats[['Player_ID', 'Game_ID']].copy()
        game_stats_for_teams['Team'] = None # Or some default / error indicator

    team_game_counts = {}
    for team in teams_map.keys():
        filtered_games = game_stats_for_teams[game_stats_for_teams['Team'] == team]
        unique_games = filtered_games['Game_ID'].nunique()
        team_game_counts[team] = unique_games

    player_game_counts = {}
    player_availability_score = {}
    for player in player_team['Player_ID']:
        filtered_games = game_stats[game_stats['Player_ID'] == player]
        # Need to get the team for this player from player_team, as game_stats might not have it consistently for all their games
        player_current_team_abbr = player_team[player_team['Player_ID'] == player]['Team'].values

        unique_games = filtered_games['Game_ID'].nunique()
        player_game_counts[player] = unique_games
        if player_current_team_abbr.size > 0 and player_current_team_abbr[0] in team_game_counts:
            team_abbr = player_current_team_abbr[0]
            team_games = team_game_counts.get(team_abbr, 1) # Default to 1 to avoid division by zero if team not in counts
            player_availability_score[player] = unique_games / team_games
        else:
            player_availability_score[player] = 0

    return player_availability_score