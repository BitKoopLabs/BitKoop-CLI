"""
Wallet management utilities for the BitKoop CLI.
"""

import json
import time
from typing import Any, Optional, Union

from bittensor_wallet import Config, Wallet


class WalletManager:
    """Manages wallet operations for the BitKoop CLI."""

    def __init__(
        self,
        wallet_name: Optional[str] = None,
        wallet_hotkey: Optional[str] = None,
        wallet_path: str = "~/.bittensor/wallets/",
    ):
        """
        Initialize the wallet manager.

        Args:
            wallet_name: Name of the wallet (required for actual wallet operations)
            wallet_hotkey: Name of the hotkey (required for actual wallet operations)
            wallet_path: Path to the wallets directory
        """
        self.wallet_name = wallet_name
        self.wallet_hotkey = wallet_hotkey
        self.wallet_path = wallet_path
        self._wallet: Optional[Wallet] = None

    @property
    def wallet(self) -> Wallet:
        """Get the wallet instance, creating it if necessary."""
        if self._wallet is None:
            if not self.wallet_name or not self.wallet_hotkey:
                raise ValueError(
                    f"Wallet name and hotkey are required. "
                    f"Got wallet_name='{self.wallet_name}', wallet_hotkey='{self.wallet_hotkey}'"
                )

            self._wallet = Wallet(
                config=Config(self.wallet_name, self.wallet_hotkey, self.wallet_path)
            )
        return self._wallet

    @property
    def hotkey_address(self) -> str:
        """Get the SS58 address of the hotkey."""
        return self.wallet.hotkey.ss58_address

    def get_hotkey(self):
        """Get the hotkey object directly for signing operations."""
        return self.wallet.hotkey

    def is_valid(self) -> bool:
        """Check if this wallet manager has valid wallet credentials."""
        return bool(self.wallet_name and self.wallet_hotkey)

    def create_signature(self, data: Union[dict[str, Any], str]) -> str:
        """
        Create a signature for the given data using the wallet's hotkey.

        Args:
            data: Dictionary or string to sign

        Returns:
            Hex string signature
        """
        if isinstance(data, dict):
            message_to_sign = json.dumps(data, sort_keys=True, separators=(",", ":"))
        else:
            message_to_sign = str(data)

        signature = self.wallet.hotkey.sign(message_to_sign)

        return signature.hex()

    def verify_wallet_access(self) -> dict[str, Any]:
        """
        Verify that the wallet can be accessed and used for signing.

        Returns:
            Dictionary containing verification results
        """
        try:
            # Try to access the hotkey address
            hotkey_address = self.hotkey_address

            # Try to create a test signature
            test_data = {"test": "verification", "timestamp": int(time.time())}
            test_signature = self.create_signature(test_data)

            return {
                "success": True,
                "wallet_name": self.wallet_name,
                "hotkey_name": self.wallet_hotkey,
                "hotkey_address": hotkey_address,
                "test_signature": test_signature,
                "wallet_path": self.wallet_path,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "wallet_name": self.wallet_name,
                "hotkey_name": self.wallet_hotkey,
                "wallet_path": self.wallet_path,
            }

    def get_wallet_info(self) -> dict[str, Any]:
        """
        Get information about the current wallet.

        Returns:
            Dictionary containing wallet information
        """
        try:
            return {
                "success": True,
                "wallet_name": self.wallet_name,
                "hotkey_name": self.wallet_hotkey,
                "hotkey_address": self.hotkey_address,
                "wallet_path": self.wallet_path,
                "is_accessible": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "wallet_name": self.wallet_name,
                "hotkey_name": self.wallet_hotkey,
                "wallet_path": self.wallet_path,
                "is_accessible": False,
            }

    @classmethod
    def from_args(cls, args) -> "WalletManager":
        """
        Create a WalletManager from command line arguments.
        Accepts any wallet.name and wallet.hotkey values, including 'default'.

        Args:
            args: Namespace object from argparse

        Returns:
            WalletManager instance
        """
        wallet_name = None
        wallet_hotkey = None
        wallet_path = "~/.bittensor/wallets/"

        # Get wallet values from bittensor_wallet arguments
        wallet_name = getattr(args, "wallet.name", None)
        wallet_hotkey = getattr(args, "wallet.hotkey", None)
        wallet_path = getattr(args, "wallet.path", wallet_path)

        return cls(wallet_name, wallet_hotkey, wallet_path)

    @classmethod
    def from_args_auto(cls, args) -> "WalletManager":
        """
        Create a WalletManager from command line arguments.
        This is just an alias for from_args() now - no auto-detection.

        Args:
            args: Namespace object from argparse

        Returns:
            WalletManager instance
        """
        return cls.from_args(args)


def create_wallet_manager(
    wallet_name: Optional[str] = None,
    wallet_hotkey: Optional[str] = None,
    wallet_path: str = "~/.bittensor/wallets/",
) -> WalletManager:
    """
    Create a wallet manager instance.

    Args:
        wallet_name: Name of the wallet (required for actual operations)
        wallet_hotkey: Name of the hotkey (required for actual operations)
        wallet_path: Path to the wallets directory

    Returns:
        WalletManager instance
    """
    return WalletManager(wallet_name, wallet_hotkey, wallet_path)


def create_wallet_manager_from_args(args) -> WalletManager:
    """
    Create a wallet manager from command line arguments.

    Args:
        args: Namespace object from argparse

    Returns:
        WalletManager instance
    """
    return WalletManager.from_args_auto(args)
