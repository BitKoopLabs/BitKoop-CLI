"""
My rank command for the Koupons CLI.
"""

from bitkoop_miner_cli.business import ranking as ranking_business
from bitkoop_miner_cli.utils.display import display_panel, display_table
from bitkoop_miner_cli.utils.formatting import format_rank_data


def my_rank_command(args):
    """Show current 7-day score, rank, and reward boost"""
    display_panel("My Rank", "Your Mining Statistics", border_style="green")

    # Get the rank information using the business logic function
    rank_data = ranking_business.get_my_rank()

    # Create a table to display the rank information
    columns = [("Metric", "cyan"), ("Value", "yellow")]

    # Format the rank data for display
    rows = format_rank_data(rank_data)

    display_table("Your Mining Statistics", columns, rows)
