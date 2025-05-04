from django.core.management.base import BaseCommand
from fantasy_nba.ratings import categories, player_selection, calc_fgn_ftn
import pandas as pd
import statistics

file_path = 'data/all_player_game_stats_2024_2025.csv'
game_stats = pd.read_csv(file_path)

def calculate_average_coefficient_of_variation(df, categories, player_selection):
    average_cv_per_category = {}
    if 'Player_ID' not in df.columns:
        raise ValueError("The DataFrame requires a 'Player_ID' column.")
    for category in categories:
        if category not in df.columns:
            print(f"Warning: Category '{category}' not found. Skipping.")
            continue
        print(f"Processing category: {category}")
        cv_values = []
        
        for player in player_selection:
            player_data = df[df['Player_ID'] == player]
            if not player_data.empty:
                player_mean = player_data[category].mean()
                player_std = player_data[category].std(ddof=0)
                if player_mean != 0:
                    cv = abs(player_std / player_mean)
                    cv_values.append(cv)
                elif player_std == 0:
                    cv_values.append(0)
                else:
                    print(f"Warning: Player {player} has a mean of 0 for {category}, CV undefined. Skipping for average.")
            else:
                print(f"Warning: Player ID '{player}' not found in DataFrame.")

        average_cv_per_category[category] = statistics.mean(cv_values) if cv_values else 0

    return average_cv_per_category

class Command(BaseCommand):
    help = "Calculate game-to-game variance per player for each category"

    def handle(self, *args, **kwargs):
        file_path = 'data/all_player_game_stats_2024_2025.csv'
        stats_file = pd.read_csv(file_path)
        stats = calc_fgn_ftn(stats_file)
        print("Stats DataFrame after calc_fgn_ftn:")
        print(stats.head())
        
        print(categories)

        variance_results = calculate_average_coefficient_of_variation(stats, categories, player_selection)

        print("\nGame-to-game variance per category (average across players):")
        for category, avg_variance in variance_results.items():
            print(f"- {category}: {avg_variance:.4f}")

        csv_filename = 'game_to_game_variance_per_category.csv'
        output_df = pd.DataFrame(list(variance_results.items()), columns=['Category', 'Average Variance'])
        output_df.to_csv(csv_filename, index=False)
        print(f"\nResults saved to '{csv_filename}'")
