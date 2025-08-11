"""
Unit tests for the replace command.
"""

from argparse import Namespace
from unittest import mock

import pytest

from koupons_miner_cli.commands.replace import replace_code_command
from koupons_miner_cli.utils.wallet import WalletManager


class TestReplaceCommand:
    """Test replace command functionality."""

    @pytest.fixture
    def mock_args(self):
        """Create mock command arguments."""
        args = Namespace()
        args.site = "example.com"
        args.old_code = "OLD123"
        args.new_code = "NEW123"
        args.wallet_path = "/path/to/wallet"
        args.wallet_hotkey = "test_hotkey"
        return args

    @pytest.fixture
    def alternative_args(self):
        """Create alternative mock command arguments."""
        args = Namespace()
        args.site = "different.com"
        args.old_code = "DIFF123"
        args.new_code = "NEWDIFF123"
        args.wallet_path = "/path/to/wallet"
        args.wallet_hotkey = "test_hotkey"
        return args

    @pytest.fixture
    def common_mocks(self):
        """Setup common mocks used across multiple tests."""
        with mock.patch(
            "koupons_miner_cli.commands.replace.display_panel"
        ) as mock_display_panel, mock.patch(
            "koupons_miner_cli.commands.replace.display_table"
        ) as mock_display_table, mock.patch(
            "koupons_miner_cli.commands.replace.print_success"
        ) as mock_print_success, mock.patch(
            "koupons_miner_cli.commands.replace.print_error"
        ) as mock_print_error, mock.patch(
            "koupons_miner_cli.commands.replace.WalletManager"
        ) as mock_wallet_manager_class, mock.patch(
            "koupons_miner_cli.commands.replace.codes_business.replace_coupon_code"
        ) as mock_replace_coupon_code:
            # Setup wallet manager mock
            mock_wallet = mock.Mock(spec=WalletManager)
            mock_wallet_manager_class.from_args.return_value = mock_wallet

            yield {
                "display_panel": mock_display_panel,
                "display_table": mock_display_table,
                "print_success": mock_print_success,
                "print_error": mock_print_error,
                "wallet_manager_class": mock_wallet_manager_class,
                "replace_coupon_code": mock_replace_coupon_code,
                "wallet": mock_wallet,
            }

    def _assert_display_calls(self, mocks, args):
        """Assert display calls are made correctly."""
        mocks["display_panel"].assert_called_once_with(
            "Replace Code",
            f"Replacing code for [bold]{args.site}[/bold]",
            border_style="yellow",
        )

        mocks["display_table"].assert_called_once_with(
            "Code Replacement Details",
            [("Field", "cyan"), ("Value", "yellow")],
            [
                ["Site", args.site],
                ["Old Code", args.old_code],
                ["New Code", args.new_code],
            ],
        )

    def _assert_wallet_operations(self, mocks, args):
        """Assert wallet operations are performed correctly."""
        mocks["wallet_manager_class"].from_args.assert_called_once_with(args)

    def _assert_business_logic_call(self, mocks, args):
        """Assert business logic is called correctly."""
        mocks["replace_coupon_code"].assert_called_once_with(
            mocks["wallet"], args.site, args.old_code, args.new_code
        )

    def test_replace_success(self, mock_args, common_mocks):
        """Test successful code replacement."""
        # Setup business logic mock to return success
        common_mocks["replace_coupon_code"].return_value = {
            "success": True,
            "message": "Code replaced successfully",
        }

        # Call the command
        replace_code_command(mock_args)

        # Verify all operations
        self._assert_display_calls(common_mocks, mock_args)
        self._assert_wallet_operations(common_mocks, mock_args)
        self._assert_business_logic_call(common_mocks, mock_args)

        # Verify success message
        common_mocks["print_success"].assert_called_once_with(
            "Code replaced successfully!"
        )

        # Verify no error messages
        common_mocks["print_error"].assert_not_called()

    @pytest.mark.parametrize(
        "api_response,expected_error",
        [
            (
                {"success": False, "error": "Old code not found"},
                "Code replacement failed: Old code not found",
            ),
            ({"success": False}, "Code replacement failed: Unknown error occurred"),
        ],
    )
    def test_replace_failure(
        self, mock_args, common_mocks, api_response, expected_error
    ):
        """Test replacement failure scenarios."""
        # Setup business logic mock to return failure
        common_mocks["replace_coupon_code"].return_value = api_response

        # Call the command
        replace_code_command(mock_args)

        # Verify error message
        common_mocks["print_error"].assert_called_once_with(expected_error)

        # Verify no success messages
        common_mocks["print_success"].assert_not_called()

    def test_replace_with_different_site(self, alternative_args, common_mocks):
        """Test replacement with different site parameters."""
        # Setup business logic mock to return success
        common_mocks["replace_coupon_code"].return_value = {"success": True}

        # Call the command
        replace_code_command(alternative_args)

        # Verify display calls with different site
        self._assert_display_calls(common_mocks, alternative_args)

        # Verify business logic call with different parameters
        self._assert_business_logic_call(common_mocks, alternative_args)
