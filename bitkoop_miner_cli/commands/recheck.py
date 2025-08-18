"""
Recheck code command for the bitkoop CLI.
"""

import functools
from argparse import Namespace

from bitkoop_miner_cli.business.recheck_code_logic import recheck_coupon_code
from bitkoop_miner_cli.utils.display import (
    CouponOperation,
    display_coupon_error,
    display_panel,
    display_progress,
    print_error,
    print_info,
    print_success,
)
from bitkoop_miner_cli.utils.wallet import WalletManager


def display_success_stats(result: dict, code: str):
    """Display success statistics for recheck operation."""
    stats = result.get("multi_validator_stats", {})

    successful = stats.get("successful_submissions", 0)
    total = stats.get("total_validators", 0)
    success_rate = stats.get("success_rate", 0.0)

    display_panel(
        "Recheck Successful",
        f"Coupon '[bold]{code}[/bold]' successfully submitted to "
        f"{successful}/{total} validators for rechecking "
        f"([green]{success_rate:.1f}%[/green] success rate)",
        border_style="green",
    )


def recheck_code_command(args: Namespace):
    """Recheck a coupon code across the validator network."""
    site = args.site
    code = args.code
    max_validators = getattr(args, "max_validators", None)

    display_panel(
        "Recheck Code",
        f"Rechecking code '[bold]{code}[/bold]' for [bold]{site}[/bold]",
        border_style="blue",
    )

    try:
        wallet_manager = WalletManager.from_args(args)
    except Exception as e:
        print_error(f"Failed to initialize wallet manager: {e}")
        return

    wallet_verification = wallet_manager.verify_wallet_access()
    if not wallet_verification["success"]:
        print_error(f"Wallet verification failed: {wallet_verification['error']}")
        return

    print_success(f"Recheck started using wallet: {wallet_manager.hotkey_address}")

    func = functools.partial(
        recheck_coupon_code,
        wallet_manager,
        site,
        code,
        max_validators,
    )

    try:
        result = display_progress("Rechecking code...", func)
    except ValueError as ve:
        error_message = str(ve)
        if "not found in supervisor" in error_message:
            print_error(f"❌ {error_message}")
        else:
            print_error(f"❌ Validation error: {error_message}")
        return
    except Exception as e:
        print_error(f"Recheck failed with exception: {e}")
        return

    if result.get("success", False):
        display_success_stats(result, code)

        if result.get("message"):
            print_info(result["message"])
    else:
        display_coupon_error(code, CouponOperation.RECHECK, result)

        if "multi_validator_stats" in result:
            stats = result["multi_validator_stats"]
            successful = stats.get("successful_submissions", 0)
            total = stats.get("total_validators", 0)

            if successful > 0:
                print_info(
                    f"Partial success: {successful}/{total} validators accepted the recheck"
                )
            else:
                print_info(f"All {total} validators rejected the recheck")

            if stats.get("total_time"):
                print_info(f"Total recheck time: {stats['total_time']:.2f}s")

        print_info("💡 Tip: Check your code format and network connectivity")
