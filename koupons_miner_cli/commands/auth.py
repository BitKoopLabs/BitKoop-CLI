"""
Authentication command for the Koupons CLI.
"""

import functools
from argparse import Namespace

from bittensor_wallet import Config, Wallet

from koupons_miner_cli.business import auth as auth_business
from koupons_miner_cli.utils.display import (
    display_panel,
    display_progress,
    print_error,
    print_success,
)


def auth_command(args: Namespace):
    """Start the authentication process"""
    display_panel(
        "Auth", "Starting Koupons authentication process...", border_style="blue"
    )

    # Extract wallet parameters from args
    wallet_name = getattr(args, "wallet.name", "default")
    wallet_hotkey = getattr(args, "wallet.hotkey", "default")
    wallet_path = getattr(args, "wallet.path", "~/.bittensor/wallets/")

    # Create wallet config
    wallet_config = Wallet(config=Config(wallet_name, wallet_hotkey, wallet_path))

    # Authenticate the user
    func = functools.partial(auth_business.authenticate_user, wallet_config)
    result = display_progress("Authenticating...", func)

    if "api_key" in result and result["api_key"]:
        print_success("Authentication successful!")
        print_success(f"API key: {result['api_key']}")
    else:
        print_error("Authentication failed!")
