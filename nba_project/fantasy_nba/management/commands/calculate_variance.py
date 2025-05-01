from django.core.management.base import BaseCommand
from fantasy_nba.ratings import categories, player_selection
import pandas as pd
import statistics

file_path = 'data/all_player_game_stats_2024_2025.csv'
game_stats = pd.read_csv(file_path)

def calculate_game_to_game_variance(df, categories):
    average_variance = {}

    if 'Player_ID' not in df.columns:
        raise ValueError("The DataFrame requires a 'Player_ID' column to identify players.")

    for category in categories:
        if category not in df.columns:
            print(f"Warning: Category '{category}' not found in the DataFrame. Skipping.")
            continue

        print(f"Processing category: {category}")
        variance = []
        for player in player_selection:
            if player not in df['Player_ID'].values:
                print(f"Warning: Player ID '{player}' not found in the DataFrame. Skipping.")
                continue
            player_data = df[df['Player_ID'] == player]

            variance.append(player_data[category].var(ddof=0))
        average_variance[category] = statistics.mean(variance)

    return average_variance

class Command(BaseCommand):
    help = "Calculate game-to-game variance per player for each category"

    def handle(self, *args, **kwargs):
        # Load the data directly from the CSV file
        file_path = 'data/all_player_game_stats_2024_2025.csv'
        stats = pd.read_csv(file_path)

        # Define the categories to calculate variance for
        categories = ['PTS', 'FG3M', 'REB', 'BLK', 'AST', 'TOV']

        # Calculate game-to-game variance
        variance_results = calculate_game_to_game_variance(stats, categories)

        # Output the results
        output_choice = input("Choose output method ('screen' or 'csv'): ").lower()

        if output_choice == 'screen':
            print("\nGame-to-game variance per category (average across players):")
            for category, avg_variance in variance_results.items():
                print(f"- {category}: {avg_variance:.4f}")
        elif output_choice == 'csv':
            csv_filename = 'game_to_game_variance_per_category.csv'
            output_df = pd.DataFrame(list(variance_results.items()), columns=['Category', 'Average Variance'])
            output_df.to_csv(csv_filename, index=False)
            print(f"\nResults saved to '{csv_filename}'")
        else:
            print("Invalid output choice. Please enter 'screen' or 'csv'.")