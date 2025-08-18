"""
Unit tests for the view command.
"""

from argparse import Namespace
from unittest import mock

import pytest

from bitkoop_miner_cli.commands.view import (
    view_codes_command,
    view_codes_command_with_options,
)
from bitkoop_miner_cli.utils.wallet import WalletManager


class TestViewCommand:
    """Test view command functionality."""

    @pytest.fixture
    def mock_args(self):
        """Create mock command arguments."""
        args = Namespace()
        args.site = "example.com"
        args.category = "electronics"
        args.active_only = True
        args.limit = 50
        args.offset = 10
        return args

    @pytest.fixture
    def minimal_args(self):
        """Create minimal mock command arguments."""
        args = Namespace()
        args.site = "example.com"
        return args

    @pytest.fixture
    def pagination_args(self):
        """Create pagination mock command arguments."""
        args = Namespace()
        args.site = "example.com"
        args.limit = 2
        return args

    @pytest.fixture
    def sample_codes(self):
        """Create sample code data."""
        return [
            {
                "code": "TEST123",
                "site": "example.com",
                "discount": "10%",
                "expires_at": "2024-12-31T23:59:59Z",
                "category": "electronics",
                "status": "Active",
                "created_at": "2024-01-01T00:00:00Z",
                "miner_hotkey": "test_hotkey",
            },
            {
                "code": "SAVE20",
                "site": "example.com",
                "discount": "20%",
                "expires_at": "2024-11-30T23:59:59Z",
                "category": "electronics",
                "status": "Active",
                "created_at": "2024-01-02T00:00:00Z",
                "miner_hotkey": "test_hotkey",
            },
        ]

    @pytest.fixture
    def common_mocks(self):
        """Setup common mocks used across multiple tests."""
        with mock.patch(
            "bitkoop_miner_cli.commands.view.display_panel"
        ) as mock_display_panel, mock.patch(
            "bitkoop_miner_cli.commands.view.display_table"
        ) as mock_display_table, mock.patch(
            "bitkoop_miner_cli.commands.view.WalletManager"
        ) as mock_wallet_manager_class, mock.patch(
            "bitkoop_miner_cli.commands.view.codes_business.get_coupon_codes"
        ) as mock_get_coupon_codes, mock.patch(
            "bitkoop_miner_cli.commands.view.format_code_data"
        ) as mock_format_code_data:
            # Setup wallet manager mock
            mock_wallet = mock.Mock(spec=WalletManager)
            mock_wallet_manager_class.return_value = mock_wallet

            yield {
                "display_panel": mock_display_panel,
                "display_table": mock_display_table,
                "wallet_manager_class": mock_wallet_manager_class,
                "get_coupon_codes": mock_get_coupon_codes,
                "format_code_data": mock_format_code_data,
                "wallet": mock_wallet,
            }

    def _setup_format_code_data_mock(self, mocks):
        """Setup format_code_data mock to return expected data."""
        mocks["format_code_data"].side_effect = lambda x: [
            x["code"],
            x["site"],
            x["discount"],
            x["expires_at"],
            x["category"],
            x["status"],
        ]

    def _assert_basic_display_call(self, mocks, site):
        """Assert basic display panel call is made correctly."""
        mocks["display_panel"].assert_any_call(
            "View Codes", f"Viewing codes for [bold]{site}[/bold]", border_style="blue"
        )

    def _assert_business_logic_call(self, mocks, args):
        """Assert business logic is called with correct parameters."""
        expected_params = {
            "wallet_manager": mocks["wallet"],
            "site": args.site,
            "category": getattr(args, "category", None),
            "active_only": getattr(args, "active_only", True),
            "limit": getattr(args, "limit", 100),
            "offset": getattr(args, "offset", 0),
        }
        mocks["get_coupon_codes"].assert_called_once_with(**expected_params)

    def _assert_table_display(self, mocks, site, codes_data):
        """Assert table display is called correctly."""
        mocks["display_table"].assert_called_once_with(
            f"Codes for {site}",
            [
                ("Code", "cyan"),
                ("Site", "blue"),
                ("Discount", "yellow"),
                ("Expires At", "magenta"),
                ("Category", "green"),
                ("Status", "bold"),
            ],
            codes_data,
        )

    def test_view_success(self, mock_args, common_mocks, sample_codes):
        """Test successful code viewing."""
        # Setup mocks
        common_mocks["get_coupon_codes"].return_value = sample_codes
        self._setup_format_code_data_mock(common_mocks)

        # Call the command
        view_codes_command(mock_args)

        # Verify operations
        self._assert_basic_display_call(common_mocks, "example.com")
        common_mocks["wallet_manager_class"].assert_called_once()
        self._assert_business_logic_call(common_mocks, mock_args)

        # Verify table display with expected data
        expected_table_data = [
            [
                "TEST123",
                "example.com",
                "10%",
                "2024-12-31T23:59:59Z",
                "electronics",
                "Active",
            ],
            [
                "SAVE20",
                "example.com",
                "20%",
                "2024-11-30T23:59:59Z",
                "electronics",
                "Active",
            ],
        ]
        self._assert_table_display(common_mocks, "example.com", expected_table_data)

        # Verify format_code_data was called for each code
        assert common_mocks["format_code_data"].call_count == 2

    def test_view_no_codes(self, mock_args, common_mocks):
        """Test viewing when no codes found."""
        # Setup mocks
        common_mocks["get_coupon_codes"].return_value = []

        # Call the command
        view_codes_command(mock_args)

        # Verify display calls
        self._assert_basic_display_call(common_mocks, "example.com")
        common_mocks["display_panel"].assert_any_call(
            "No Codes Found",
            "No codes found for [bold]example.com[/bold]",
            border_style="yellow",
        )

        # Verify no table display
        common_mocks["display_table"].assert_not_called()

    def test_view_minimal_args(self, minimal_args, common_mocks):
        """Test viewing with minimal arguments."""
        # Setup mocks
        common_mocks["get_coupon_codes"].return_value = []

        # Call the command
        view_codes_command(minimal_args)

        # Verify business logic call with default values
        self._assert_business_logic_call(common_mocks, minimal_args)

    def test_view_pagination(self, pagination_args, common_mocks):
        """Test viewing with pagination."""
        # Setup mocks
        common_mocks["get_coupon_codes"].return_value = [
            {"code": "TEST1"},
            {"code": "TEST2"},
        ]
        common_mocks["format_code_data"].side_effect = lambda x: [
            x["code"],
            "",
            "",
            "",
            "",
            "",
        ]

        # Call the command
        view_codes_command(pagination_args)

        # Verify pagination message is displayed
        common_mocks["display_panel"].assert_any_call(
            "Pagination",
            "Showing 2 codes. Use --limit and --offset for more results.",
            border_style="dim",
        )

    def test_view_exception(self, mock_args, common_mocks):
        """Test viewing when exception occurs."""
        # Setup mocks
        common_mocks["get_coupon_codes"].side_effect = Exception("Network error")

        # Call the command
        view_codes_command(mock_args)

        # Verify error display
        common_mocks["display_panel"].assert_any_call(
            "Error",
            "Failed to fetch codes: [red]Network error[/red]",
            border_style="red",
        )


