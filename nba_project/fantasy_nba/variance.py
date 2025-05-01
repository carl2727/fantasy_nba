# fantasy_nba/variance.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
import pandas as pd
from fantasy_nba.ratings import categories, stats

def calculate_total_variance_per_category(df, categories):
    """
    Calculates the summed variance of each player per category across the entire season.

    Args:
        df (pd.DataFrame): The DataFrame containing player statistics.
                           It should include a unique player identification column (e.g., 'PLAYER_ID')
                           and the columns for the various categories.
        categories (list): A list of the categories (column names) for which the variance
                           should be calculated.

    Returns:
        dict: A dictionary where the keys are the categories and the values are the
              summed variance of all players in that category.
    """
    total_variance_per_category = {}

    # Ensure the player ID column exists
    if 'PLAYER_ID' not in df.columns:
        raise ValueError("The DataFrame requires a 'PLAYER_ID' column to identify players.")

    for category in categories:
        if category not in df.columns:
            print(f"Warning: Category '{category}' not found in the DataFrame. Skipping.")
            continue

        # Group the DataFrame by player ID
        grouped_by_player = df.groupby('PLAYER_ID')

        # Calculate the variance for each player in the current category
        player_variances = grouped_by_player[category].var(ddof=0) # ddof=0 for population variance

        # Sum the variances of all players for this category
        total_variance_for_category = player_variances.sum()
        total_variance_per_category[category] = total_variance_for_category

    return total_variance_per_category

if __name__ == '__main__':
    from .ratings import stats, categories

    if stats is not None and categories is not None:
        variance_results = calculate_total_variance_per_category(stats, categories)

        output_choice = input("Choose output method ('screen' or 'csv'): ").lower()

        if output_choice == 'screen':
            print("\nSummed variance per category (across all players):")
            for category, total_variance in variance_results.items():
                print(f"- {category}: {total_variance:.4f}")
        elif output_choice == 'csv':
            csv_filename = 'total_variance_per_category.csv'
            output_df = pd.DataFrame(list(variance_results.items()), columns=['Category', 'Total Variance'])
            output_df.to_csv(csv_filename, index=False)
            print(f"\nResults saved to '{csv_filename}'")
        else:
            print("Invalid output choice. Please enter 'screen' or 'csv'.")
    else:
        print("Error: 'stats' DataFrame or 'categories' list not found.")