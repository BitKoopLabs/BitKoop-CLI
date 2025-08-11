import functools
from argparse import Namespace

from koupons_miner_cli.business.recheck_code_logic import recheck_coupon_code
from koupons_miner_cli.utils.display import (
    display_panel,
    display_progress,
    print_error,
    print_info,
    print_success,
)
from koupons_miner_cli.utils.wallet import WalletManager


def display_success_stats(result: dict, code: str):
    stats = result["multi_validator_stats"]

    display_panel(
        "Recheck Successful",
        f"Coupon '[bold]{code}[/bold]' successfully submitted to "
        f"{stats['successful_submissions']}/{stats['total_validators']} validators for rechecking "
        f"([green]{stats['success_rate']:.1f}%[/green] success rate)",
        border_style="green",
    )


def recheck_code_command(args: Namespace):
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

    print_success(f"Using wallet: {wallet_manager.hotkey_address}")

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
            print_info("💡 Run 'bitkoop list-sites' to see available sites.")
        else:
            print_error(f"❌ Validation error: {error_message}")
        return
    except Exception as e:
        print_error(f"Recheck failed with exception: {e}")
        return

    if result.get("success", False):
        display_success_stats(result, code)
    else:
        error_msg = result.get("error", "Unknown error occurred")
        display_panel(
            "Recheck Failed",
            f"Code: {code}\nError: {error_msg}",
            border_style="red",
        )
