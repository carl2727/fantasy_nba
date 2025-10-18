import pandas as pd
import os

def create_fantasy_positions_csv(
    positions_input_csv_path="positions.csv",
    players_input_csv_path="nba_players.csv", # Path to nba_players.csv
    output_csv_path="fantasy_positions.csv"):
    """
    Transforms NBA positions from an input CSV to standard fantasy basketball positions
    (PG, SG, SF, PF, C) and saves them in a long format CSV.

    The mapping is as follows:
    - "Guard": PG, SG
    - "Forward-Guard" or "Guard-Forward": SG, SF
    - "Forward": SF, PF
    - "Center-Forward" or "Forward-Center": PF, C
    - "Center": C

    Args:
        positions_input_csv_path (str): Path to the input CSV file with PERSON_ID and POSITION.
        players_input_csv_path (str): Path to the input CSV file with PERSON_ID and DISPLAY_FIRST_LAST.
        output_csv_path (str): Path for the output CSV file (e.g., "fantasy_positions.csv").
    """
    if not os.path.exists(positions_input_csv_path):
        print(f"Error: Positions input file '{positions_input_csv_path}' not found.")
        return
    if not os.path.exists(players_input_csv_path):
        print(f"Error: Players input file '{players_input_csv_path}' not found.")
        return

    print(f"Reading NBA positions from '{positions_input_csv_path}'...")
    try:
        nba_positions_df = pd.read_csv(positions_input_csv_path)
    except Exception as e:
        print(f"Error reading CSV file '{positions_input_csv_path}': {e}")
        return

    if 'PERSON_ID' not in nba_positions_df.columns or 'POSITION' not in nba_positions_df.columns:
        print("Error: 'PERSON_ID' and/or 'POSITION' columns not found in the input CSV.")
        return

    print(f"Reading player names from '{players_input_csv_path}'...")
    try:
        nba_players_df = pd.read_csv(players_input_csv_path, usecols=['PERSON_ID', 'DISPLAY_FIRST_LAST'])
    except Exception as e:
        print(f"Error reading CSV file '{players_input_csv_path}': {e}")
        return

    if 'PERSON_ID' not in nba_players_df.columns or 'DISPLAY_FIRST_LAST' not in nba_players_df.columns:
        print("Error: 'PERSON_ID' and/or 'DISPLAY_FIRST_LAST' columns not found in the players CSV.")
        return

    # Create a mapping from PERSON_ID to DISPLAY_FIRST_LAST for quick lookup
    player_name_map = pd.Series(nba_players_df.DISPLAY_FIRST_LAST.values, index=nba_players_df.PERSON_ID).to_dict()

    # Define the mapping from NBA positions to fantasy positions
    # Keys should exactly match the unique, stripped strings in the 'POSITION' column of positions.csv
    nba_to_fantasy_map = {
        "Guard": ["PG", "SG"],
        "Forward-Guard": ["SG", "SF"],
        "Guard-Forward": ["SG", "SF"],  # Explicitly include to match common variations
        "Forward": ["SF", "PF"],
        "Center-Forward": ["PF", "C"],
        "Forward-Center": ["PF", "C"],  # Explicitly include to match common variations
        "Center": ["C"]
        # Positions like 'Unknown', 'Invalid ID', or any other unlisted string will be ignored.
    }

    fantasy_positions_list = []
    unique_players_processed_count = set() # To count unique players with valid mappings
    skipped_positions_summary = {} # To count occurrences of unmapped/skipped positions

    print("Transforming positions to fantasy basketball format...")
    for index, row in nba_positions_df.iterrows():
        person_id = row['PERSON_ID']
        player_name = player_name_map.get(person_id, "Unknown Name") # Get name, default if not found
        nba_position_str = row['POSITION']

        # Handle potential NaN values or non-string types for position
        if pd.isna(nba_position_str) or not isinstance(nba_position_str, str):
            nba_position_str = "Unknown" # Treat as "Unknown" for consistent handling

        normalized_nba_pos = nba_position_str.strip()

        if normalized_nba_pos in nba_to_fantasy_map:
            fantasy_pos_for_player = nba_to_fantasy_map[normalized_nba_pos]
            for fp_eligible in fantasy_pos_for_player:
                fantasy_positions_list.append({
                    'PERSON_ID': person_id,
                    'DISPLAY_FIRST_LAST': player_name,
                    'FANTASY_POSITION': fp_eligible
                })
            unique_players_processed_count.add(person_id)
        else:
            # Record and count positions that are not in the map
            if normalized_nba_pos not in skipped_positions_summary:
                skipped_positions_summary[normalized_nba_pos] = 0
            skipped_positions_summary[normalized_nba_pos] += 1
            # You can uncomment the following lines to print warnings for unexpected unmapped positions during processing:
            # if normalized_nba_pos not in ["Unknown", "Invalid ID"]: # Example: Don't warn for expected skips
            #     print(f"Warning: NBA position '{normalized_nba_pos}' for {player_name} (ID: {person_id}) has no defined fantasy mapping. Skipping.")

    if skipped_positions_summary:
        print("\nSummary of NBA positions not mapped (and therefore skipped):")
        for pos, count in skipped_positions_summary.items():
            print(f"- '{pos}': {count} occurrences")

    if fantasy_positions_list:
        output_df = pd.DataFrame(fantasy_positions_list)
        # Sort by DISPLAY_FIRST_LAST, then PERSON_ID, then FANTASY_POSITION for a consistent and readable output
        output_df.sort_values(by=['DISPLAY_FIRST_LAST', 'PERSON_ID', 'FANTASY_POSITION'], inplace=True)
        try:
            output_df.to_csv(output_csv_path, index=False)
            print(f"\nSuccessfully created '{output_csv_path}'.")
            print(f"Total fantasy position entries generated: {len(output_df)}")
            print(f"Number of unique players with fantasy positions: {len(unique_players_processed_count)}")
        except Exception as e:
            print(f"Error writing CSV file '{output_csv_path}': {e}")
    else:
        print("\nNo fantasy position data was generated. This might be due to an empty input file, "
              "no matching positions in the mapping, or other data issues.")

if __name__ == "__main__":
    # Determine the directory where the script is located
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    # Define input file paths relative to the script's directory
    positions_file = os.path.join(script_directory, "positions.csv")
    players_file = os.path.join(script_directory, "nba_players.csv") # Make sure this file exists
    output_file = os.path.join(script_directory, "fantasy_positions.csv") # Output file
    
    create_fantasy_positions_csv(
        positions_input_csv_path=positions_file,
        players_input_csv_path=players_file,
        output_csv_path=output_file
    )
