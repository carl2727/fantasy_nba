import pandas as pd

def calculate_games_per_week(schedule_file):
    # Read the schedule file
    schedule = pd.read_csv(schedule_file)

    # Map of team names to IDs
    team_name_map = {
        "Atlanta Hawks": 1610612737,
        "Boston Celtics": 1610612738,
        "Brooklyn Nets": 1610612751,
        "Charlotte Hornets": 1610612766,
        "Chicago Bulls": 1610612741,
        "Cleveland Cavaliers": 1610612739,
        "Dallas Mavericks": 1610612742,
        "Denver Nuggets": 1610612743,
        "Detroit Pistons": 1610612765,
        "Golden State Warriors": 1610612744,
        "Houston Rockets": 1610612745,
        "Indiana Pacers": 1610612754,
        "Los Angeles Clippers": 1610612746,
        "Los Angeles Lakers": 1610612747,
        "Memphis Grizzlies": 1610612763,
        "Miami Heat": 1610612748,
        "Milwaukee Bucks": 1610612749,
        "Minnesota Timberwolves": 1610612750,
        "New Orleans Pelicans": 1610612740,
        "New York Knicks": 1610612752,
        "Oklahoma City Thunder": 1610612760,
        "Orlando Magic": 1610612753,
        "Philadelphia 76ers": 1610612755,
        "Phoenix Suns": 1610612756,
        "Portland Trail Blazers": 1610612757,
        "Sacramento Kings": 1610612758,
        "San Antonio Spurs": 1610612759,
        "Toronto Raptors": 1610612761,
        "Utah Jazz": 1610612762,
        "Washington Wizards": 1610612764,
    }

    # Map team names to IDs for visitor and home teams
    schedule['visitor_id'] = schedule['Visitor'].map(team_name_map)
    schedule['home_id'] = schedule['Home'].map(team_name_map)

    # Convert the 'Game Date' column to datetime and extract calendar week
    schedule['Date'] = pd.to_datetime(schedule['Game Date'])
    schedule['calendar_week'] = schedule['Date'].dt.isocalendar().week

    # Initialize dictionaries
    games_per_week = {}
    max_games_per_week = {}

    # Iterate over each row in the schedule
    for _, row in schedule.iterrows():
        visitor_id = row['visitor_id']
        home_id = row['home_id']
        week = row['calendar_week']

        # Update visitor team's games
        if visitor_id not in games_per_week:
            games_per_week[visitor_id] = {}
        if week not in games_per_week[visitor_id]:
            games_per_week[visitor_id][week] = 0
        games_per_week[visitor_id][week] += 1

        # Update home team's games
        if home_id not in games_per_week:
            games_per_week[home_id] = {}
        if week not in games_per_week[home_id]:
            games_per_week[home_id][week] = 0
        games_per_week[home_id][week] += 1

    # Calculate the maximum games per week
    for team_id, weeks in games_per_week.items():
        for week, games in weeks.items():
            if week not in max_games_per_week:
                max_games_per_week[week] = 0
            max_games_per_week[week] = max(max_games_per_week[week], games)

    # Return the two dictionaries
    return games_per_week, max_games_per_week

# Allow the module to be run directly for testing
if __name__ == "__main__":
    schedule_file = "data/regular_season_schedule_2024-2025.csv"
    games_per_week, max_games_per_week = calculate_games_per_week(schedule_file)
    print("Games Per Week:", games_per_week)
    print("Max Games Per Week:", max_games_per_week)