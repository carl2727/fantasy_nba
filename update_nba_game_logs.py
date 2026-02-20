import pandas as pd
from nba_api.stats.endpoints import LeagueGameLog
from datetime import datetime, timedelta
import time
import os

# --- Configuration ---
TARGET_SEASON_API_FORMAT = "2025-26"  # Season format for the NBA API
# This is the base path from your context
BASE_PROJECT_PATH = "c:/Users/Carl/OneDrive/Code Projects/fantasy_nba/"
GAME_LOGS_CSV_FILENAME = "all_player_game_stats_2025_2026.csv"
GAME_LOGS_CSV_FULL_PATH = os.path.join(BASE_PROJECT_PATH, GAME_LOGS_CSV_FILENAME)

# Define the expected columns for the CSV to ensure consistency and order
EXPECTED_COLUMNS = [
    'SEASON_ID', 'Player_ID', 'Game_ID', 'GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'FGM', 'FGA', 'FG_PCT',
    'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK',
    'TOV', 'PF', 'PTS', 'PLUS_MINUS', 'VIDEO_AVAILABLE'
]
# Season start date (approximate, adjust if needed for the specific season)
# This is used if the CSV is empty.
SEASON_START_DATE = datetime(2025, 10, 1) 

def load_existing_gamelogs(filepath):
    """Loads existing game logs from a CSV file."""
    try:
        df = pd.read_csv(filepath)
        if df.empty:
            print(f"File {filepath} is empty. Will fetch data from season start.")
            return pd.DataFrame(columns=EXPECTED_COLUMNS)
        
        # Convert GAME_DATE to datetime objects for comparison
        # The format in your CSV is like "APR 01, 2025"
        df['GAME_DATE_DT'] = pd.to_datetime(df['GAME_DATE'], format='%b %d, %Y')
        
        # Ensure Player_ID and Game_ID are suitable for merging/comparison
        df['Player_ID'] = df['Player_ID'].astype(int)
        df['Game_ID'] = df['Game_ID'].astype(str) # API returns Game_ID as string
        df['SEASON_ID'] = df['SEASON_ID'].astype(int)
        print(f"Successfully loaded {len(df)} existing game logs from {filepath}")
        return df
    except FileNotFoundError:
        print(f"File not found: {filepath}. A new file will be created.")
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    except pd.errors.EmptyDataError:
        print(f"File is empty: {filepath}. A new file will be created.")
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    except Exception as e:
        print(f"Error loading CSV {filepath}: {e}. Starting with an empty DataFrame.")
        return pd.DataFrame(columns=EXPECTED_COLUMNS)

def get_date_range_for_fetch(df_existing_gamelogs):
    """Determines the date range to fetch new games."""
    today = datetime.now()
    # Fetch data up to yesterday to ensure games are finalized
    yesterday = today - timedelta(days=1) 
    
    date_to_fetch = yesterday

    if df_existing_gamelogs.empty or 'GAME_DATE_DT' not in df_existing_gamelogs.columns or df_existing_gamelogs['GAME_DATE_DT'].isnull().all():
        date_from_fetch = SEASON_START_DATE
        print(f"No existing valid game data. Fetching from season start: {date_from_fetch.strftime('%Y-%m-%d')}")
    else:
        latest_date_in_csv = df_existing_gamelogs['GAME_DATE_DT'].max()
        date_from_fetch = latest_date_in_csv + timedelta(days=1)
        print(f"Latest game date in CSV: {latest_date_in_csv.strftime('%Y-%m-%d')}.")
    
    print(f"Attempting to fetch games from {date_from_fetch.strftime('%Y-%m-%d')} to {date_to_fetch.strftime('%Y-%m-%d')}.")

    if date_from_fetch > date_to_fetch:
        print(f"Fetch start date {date_from_fetch.strftime('%Y-%m-%d')} is after fetch end date {date_to_fetch.strftime('%Y-%m-%d')}. No new games to fetch today.")
        return None, None

    return date_from_fetch.strftime('%Y-%m-%d'), date_to_fetch.strftime('%Y-%m-%d')

