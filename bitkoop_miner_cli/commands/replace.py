"""
Replace code command for the Koupons CLI.
"""

from bitkoop_miner_cli.business import codes as codes_business
from bitkoop_miner_cli.utils.display import (
    display_panel,
    display_table,
    print_error,
    print_success,
)
from bitkoop_miner_cli.utils.wallet import WalletManager


def replace_code_command(args):
    """Replace an existing code with a new one"""
    site = args.site
    old_code = args.old_code
    new_code = args.new_code

    display_panel(
        "Replace Code", f"Replacing code for [bold]{site}[/bold]", border_style="yellow"
    )

    # Create a table to display the replacement details
    columns = [("Field", "cyan"), ("Value", "yellow")]

    rows = [["Site", site], ["Old Code", old_code], ["New Code", new_code]]

    display_table("Code Replacement Details", columns, rows)

    # Create wallet manager from args
    wallet_manager = WalletManager.from_args(args)

    # Replace the code using the business logic function
    result = codes_business.replace_coupon_code(
        wallet_manager, site, old_code, new_code
    )

    if result["success"]:
        print_success("Code replaced successfully!")
    else:
        error_msg = result.get("error", "Unknown error occurred")
        print_error(f"Code replacement failed: {error_msg}")
