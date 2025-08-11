"""
Unit tests for the submit command.
"""

from argparse import Namespace
from unittest import mock

import pytest

from koupons_miner_cli.commands.submit import submit_code_command
from koupons_miner_cli.utils.wallet import WalletManager


class TestSubmitCommand:
    """Test submit command functionality."""

    @pytest.fixture
    def mock_args(self):
        """Create mock command arguments."""
        args = Namespace()
        args.site = "example.com"
        args.code = "TEST123"
        args.discount = "10%"
        args.expires_at = "2024-12-31"
        args.category = "electronics"
        args.wallet_path = "/path/to/wallet"
        args.wallet_hotkey = "test_hotkey"
        return args

    @pytest.fixture
    def minimal_args(self):
        """Create minimal mock command arguments."""
        args = Namespace()
        args.site = "example.com"
        args.code = "TEST123"
        args.discount = None
        args.expires_at = None
        args.category = None
        args.wallet_path = "/path/to/wallet"
        args.wallet_hotkey = "test_hotkey"
        return args

    @pytest.fixture
    def common_mocks(self):
        """Setup common mocks used across multiple tests."""
        with mock.patch(
            "koupons_miner_cli.commands.submit.display_panel"
        ) as mock_display_panel, mock.patch(
            "koupons_miner_cli.commands.submit.display_table"
        ) as mock_display_table, mock.patch(
            "koupons_miner_cli.commands.submit.display_progress"
        ) as mock_display_progress, mock.patch(
            "koupons_miner_cli.commands.submit.print_success"
        ) as mock_print_success, mock.patch(
            "koupons_miner_cli.commands.submit.print_error"
        ) as mock_print_error, mock.patch(
            "koupons_miner_cli.commands.submit.WalletManager"
        ) as mock_wallet_manager_class:
            # Setup wallet manager mock with successful verification by default
            mock_wallet = mock.Mock(spec=WalletManager)
            mock_wallet.hotkey_address = "test_hotkey"
            mock_wallet.verify_wallet_access.return_value = {"success": True}
            mock_wallet_manager_class.from_args.return_value = mock_wallet

            yield {
                "display_panel": mock_display_panel,
                "display_table": mock_display_table,
                "display_progress": mock_display_progress,
                "print_success": mock_print_success,
                "print_error": mock_print_error,
                "wallet_manager_class": mock_wallet_manager_class,
                "wallet": mock_wallet,
            }

    def _assert_display_calls(self, mocks, args):
        """Assert display calls are made correctly."""
        mocks["display_panel"].assert_called_once_with(
            "Submit Code",
            f"Submitting code for [bold]{args.site}[/bold]",
            border_style="green",
        )

        expected_table_data = [
            ["Site", args.site],
            ["Code", args.code],
            ["Discount", args.discount or "N/A"],
            ["Expires At", args.expires_at or "N/A"],
            ["Category", args.category or "N/A"],
        ]

        mocks["display_table"].assert_called_once_with(
            "Code Submission Details",
            [("Field", "cyan"), ("Value", "yellow")],
            expected_table_data,
        )

    def _assert_wallet_operations(self, mocks, args):
        """Assert wallet operations are performed correctly."""
        mocks["wallet_manager_class"].from_args.assert_called_once_with(args)
        mocks["wallet"].verify_wallet_access.assert_called_once()

    def _assert_progress_display(self, mocks):
        """Assert progress display is called correctly."""
        mocks["display_progress"].assert_called_once()
        progress_args = mocks["display_progress"].call_args[0]
        assert progress_args[0] == "Submitting code..."

    def test_submit_success_with_full_response(self, mock_args, common_mocks):
        """Test successful code submission with full response data."""
        # Setup display_progress mock to return success with full data
        common_mocks["display_progress"].return_value = {
            "success": True,
            "code_id": "example.com_TEST123",
            "message": "Code submitted successfully",
        }

        # Call the command
        submit_code_command(mock_args)

        # Verify all display and wallet operations
        self._assert_display_calls(common_mocks, mock_args)
        self._assert_wallet_operations(common_mocks, mock_args)
        self._assert_progress_display(common_mocks)

        # Verify success messages
        common_mocks["print_success"].assert_any_call("Using wallet: test_hotkey")
        common_mocks["print_success"].assert_any_call("Code submitted successfully!")
        common_mocks["print_success"].assert_any_call("Code ID: example.com_TEST123")

        # Verify no error messages
        common_mocks["print_error"].assert_not_called()

    def test_submit_success_without_code_id(self, mock_args, common_mocks):
        """Test successful submission without code_id in response."""
        # Setup display_progress mock to return success without code_id
        common_mocks["display_progress"].return_value = {
            "success": True,
            "message": "Code submitted successfully",
        }

        # Call the command
        submit_code_command(mock_args)

        # Verify success messages without code_id
        common_mocks["print_success"].assert_any_call("Using wallet: test_hotkey")
        common_mocks["print_success"].assert_any_call("Code submitted successfully!")

        # Verify no code_id message
        code_id_calls = [
            call
            for call in common_mocks["print_success"].call_args_list
            if "Code ID:" in str(call)
        ]
        assert len(code_id_calls) == 0

        # Verify no error messages
        common_mocks["print_error"].assert_not_called()

    def test_submit_with_minimal_args(self, minimal_args, common_mocks):
        """Test submission with minimal arguments."""
        # Setup display_progress mock to return success
        common_mocks["display_progress"].return_value = {"success": True}

        # Call the command
        submit_code_command(minimal_args)

        # Verify display calls with N/A values
        self._assert_display_calls(common_mocks, minimal_args)

    def test_submit_wallet_verification_failed(self, mock_args, common_mocks):
        """Test submission with wallet verification failure."""
        # Setup wallet verification failure
        common_mocks["wallet"].verify_wallet_access.return_value = {
            "success": False,
            "error": "Wallet not found",
        }

        # Call the command
        submit_code_command(mock_args)

        # Verify error message
        common_mocks["print_error"].assert_called_once_with(
            "Wallet verification failed: Wallet not found"
        )

        # Verify no success messages
        common_mocks["print_success"].assert_not_called()

    @pytest.mark.parametrize(
        "submission_response,expected_error",
        [
            (
                {"success": False, "error": "Code already exists"},
                "Code submission failed: Code already exists",
            ),
            ({"success": False}, "Code submission failed!"),
        ],
    )
    def test_submit_failure_scenarios(
        self, mock_args, common_mocks, submission_response, expected_error
    ):
        """Test various submission failure scenarios."""
        # Setup display_progress mock to return failure
        common_mocks["display_progress"].return_value = submission_response

        # Call the command
        submit_code_command(mock_args)

        # Verify error message
        common_mocks["print_error"].assert_called_with(expected_error)

        # Verify wallet success message but no submission success
        common_mocks["print_success"].assert_called_once_with(
            "Using wallet: test_hotkey"
        )
