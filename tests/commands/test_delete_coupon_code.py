"""
Unit tests for the delete command.
"""

from argparse import Namespace
from unittest import mock

import pytest

from bitkoop_miner_cli.commands.delete import delete_code_command
from bitkoop_miner_cli.utils.wallet import WalletManager


class TestDeleteCommand:
    """Test delete command functionality."""

    @pytest.fixture
    def mock_args(self):
        """Create mock command arguments."""
        args = Namespace()
        args.site = "example.com"
        args.code = "TEST123"
        return args

    @pytest.fixture
    def alternative_args(self):
        """Create alternative mock command arguments."""
        args = Namespace()
        args.site = "different.com"
        args.code = "DIFF123"
        return args

    @pytest.fixture
    def common_mocks(self):
        """Setup common mocks used across multiple tests."""
        with mock.patch(
            "bitkoop_miner_cli.commands.delete.display_panel"
        ) as mock_display_panel, mock.patch(
            "bitkoop_miner_cli.commands.delete.display_table"
        ) as mock_display_table, mock.patch(
            "bitkoop_miner_cli.commands.delete.confirm_action"
        ) as mock_confirm_action, mock.patch(
            "bitkoop_miner_cli.commands.delete.print_success"
        ) as mock_print_success, mock.patch(
            "bitkoop_miner_cli.commands.delete.print_error"
        ) as mock_print_error, mock.patch(
            "bitkoop_miner_cli.commands.delete.print_warning"
        ) as mock_print_warning, mock.patch(
            "bitkoop_miner_cli.commands.delete.WalletManager"
        ) as mock_wallet_manager_class, mock.patch(
            "bitkoop_miner_cli.commands.delete.codes_business.delete_coupon_code"
        ) as mock_delete_coupon_code:
            # Setup wallet manager mock
            mock_wallet = mock.Mock(spec=WalletManager)
            mock_wallet_manager_class.return_value = mock_wallet

            yield {
                "display_panel": mock_display_panel,
                "display_table": mock_display_table,
                "confirm_action": mock_confirm_action,
                "print_success": mock_print_success,
                "print_error": mock_print_error,
                "print_warning": mock_print_warning,
                "wallet_manager_class": mock_wallet_manager_class,
                "delete_coupon_code": mock_delete_coupon_code,
                "wallet": mock_wallet,
            }

    def _assert_basic_display_calls(self, mocks, args):
        """Assert basic display calls are made correctly."""
        mocks["display_panel"].assert_any_call(
            "Delete Code",
            f"Deleting code for [bold]{args.site}[/bold]",
            border_style="red",
        )

        mocks["display_table"].assert_called_once_with(
            "Code Deletion Details",
            [("Field", "cyan"), ("Value", "yellow")],
            [["Site", args.site], ["Code", args.code]],
        )

    def _assert_confirmation_call(self, mocks, args):
        """Assert confirmation is called correctly."""
        mocks["confirm_action"].assert_called_once_with(
            f"Are you sure you want to delete code {args.code} for {args.site}?"
        )

    def _assert_business_logic_call(self, mocks, args):
        """Assert business logic is called correctly."""
        mocks["delete_coupon_code"].assert_called_once_with(
            wallet_manager=mocks["wallet"], site=args.site, code=args.code
        )

    def test_delete_success_with_full_response(self, mock_args, common_mocks):
        """Test successful code deletion with full server response."""
        # Setup confirmation and business logic mocks
        common_mocks["confirm_action"].return_value = True
        common_mocks["delete_coupon_code"].return_value = {
            "success": True,
            "message": "Code deleted successfully",
            "deleted_at": "2024-01-01T12:00:00Z",
        }

        # Call the command
        delete_code_command(mock_args)

        # Verify display calls
        self._assert_basic_display_calls(common_mocks, mock_args)
        self._assert_confirmation_call(common_mocks, mock_args)

        # Verify wallet manager creation and business logic call
        common_mocks["wallet_manager_class"].assert_called_once()
        self._assert_business_logic_call(common_mocks, mock_args)

        # Verify success messages
        common_mocks["print_success"].assert_any_call("Code deleted successfully!")
        common_mocks["print_success"].assert_any_call(
            "Deleted at: 2024-01-01T12:00:00Z"
        )

        # Verify server response display
        common_mocks["display_panel"].assert_any_call(
            "Server Response", "Code deleted successfully", border_style="green"
        )

        # Verify no error or warning messages
        common_mocks["print_error"].assert_not_called()
        common_mocks["print_warning"].assert_not_called()

    def test_delete_success_with_minimal_response(self, mock_args, common_mocks):
        """Test successful deletion with minimal response data."""
        # Setup confirmation and business logic mocks
        common_mocks["confirm_action"].return_value = True
        common_mocks["delete_coupon_code"].return_value = {"success": True}

        # Call the command
        delete_code_command(mock_args)

        # Verify success message
        common_mocks["print_success"].assert_called_once_with(
            "Code deleted successfully!"
        )

        # Verify no additional success messages or server response display
        success_calls = [
            str(call) for call in common_mocks["print_success"].call_args_list
        ]
        assert len(success_calls) == 1

        # Verify no server response panel (since no message)
        panel_calls = [
            call
            for call in common_mocks["display_panel"].call_args_list
            if call[0][0] == "Server Response"
        ]
        assert len(panel_calls) == 0

    def test_delete_cancelled(self, mock_args, common_mocks):
        """Test deletion when user cancels."""
        # Setup confirmation mock to return False
        common_mocks["confirm_action"].return_value = False

        # Call the command
        delete_code_command(mock_args)

        # Verify confirmation
        self._assert_confirmation_call(common_mocks, mock_args)

        # Verify warning message
        common_mocks["print_warning"].assert_called_once_with("Deletion cancelled.")

        # Verify no wallet manager creation or business logic call
        common_mocks["wallet_manager_class"].assert_not_called()
        common_mocks["delete_coupon_code"].assert_not_called()

    @pytest.mark.parametrize(
        "api_response,expected_error",
        [
            (
                {"success": False, "error": "Code not found"},
                "Code deletion failed: Code not found",
            ),
            ({"success": False}, "Code deletion failed: Unknown error occurred"),
        ],
    )
    def test_delete_api_failure(
        self, mock_args, common_mocks, api_response, expected_error
    ):
        """Test deletion with various API failure scenarios."""
        # Setup confirmation and business logic mocks
        common_mocks["confirm_action"].return_value = True
        common_mocks["delete_coupon_code"].return_value = api_response

        # Call the command
        delete_code_command(mock_args)

        # Verify error message
        common_mocks["print_error"].assert_called_once_with(expected_error)

    def test_delete_exception(self, mock_args, common_mocks):
        """Test deletion when exception occurs."""
        # Setup confirmation and business logic mocks
        common_mocks["confirm_action"].return_value = True
        common_mocks["delete_coupon_code"].side_effect = Exception("Network error")

        # Call the command
        delete_code_command(mock_args)

        # Verify error messages
        common_mocks["print_error"].assert_called_once_with(
            "Unexpected error: Network error"
        )

        # Verify error details panel
        common_mocks["display_panel"].assert_any_call(
            "Error Details", "[red]Network error[/red]", border_style="red"
        )

    def test_delete_with_different_site(self, alternative_args, common_mocks):
        """Test deletion with different site parameters."""
        # Setup confirmation and business logic mocks
        common_mocks["confirm_action"].return_value = True
        common_mocks["delete_coupon_code"].return_value = {"success": True}

        # Call the command
        delete_code_command(alternative_args)

        # Verify display calls with different site
        self._assert_basic_display_calls(common_mocks, alternative_args)
        self._assert_confirmation_call(common_mocks, alternative_args)
        self._assert_business_logic_call(common_mocks, alternative_args)
