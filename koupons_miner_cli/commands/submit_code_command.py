"""
Submit code command for the Koupons CLI.
"""

from argparse import Namespace

from koupons_miner_cli.business.submit_code_logic import (
    UserCancellationError,
    submit_coupon_code,
)
from koupons_miner_cli.utils.display import (
    display_panel,
    display_table,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from koupons_miner_cli.utils.wallet import WalletManager


def format_global_status(is_global_val):
    """Format the global status for display."""
    if is_global_val is True:
        return "Yes"
    elif is_global_val is False:
        return "No (Local)"
    else:
        return "N/A (Auto-detect)"


def truncate_text(text, max_length=50):
    """Truncate text for display if too long."""
    if not text:
        return "N/A"
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_stats_summary(stats):
    """Format validator statistics for display."""
    if not stats:
        return []

    summary_lines = []

    # Main success stats
    total = stats.get("total_validators", 0)
    successful = stats.get("successful_submissions", 0)
    success_rate = stats.get("success_rate", 0)

    summary_lines.append(
        f"Validators: {successful}/{total} receive coupons with ({success_rate:.1f}% success rate for validation)"
    )

    # Timing info
    if stats.get("total_time"):
        summary_lines.append(f"Submission time: {stats['total_time']:.2f}s")

    return summary_lines


def prompt_user_confirmation(message):
    """
    Prompt the user for confirmation with a yes/no question.

    Args:
        message: The message to display to the user

    Returns:
        bool: True if the user confirms, False otherwise
    """
    while True:
        response = input(f"{message} (y/n): ").strip().lower()
        if response in ["y", "yes"]:
            return True
        elif response in ["n", "no"]:
            return False
        else:
            print_warning("Please enter 'y' or 'n'")


def submit_code_command(args: Namespace):
    """Submit a new coupon code using wallet signature authentication"""
    # Extract arguments
    site = args.site
    code = args.code
    discount = args.discount
    expires_at = args.expires_at
    category = args.category
    restrictions = getattr(args, "restrictions", None)
    country_code = getattr(args, "country_code", None)
    product_url = getattr(args, "product_url", None)
    is_global = getattr(args, "is_global", None)
    max_validators = getattr(args, "max_validators", None)

    # Display submission header
    display_panel(
        "Submit Code", f"Submitting code for [bold]{site}[/bold]", border_style="green"
    )

    # Build details table
    columns = [("Field", "cyan"), ("Value", "yellow")]
    rows = [
        ["Site", site],
        ["Code", code],
        ["Discount", discount or "N/A"],
        ["Expires At", expires_at or "N/A"],
        ["Category", category or "N/A"],
        ["Restrictions", truncate_text(restrictions)],
        ["Country Code", country_code or "N/A"],
        ["Product URL", truncate_text(product_url)],
        ["Global Coupon", format_global_status(is_global)],
    ]

    # Add max validators if specified
    if max_validators:
        rows.append(["Max Validators", str(max_validators)])

    display_table("Code Submission Details", columns, rows)

    # Initialize wallet manager
    try:
        wallet_manager = WalletManager.from_args(args)
    except Exception as e:
        print_error(f"Failed to initialize wallet manager: {e}")
        return

    # Verify wallet access
    wallet_verification = wallet_manager.verify_wallet_access()
    if not wallet_verification["success"]:
        print_error(f"Wallet verification failed: {wallet_verification['error']}")
        return

    print_success(f"Using wallet: {wallet_manager.hotkey_address}")

    # Execute the submission with proper validation and confirmation handling
    try:
        # This function handles all validation including category validation
        # and prompts for confirmation outside of the progress display
        result = submit_coupon_code(
            wallet_manager=wallet_manager,
            site=site,
            code=code,
            discount=discount,
            expires_at=expires_at,
            category=category,
            restrictions=restrictions,
            country_code=country_code,
            product_url=product_url,
            is_global=is_global,
            max_validators=max_validators,
            confirm_callback=prompt_user_confirmation,
        )
    except ValueError as ve:
        error_message = str(ve)
        if "not found in supervisor" in error_message:
            print_error(f"❌ {error_message}")
            print_info("💡 Run 'koupons list-sites' to see available sites.")
        else:
            print_error(f"❌ Validation error: {error_message}")
        return
    except UserCancellationError:
        print_info("Submission cancelled by user.")
        return
    except Exception as e:
        print_error(f"Submission failed with exception: {e}")
        return

    # Handle results
    if result.get("success", False):
        print_success("✅  Coupon Successfully Submitted for Validation")

        # Display validator statistics
        if "multi_validator_stats" in result:
            stats = result["multi_validator_stats"]
            for line in format_stats_summary(stats):
                print_info(line)

        # Display additional message
        if result.get("message"):
            print_info(result["message"])

        # Show coupon data if available
        if result.get("coupon"):
            print_info("Coupon data recorded in validator network")

    else:
        # Get the error message - use direct error message from result
        error_msg = result.get("error", "Unknown error occurred")

        display_panel(
            "❌ Submission Failed",
            f"Failed to submit coupon '[bold]{code}[/bold]': [red]{error_msg}[/red]",
            border_style="red",
        )

        print_info(
            "💡 Tip: Check your wallet balance, code format, and network connectivity"
        )
