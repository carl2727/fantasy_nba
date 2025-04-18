import pandas as pd

categories = ['FG%', 'FT%', 'PTS', 'FG3M', 'REB', 'BLK', 'AST', 'TOV']
rating_columns = ['FG%_RT', 'FT%_RT', 'FG3M_RT', 'PTS_RT', 'REB_RT', 'AST_RT', 'TOV_RT']
game_stats_file = "all_player_game_stats_2024_2025.csv"
players_file = "nba_players.csv"
game_stats = pd.read_csv(game_stats_file)
players = pd.read_csv(players_file)
game_stats.drop(columns=['Game_ID', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'VIDEO_AVAILABLE'], inplace=True)
game_stats = game_stats.groupby('Player_ID').mean().reset_index()

stats = pd.merge(
    game_stats,
    players[['PERSON_ID', 'DISPLAY_FIRST_LAST']],
    left_on='Player_ID',
    right_on='PERSON_ID',
    how='left'
)

stats.rename(columns={'DISPLAY_FIRST_LAST': 'Name'}, inplace=True)
stats.drop(columns=['PERSON_ID'])

stats['FGPM'] = stats['FGM'] - (stats['FGA'] - stats['FGM'])
stats['FG%'] = stats['FGPM'] - stats['FGPM'].min()
stats['FTPM'] = stats['FTM'] - (stats['FTA'] - stats['FTM'])
stats['FT%'] = stats['FTPM'] - stats['FTPM'].min()

for cat in categories:
    max = stats[cat].max()
    stats[cat + '_RT'] = stats[cat] / max

stats['TOV_RT'] = stats['TOV_RT'] * (-1)

ratings = stats[['Name', 'Player_ID', 'FG%_RT', 'FT%_RT', 'FG3M_RT', 'PTS_RT', 'REB_RT', 'AST_RT', 'TOV_RT']]
ratings['Total_Rating'] = ratings[rating_columns].sum(axis=1)
ratings['Total_Rating'] = (ratings['Total_Rating'] / ratings['Total_Rating'].max())*100
ratings.sort_values('Total_Rating', ascending=False, inplace=True)
stats.to_csv('all_player_stats_2024_2025.csv', index=False)
ratings.to_csv('ratings.csv', index=False)