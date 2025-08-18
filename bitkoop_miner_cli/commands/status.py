"""
View status command for the bitkoop CLI.
"""

from bitkoop_miner_cli.business import status as status_business
from bitkoop_miner_cli.utils.display import display_panel, display_table
from bitkoop_miner_cli.utils.formatting import format_status_data


def view_status_command(args):
    """View live status and discount % of validated codes"""
    site = args.site

    display_panel(
        "View Status", f"Viewing status for [bold]{site}[/bold]", border_style="blue"
    )

    # Get the status using the business logic function
    status_data = status_business.get_coupon_status(site)

    # Create a table to display the status
    columns = [
        ("Code", "cyan"),
        ("Site", "blue"),
        ("Discount", "yellow"),
        ("Status", "bold"),
        ("Last Validated", "magenta"),
    ]

    # Format the status data for display
    rows = [format_status_data(status) for status in status_data]

    display_table(f"Status for {site}", columns, rows)
