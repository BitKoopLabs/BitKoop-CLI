"""Rank command for the BitKoop CLI - shows individual wallet rank."""

import logging
import sys

from bitkoop_miner_cli.utils.display import display_panel
from bitkoop_miner_cli.utils.supervisor_api_client import create_supervisor_client
from bitkoop_miner_cli.utils.wallet import WalletManager

logger = logging.getLogger(__name__)


def has_wallet_params() -> bool:
    """Check if wallet parameters are provided in command line"""
    return "--wallet.name" in sys.argv or "--wallet.hotkey" in sys.argv


def list_rank_command(args):
    if not hasattr(args, "wallet.name"):
        setattr(args, "wallet.name", "default")
    if not hasattr(args, "wallet.hotkey"):
        setattr(args, "wallet.hotkey", "default")

    wallet_name = getattr(args, "wallet.name", "default")
    hotkey_name = getattr(args, "wallet.hotkey", "default")

    try:
        wallet_manager = WalletManager.from_args_auto(args)
        if not wallet_manager.is_valid():
            raise ValueError("Invalid wallet")

        miner_hotkey = wallet_manager.hotkey_address
        if not miner_hotkey:
            raise ValueError("No hotkey address")

    except Exception as e:
        error_msg = str(e)
        if any(
            x in error_msg
            for x in ["FileNotFound", "does not exist", "Failed to get hotkey"]
        ):
            display_panel(
                "Wallet Not Found",
                f"Wallet not found. Please check that wallet.name '[red]{wallet_name}[/red]' "
                f"and wallet.hotkey '[red]{hotkey_name}[/red]' exist.",
                border_style="red",
            )
        else:
            display_panel(
                "Wallet Error",
                f"Failed to load wallet: [red]{error_msg}[/red]",
                border_style="red",
            )
        return

    try:
        with create_supervisor_client() as client:
            result = client.get_rank(
                miner_hotkey=miner_hotkey,
                sort_order="desc",
            )
            ranks = result.get("ranks", [])

        if not ranks:
            display_panel(
                "No Rankings Found",
                "No rankings available for your wallet",
                border_style="yellow",
            )
            return

        rank_info = ranks[0]
        content = f"""[bold]Position on Leaderboard:[/bold] #{rank_info.rank}
[bold]Total Points:[/bold] {rank_info.total_points:.0f}
[bold]Coupon Summary:[/bold]
  • Valid Coupons: [green]{rank_info.valid_count}[/green]
  • Expired/Invalid Coupons: [red]{rank_info.invalid_count}[/red]
  • Coupons Awaiting Approval: [yellow]{rank_info.pending_count}[/yellow]"""

        display_panel("My Rank", content, border_style="cyan")

    except Exception as error:
        display_panel(
            "Error",
            f"Failed to fetch rankings: [red]{str(error)}[/red]",
            border_style="red",
        )