def fetch_nba_gamelogs_from_api(season_api_format, date_from_str=None, date_to_str=None):
    """Fetches game logs from NBA API for the given season and date range."""
    print(f"Fetching NBA game logs for season {season_api_format} from {date_from_str} to {date_to_str}...")
    try:
        # Adding a small delay to be polite to the API
        time.sleep(1)
        gamelog_endpoint = LeagueGameLog(
            season=season_api_format,
            league_id="00", # NBA
            season_type_all_star="Regular Season", # Assuming regular season games
            date_from_nullable=date_from_str,
            date_to_nullable=date_to_str,
            player_or_team_abbreviation='P' # Explicitly request Player data
        )
        df_new_logs = gamelog_endpoint.get_data_frames()[0]
        
        if df_new_logs.empty:
            print("No new game logs found from API for the specified date range.")
            return pd.DataFrame()

        print(f"Fetched {len(df_new_logs)} raw game log entries from API.")
        return df_new_logs
    except Exception as e:
        print(f"Error fetching data from NBA API: {e}")
        return pd.DataFrame()

def transform_and_filter_new_logs(df_api_logs, df_existing_logs):
    """Transforms API data to match CSV format and filters out duplicates."""
    if df_api_logs.empty:
        return pd.DataFrame()

    df_transformed = df_api_logs.copy()

    # Rename API columns to match CSV conventions if needed
    df_transformed.rename(columns={
        'PLAYER_ID': 'Player_ID', 
        'GAME_ID': 'Game_ID'
        # Add other renames if API column names differ significantly from EXPECTED_COLUMNS
    }, inplace=True)

    # Ensure SEASON_ID is an integer.
    # The API (when fetching player data) returns SEASON_ID in the 2YYYY format (e.g., 22024 for "2024-25" season).
    # So, direct conversion to int is sufficient.
    if 'SEASON_ID' in df_transformed.columns:
        df_transformed['SEASON_ID'] = df_transformed['SEASON_ID'].astype(int)
    
    # Format GAME_DATE to match CSV's "MON DD, YYYY" (e.g., "APR 01, 2025")
    df_transformed['GAME_DATE_DT'] = pd.to_datetime(df_transformed['GAME_DATE']) # For sorting later
    df_transformed['GAME_DATE'] = df_transformed['GAME_DATE_DT'].dt.strftime('%b %d, %Y').str.upper()
    
    
    # Ensure Player_ID and Game_ID types are consistent for filtering
    # First, ensure 'Player_ID' column exists.
    # This check is performed after the initial attempt to rename 'PLAYER_ID' (all caps from API) to 'Player_ID'.
    # If 'Player_ID' is not present, it checks for 'PERSON_ID' as a fallback.
    if 'Player_ID' not in df_transformed.columns:
        if 'PERSON_ID' in df_transformed.columns:
            print("Info: 'Player_ID' column not found (after initial 'PLAYER_ID' rename attempt), "
                    "'PERSON_ID' column found. Renaming 'PERSON_ID' to 'Player_ID'.")
            df_transformed.rename(columns={'PERSON_ID': 'Player_ID'}, inplace=True)
        else:
            # If neither 'Player_ID' (after potential rename from API's 'PLAYER_ID') nor 'PERSON_ID' is found
            original_api_cols = df_api_logs.columns.tolist() # Get columns from the original API data
            current_transformed_cols = df_transformed.columns.tolist() # Columns after initial 'PLAYER_ID' rename
            raise KeyError(
                f"Critical Error: 'Player_ID' column could not be established. \n"
                f"Attempted to use 'Player_ID' (after potential rename from API's 'PLAYER_ID') and 'PERSON_ID' (from API).\n"
                f"Original API data columns: {original_api_cols}\n"
                f"DataFrame columns after initial 'PLAYER_ID' rename attempt: {current_transformed_cols}"
            )

    df_transformed['Player_ID'] = df_transformed['Player_ID'].astype(int)
    df_transformed['Game_ID'] = df_transformed['Game_ID'].astype(str)

    # Select only the columns expected in the CSV
    cols_to_use = [col for col in EXPECTED_COLUMNS if col in df_transformed.columns]
    df_transformed = df_transformed[cols_to_use]

    # Filter out duplicates already present in the existing CSV
    if not df_existing_logs.empty and 'Game_ID' in df_existing_logs.columns and 'Player_ID' in df_existing_logs.columns:
        # Create unique keys for existing logs
        existing_keys = set(zip(df_existing_logs['Game_ID'].astype(str), df_existing_logs['Player_ID'].astype(int)))
        
        df_transformed = df_transformed[
            ~df_transformed.apply(lambda row: (str(row['Game_ID']), int(row['Player_ID'])) in existing_keys, axis=1)
        ]
        print(f"After filtering duplicates, {len(df_transformed)} truly new game logs remain.")
    else:
        print("No existing logs to check for duplicates against, or key columns missing.")
        
    return df_transformed

