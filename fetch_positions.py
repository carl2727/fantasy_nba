import pandas as pd
from nba_api.stats.endpoints import commonplayerinfo
from nba_api.stats.library.parameters import SeasonAll
import time
import os

def get_player_position(player_id):
    """
    Fetches the position for a given player_id using nba_api.

    Args:
        player_id (int): The PERSON_ID of the player.

    Returns:
        str: The player's position (e.g., 'Guard', 'Forward', 'Center', 'G-F'), 
             or None if not found or an error occurs.
    """
    try:
        # Fetch player info
        player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id, timeout=30)
        
        # The result is a list of dictionaries, we usually want the first one
        # The data is typically in 'CommonPlayerInfo' or 'PlayerHeadlineStats'
        # Let's check 'CommonPlayerInfo' first
        player_data_frame = player_info.common_player_info.get_data_frame()
        
        if not player_data_frame.empty:
            position = player_data_frame['POSITION'].iloc[0]
            if position:
                return position.strip() # Return stripped position
            else: # Position might be empty string
                # Fallback to PlayerHeadlineStats if position is empty in CommonPlayerInfo
                # This is less common but good to have a check
                player_headline_stats_df = player_info.player_headline_stats.get_data_frame()
                if not player_headline_stats_df.empty:
                    # Position is not directly in PlayerHeadlineStats,
                    # but this check confirms data was fetched.
                    # If CommonPlayerInfo had an empty position, it's likely the primary source.
                    return None # Or handle as 'Unknown'
        return None # Position not found
    except Exception as e:
        print(f"Error fetching position for player_id {player_id}: {e}")
        return None

def create_positions_csv(input_csv_path="nba_players.csv", output_csv_path="positions.csv"):
    """
    Reads player IDs from input_csv_path, fetches their positions,
    and saves them to output_csv_path.
    """
    if not os.path.exists(input_csv_path):
        print(f"Error: Input file '{input_csv_path}' not found.")
        return

    print(f"Reading players from {input_csv_path}...")
    try:
        players_df = pd.read_csv(input_csv_path)
    except Exception as e:
        print(f"Error reading CSV file '{input_csv_path}': {e}")
        return

    if 'PERSON_ID' not in players_df.columns:
        print("Error: 'PERSON_ID' column not found in the input CSV.")
        return

    player_positions = []
    total_players = len(players_df)
    print(f"Found {total_players} players. Fetching positions (this may take a while)...")

    for index, row in players_df.iterrows():
        person_id = row['PERSON_ID']
        
        # Ensure person_id is an integer
        try:
            person_id = int(person_id)
        except ValueError:
            print(f"Skipping invalid PERSON_ID: {row['PERSON_ID']} for player {row.get('DISPLAY_FIRST_LAST', 'N/A')}")
            player_positions.append({'PERSON_ID': row['PERSON_ID'], 'POSITION': 'Invalid ID'})
            continue

        player_name = row.get('DISPLAY_FIRST_LAST', f"ID: {person_id}") # Use name if available for logging
        
        print(f"Fetching position for {player_name} ({index + 1}/{total_players})...")
        position = get_player_position(person_id)
        
        if position:
            player_positions.append({'PERSON_ID': person_id, 'POSITION': position})
            print(f"Found position: {position}")
        else:
            player_positions.append({'PERSON_ID': person_id, 'POSITION': 'Unknown'})
            print("Position not found or error occurred.")
        
        # NBA API can be strict with request rates.
        # A delay helps avoid getting blocked. Adjust as needed.
        time.sleep(0.7) # 700 milliseconds delay

    print("\nAll players processed.")
    
    if player_positions:
        positions_df = pd.DataFrame(player_positions)
        try:
            positions_df.to_csv(output_csv_path, index=False)
            print(f"Successfully created '{output_csv_path}'")
        except Exception as e:
            print(f"Error writing CSV file '{output_csv_path}': {e}")
    else:
        print("No position data was collected.")

if __name__ == "__main__":
    # Assuming nba_players.csv is in the same directory as the script
    # and you want positions.csv to be created there too.
    # Adjust paths if necessary.
    current_directory = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_directory, "nba_players.csv")
    output_file = os.path.join(current_directory, "positions.csv")
    
    create_positions_csv(input_csv_path=input_file, output_csv_path=output_file)
