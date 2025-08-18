"""
Leaderboard command for the bitkoop CLI.
"""

from bitkoop_miner_cli.business import ranking as ranking_business
from bitkoop_miner_cli.utils.display import display_panel, display_table
from bitkoop_miner_cli.utils.formatting import format_leaderboard_data


def leaderboard_command(args):
    """Show ranks and scores of all miners"""
    display_panel("Leaderboard", "bitkoop Mining Leaderboard", border_style="blue")

    # Get the leaderboard data using the business logic function
    leaderboard_data = ranking_business.get_leaderboard()

    # Create a table to display the leaderboard
    columns = [
        ("Rank", "bold cyan"),
        ("Miner", "yellow"),
        ("7-Day Score", "green"),
        ("Total Score", "magenta"),
        ("Reward Boost", "blue"),
    ]

    # Format the leaderboard data for display
    rows = format_leaderboard_data(leaderboard_data)

    display_table("bitkoop Mining Leaderboard", columns, rows)