def save_gamelogs_to_csv(df_to_save, filepath):
    """Saves the DataFrame to CSV, ensuring correct date format and sorting."""
    try:
        # Convert GAME_DATE to datetime for proper sorting, then back to string
        df_to_save['GAME_DATE_DT_TEMP'] = pd.to_datetime(df_to_save['GAME_DATE'], format='%b %d, %Y')
        df_sorted = df_to_save.sort_values(by=['GAME_DATE_DT_TEMP', 'Player_ID'], ascending=[True, True]) # Ascending for chronological
        
        # Ensure the GAME_DATE column is in the desired string format before saving
        df_sorted['GAME_DATE'] = df_sorted['GAME_DATE_DT_TEMP'].dt.strftime('%b %d, %Y').str.upper()
        df_sorted = df_sorted[EXPECTED_COLUMNS] # Ensure final column order and drop temp date column
        
        df_sorted.to_csv(filepath, index=False)
        print(f"Successfully saved/updated game logs to {filepath}")
    except Exception as e:
        print(f"Error saving CSV to {filepath}: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    print(f"Starting daily update for NBA game logs: {GAME_LOGS_CSV_FULL_PATH}")
    
    df_existing_logs = load_existing_gamelogs(GAME_LOGS_CSV_FULL_PATH)
    
    # Prepare df_existing_logs for concatenation by ensuring GAME_DATE is string and dropping temp column
    df_existing_for_concat = df_existing_logs.copy()
    if 'GAME_DATE_DT' in df_existing_for_concat.columns:
        if pd.api.types.is_datetime64_any_dtype(df_existing_for_concat['GAME_DATE_DT']):
             df_existing_for_concat['GAME_DATE'] = df_existing_for_concat['GAME_DATE_DT'].dt.strftime('%b %d, %Y').str.upper()
        df_existing_for_concat = df_existing_for_concat.drop(columns=['GAME_DATE_DT'], errors='ignore')

    fetch_from_date_str, fetch_to_date_str = get_date_range_for_fetch(df_existing_logs) # df_existing_logs still has GAME_DATE_DT
    
    if fetch_from_date_str and fetch_to_date_str:
        df_api_data = fetch_nba_gamelogs_from_api(TARGET_SEASON_API_FORMAT, fetch_from_date_str, fetch_to_date_str)
        
        if not df_api_data.empty:
            df_new_logs_to_add = transform_and_filter_new_logs(df_api_data, df_existing_for_concat) # Pass the one with string GAME_DATE
            
            if not df_new_logs_to_add.empty:
                df_combined = pd.concat([df_existing_for_concat, df_new_logs_to_add], ignore_index=True)
                
                # Final deduplication safeguard
                df_combined.drop_duplicates(subset=['Game_ID', 'Player_ID'], keep='last', inplace=True)
                
                save_gamelogs_to_csv(df_combined, GAME_LOGS_CSV_FULL_PATH)
                print(f"Added {len(df_new_logs_to_add)} new game logs.")
            else:
                print("No new unique game logs to add after filtering.")
        else:
            print("No new data fetched from API for the determined date range.")
    else:
        print("Date range for fetching is invalid (e.g., all up-to-date or season not started far enough).")
        
    print("Daily update script finished.")