class TestViewCommandWithOptions:
    """Test view command with options functionality."""

    @pytest.fixture
    def mock_args(self):
        """Create mock command arguments."""
        args = Namespace()
        args.site = "example.com"
        args.category = "electronics"
        args.active_only = False
        args.limit = 50
        args.offset = 10
        return args

    @pytest.fixture
    def no_filters_args(self):
        """Create args with no filters."""
        args = Namespace()
        args.site = "example.com"
        args.category = None
        args.active_only = True
        args.limit = 100
        args.offset = 0
        return args

    @pytest.fixture
    def common_mocks(self):
        """Setup common mocks used across multiple tests."""
        with mock.patch(
            "bitkoop_miner_cli.commands.view.display_panel"
        ) as mock_display_panel, mock.patch(
            "bitkoop_miner_cli.commands.view.display_table"
        ) as mock_display_table, mock.patch(
            "bitkoop_miner_cli.commands.view.WalletManager"
        ) as mock_wallet_manager_class, mock.patch(
            "bitkoop_miner_cli.commands.view.codes_business.get_coupon_codes"
        ) as mock_get_coupon_codes, mock.patch(
            "bitkoop_miner_cli.commands.view.format_code_data"
        ) as mock_format_code_data:
            # Setup wallet manager mock
            mock_wallet = mock.Mock(spec=WalletManager)
            mock_wallet_manager_class.return_value = mock_wallet

            yield {
                "display_panel": mock_display_panel,
                "display_table": mock_display_table,
                "wallet_manager_class": mock_wallet_manager_class,
                "get_coupon_codes": mock_get_coupon_codes,
                "format_code_data": mock_format_code_data,
                "wallet": mock_wallet,
            }

    def _assert_display_call_with_filters(self, mocks, site, has_filters=True):
        """Assert display panel call with appropriate filter text."""
        if has_filters:
            expected_text = f"Viewing codes for [bold]{site}[/bold] (category: electronics, including expired)"
        else:
            expected_text = f"Viewing codes for [bold]{site}[/bold]"

        mocks["display_panel"].assert_any_call(
            "View Codes", expected_text, border_style="blue"
        )

    def test_view_with_options_success(self, mock_args, common_mocks):
        """Test successful viewing with options."""
        # Setup mocks
        common_mocks["get_coupon_codes"].return_value = [{"code": "TEST123"}]
        common_mocks["format_code_data"].return_value = [
            "TEST123",
            "example.com",
            "10%",
            "",
            "electronics",
            "Active",
        ]

        # Call the command
        view_codes_command_with_options(mock_args)

        # Verify display calls with filter text
        self._assert_display_call_with_filters(
            common_mocks, "example.com", has_filters=True
        )

        # Verify results display
        common_mocks["display_panel"].assert_any_call(
            "Results",
            "Showing codes 11-11. Use --limit and --offset for pagination.",
            border_style="dim",
        )

    def test_view_with_options_no_filters(self, no_filters_args, common_mocks):
        """Test viewing with options but no filters."""
        # Setup mocks
        common_mocks["get_coupon_codes"].return_value = []

        # Call the command
        view_codes_command_with_options(no_filters_args)

        # Verify display calls without filter text
        self._assert_display_call_with_filters(
            common_mocks, "example.com", has_filters=False
        )
        common_mocks["display_panel"].assert_any_call(
            "No Codes Found",
            "No codes found for [bold]example.com[/bold]",
            border_style="yellow",
        )

    def test_view_with_options_exception(self, mock_args, common_mocks):
        """Test viewing with options when exception occurs."""
        # Setup mocks
        common_mocks["get_coupon_codes"].side_effect = Exception("Database error")

        # Call the command
        view_codes_command_with_options(mock_args)

        # Verify error display
        common_mocks["display_panel"].assert_any_call(
            "Error",
            "Failed to fetch codes: [red]Database error[/red]",
            border_style="red",
        )
