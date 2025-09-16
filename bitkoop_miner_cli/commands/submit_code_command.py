"""
Submit code command for the bitkoop CLI.
"""

from argparse import Namespace

from bitkoop_miner_cli.business.submit_code_logic import (
    UserCancellationError,
    submit_coupon_code,
)
from bitkoop_miner_cli.utils.display import (
    CouponOperation,
    display_coupon_error,
    display_panel,
    display_table,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from bitkoop_miner_cli.utils.wallet import WalletManager


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

    total = stats.get("total_validators", 0)
    successful = stats.get("successful_submissions", 0)
    success_rate = stats.get("success_rate", 0)

    summary_lines.append(
        f"Validators: {successful}/{total} receive coupons with ({success_rate:.1f}% success rate for validation)"
    )

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
    site = args.site
    code = args.code
    expires_at = getattr(args, "expires_at", None)
    category = getattr(args, "category", None)
    restrictions = getattr(args, "restrictions", None)
    country_code = getattr(args, "country_code", None)
    product_url = getattr(args, "product_url", None)
    is_global = getattr(args, "is_global", None)
    max_validators = getattr(args, "max_validators", None)

    display_panel(
        "Submit Code", f"Submitting code for [bold]{site}[/bold]", border_style="green"
    )

    columns = [("Field", "cyan"), ("Value", "yellow")]
    rows = [
        ["Site", site],
        ["Code", code],
    ]

    if expires_at:
        rows.append(["Expires At", expires_at])
    if category:
        rows.append(["Category", category])
    if restrictions:
        rows.append(["Restrictions", truncate_text(restrictions)])
    if country_code:
        rows.append(["Country Code", country_code])
    if product_url:
        rows.append(["Product URL", truncate_text(product_url)])
    if is_global is not None:
        rows.append(["Global Coupon", format_global_status(is_global)])
    if max_validators:
        rows.append(["Max Validators", str(max_validators)])

    display_table("Code Submission Details", columns, rows)

    try:
        wallet_manager = WalletManager.from_args(args)
    except Exception as e:
        print_error(f"Failed to initialize wallet manager: {e}")
        return

    wallet_verification = wallet_manager.verify_wallet_access()
    if not wallet_verification["success"]:
        print_error(f"Wallet verification failed: {wallet_verification['error']}")
        return

    print_success(f"Submit started using wallet: {wallet_manager.hotkey_address}")

    try:
        result = submit_coupon_code(
            wallet_manager=wallet_manager,
            site=site,
            code=code,
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
            print_error(f"{error_message}")
        else:
            print_error(f"Validation error: {error_message}")
        return
    except UserCancellationError:
        print_info("Submission cancelled by user.")
        return
    except Exception as e:
        print_error(f"Submission failed with exception: {e}")
        return

    if result.get("success", False):
        print_success("✅  Coupon Successfully Submitted for Validation")

        if "multi_validator_stats" in result:
            stats = result["multi_validator_stats"]
            for line in format_stats_summary(stats):
                print_info(line)

        if result.get("message"):
            print_info(result["message"])

        if result.get("coupon"):
            print_info("Coupon data recorded in validator network")

    else:
        display_coupon_error(code, CouponOperation.SUBMIT, result)
        print_info(
            "💡 Tip: Check your wallet balance, code format, and network connectivity"
        )
