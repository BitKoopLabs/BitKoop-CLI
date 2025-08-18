"""
Delete code command for the BitKoop CLI.
"""

from argparse import Namespace

from bitkoop_miner_cli.business.delete_code_logic import delete_coupon_code
from bitkoop_miner_cli.business.submit_code_logic import UserCancellationError
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


def format_stats_summary(stats):
    """Format validator statistics for display."""
    if not stats:
        return []

    summary_lines = []

    total = stats.get("total_validators", 0)
    successful = stats.get("successful_submissions", 0)
    success_rate = stats.get("success_rate", 0)

    summary_lines.append(
        f"Validators: {successful}/{total} succeeded ({success_rate:.1f}% success rate)"
    )

    if stats.get("total_time"):
        summary_lines.append(f"Deletion time: {stats['total_time']:.2f}s")

    if stats.get("avg_response_time"):
        summary_lines.append(
            f"Average response time: {stats['avg_response_time']:.2f}s"
        )

    if stats.get("network"):
        summary_lines.append(f"Network: {stats['network']}")

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


def delete_code_command(args: Namespace):
    """Delete a coupon code from the validator network"""
    site = args.site
    code = args.code
    max_validators = getattr(args, "max_validators", None)

    display_panel(
        "Delete Code",
        f"Deleting code [bold]{code}[/bold] from [bold]{site}[/bold]",
        border_style="red",
    )

    columns = [("Field", "cyan"), ("Value", "yellow")]
    rows = [
        ["Site", site],
        ["Code", code],
    ]

    if max_validators:
        rows.append(["Max Validators", str(max_validators)])

    display_table("Code Deletion Details", columns, rows)

    try:
        wallet_manager = WalletManager.from_args(args)
    except Exception as e:
        print_error(f"Failed to initialize wallet manager: {e}")
        return

    wallet_verification = wallet_manager.verify_wallet_access()
    if not wallet_verification["success"]:
        print_error(f"Wallet verification failed: {wallet_verification['error']}")
        return

    print_success(f"Deletion starts using wallet: {wallet_manager.hotkey_address}")

    try:
        result = delete_coupon_code(
            wallet_manager=wallet_manager,
            site=site,
            code=code,
            max_validators=max_validators,
            confirm_callback=prompt_user_confirmation,
        )
    except ValueError as ve:
        error_message = str(ve)
        if "not found in supervisor" in error_message:
            print_error(f"❌ {error_message}")
        else:
            print_error(f"❌ Validation error: {error_message}")
        return
    except UserCancellationError:
        print_info("Deletion cancelled by user.")
        return
    except Exception as e:
        print_error(f"Deletion failed with exception: {e}")
        return

    if result.get("success", False):
        print_success("✅ Code deleted successfully!")

        if "multi_validator_stats" in result:
            stats = result["multi_validator_stats"]
            for line in format_stats_summary(stats):
                print_info(line)

        if "code_id" in result and result["code_id"]:
            print_success(f"Deleted Code ID: {result['code_id']}")

        if result.get("message"):
            print_info(result["message"])

    else:
        display_coupon_error(code, CouponOperation.DELETE, result)

        if "multi_validator_stats" in result:
            stats = result["multi_validator_stats"]
            successful = stats.get("successful_submissions", 0)
            total = stats.get("total_validators", 0)

            if successful > 0:
                print_warning(
                    f"⚠️  Partial success: {successful}/{total} validators accepted the deletion"
                )
            else:
                print_info(f"All {total} validators rejected the deletion")

            if stats.get("total_time"):
                print_info(f"Total attempt time: {stats['total_time']:.2f}s")

        print_info("💡 Tip: Check your wallet balance and network connectivity")
