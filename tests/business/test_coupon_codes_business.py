"""
Unit tests for the codes business logic module.
"""

from datetime import datetime, timezone
from unittest import mock

import pytest
import requests

from koupons_miner_cli.business import codes as codes_business
from koupons_miner_cli.utils.wallet import WalletManager


class TestHelperFunctions:
    """Test helper functions in codes business logic."""

    @pytest.mark.parametrize(
        "response_data,expected",
        [
            ({"message": "Test error"}, "Test error"),
            ({"detail": "Test detail"}, "Test detail"),
            ({"error": "Test error"}, "Test error"),
            ({"custom": "error"}, "Backend returned error 400: {'custom': 'error'}"),
        ],
    )
    def test_extract_backend_error_message(self, response_data, expected):
        """Test extracting error message from various response formats."""
        mock_response = mock.Mock()
        mock_response.json.return_value = response_data
        mock_response.status_code = 400

        result = codes_business._extract_backend_error_message(mock_response)
        assert result == expected

    def test_extract_backend_error_message_json_error(self):
        """Test error message extraction when JSON parsing fails."""
        mock_response = mock.Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.status_code = 400
        mock_response.text = "Invalid response"

        result = codes_business._extract_backend_error_message(mock_response)
        assert result == "Backend returned error 400: Invalid response"

    @pytest.mark.parametrize(
        "input_url,expected",
        [
            ("https://example.com", "https://example.com"),
            ("http://example.com", "http://example.com"),
            ("example.com", "https://example.com"),
            ("", "https://localhost.com"),
            ("/", "https://localhost.com"),
            (None, "https://localhost.com"),
        ],
    )
    def test_normalize_site_url(self, input_url, expected):
        """Test site URL normalization with various inputs."""
        result = codes_business._normalize_site_url(input_url)
        assert result == expected

    def test_create_authenticated_headers(self):
        """Test creation of authenticated headers."""
        mock_wallet = mock.Mock(spec=WalletManager)
        mock_wallet.hotkey_address = "test_hotkey"
        mock_wallet.create_signature.return_value = "test_signature"

        payload = {"test": "data"}

        result = codes_business._create_authenticated_headers(mock_wallet, payload)

        assert result == {
            "X-Signature": "test_signature",
            "X-Hotkey": "test_hotkey",
        }

        mock_wallet.create_signature.assert_called_once_with(
            {"hotkey": "test_hotkey", "test": "data"}
        )


class TestAPIOperations:
    """Test API operations with common patterns."""

    @pytest.fixture
    def mock_wallet(self):
        """Create a mock wallet manager."""
        wallet = mock.Mock(spec=WalletManager)
        wallet.hotkey_address = "test_hotkey"
        wallet.create_signature.return_value = "test_signature"
        return wallet

    @pytest.fixture
    def success_response(self):
        """Create a successful API response."""
        response = mock.Mock()
        response.ok = True
        response.json.return_value = {"message": "Success"}
        return response

    @pytest.fixture
    def error_response(self):
        """Create an error API response."""
        response = mock.Mock()
        response.ok = False
        response.status_code = 400
        response.json.return_value = {"message": "API Error"}
        return response

    def _assert_authenticated_request(
        self, mock_request, expected_url, expected_data=None
    ):
        """Assert that request was made with proper authentication."""
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args

        assert args[0] == expected_url
        assert kwargs["headers"]["X-Signature"] == "test_signature"
        assert kwargs["headers"]["X-Hotkey"] == "test_hotkey"

        if expected_data:
            assert kwargs["json"] == expected_data

    @mock.patch("koupons_miner_cli.business.codes.requests.post")
    def test_submit_coupon_code_success(self, mock_post, mock_wallet, success_response):
        """Test successful coupon code submission."""
        success_response.json.return_value = {
            "message": "Success",
            "coupon": {"id": 1, "code": "TEST123"},
        }
        mock_post.return_value = success_response

        result = codes_business.submit_coupon_code(
            mock_wallet, "example.com", "TEST123", "10%", "2024-12-31", "electronics"
        )

        assert result["success"] is True
        assert result["message"] == "Success"
        assert result["code_id"] == "example.com_TEST123"

        expected_data = {
            "site": "https://example.com",
            "code": "TEST123",
            "discount": "10%",
            "expires_at": "2024-12-31",
            "category": "electronics",
            "hotkey": "test_hotkey",
        }
        self._assert_authenticated_request(
            mock_post, "http://localhost:8000/v1/submit-code", expected_data
        )

    @mock.patch("koupons_miner_cli.business.codes.requests.post")
    def test_submit_coupon_code_minimal_args(
        self, mock_post, mock_wallet, success_response
    ):
        """Test coupon code submission with minimal arguments."""
        mock_post.return_value = success_response

        result = codes_business.submit_coupon_code(
            mock_wallet, "example.com", "TEST123"
        )

        assert result["success"] is True
        assert result["discount"] is None

        # Verify optional fields are not included
        args, kwargs = mock_post.call_args
        json_data = kwargs["json"]
        assert "discount" not in json_data
        assert "expires_at" not in json_data
        assert "category" not in json_data

    @mock.patch("koupons_miner_cli.business.codes.requests.get")
    def test_get_coupon_codes_success(self, mock_get, mock_wallet):
        """Test successful coupon codes retrieval."""
        mock_response = mock.Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "coupons": [
                {
                    "code": "TEST123",
                    "site": "https://example.com",
                    "discount": "10%",
                    "expires_at": "2024-12-31T23:59:59Z",
                    "category": "electronics",
                    "created_at": "2024-01-01T00:00:00Z",
                    "miner_hotkey": "test_hotkey",
                }
            ]
        }
        mock_get.return_value = mock_response

        result = codes_business.get_coupon_codes(mock_wallet, "example.com")

        assert len(result) == 1
        coupon = result[0]
        assert coupon["code"] == "TEST123"
        assert coupon["site"] == "example.com"  # Normalized

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs["params"]["site"] == "https://example.com"
        assert kwargs["headers"]["X-Hotkey"] == "test_hotkey"

    @mock.patch("koupons_miner_cli.business.codes.requests.put")
    def test_replace_coupon_code_success(self, mock_put, mock_wallet):
        """Test successful coupon code replacement."""
        mock_response = mock.Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "message": "Code replaced successfully",
            "replaced_at": "2024-01-01T12:00:00Z",
        }
        mock_put.return_value = mock_response

        result = codes_business.replace_coupon_code(
            mock_wallet, "example.com", "OLD123", "NEW123"
        )

        assert result["success"] is True
        assert result["old_code_id"] == "example.com_OLD123"
        assert result["new_code_id"] == "example.com_NEW123"

        expected_data = {
            "site": "https://example.com",
            "old_code": "OLD123",
            "new_code": "NEW123",
            "hotkey": "test_hotkey",
        }
        self._assert_authenticated_request(
            mock_put, "http://localhost:8000/v1/replace-code", expected_data
        )

    @mock.patch("koupons_miner_cli.business.codes.requests.delete")
    def test_delete_coupon_code_success(self, mock_delete, mock_wallet):
        """Test successful coupon code deletion."""
        mock_response = mock.Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "message": "Code deleted successfully",
            "deleted_at": "2024-01-01T12:00:00Z",
        }
        mock_delete.return_value = mock_response

        result = codes_business.delete_coupon_code(
            mock_wallet, "example.com", "TEST123"
        )

        assert result["success"] is True
        assert result["code_id"] == "example.com_TEST123"

        expected_data = {
            "site": "https://example.com",
            "code": "TEST123",
            "hotkey": "test_hotkey",
        }
        self._assert_authenticated_request(
            mock_delete, "http://localhost:8000/v1/delete-code", expected_data
        )

    @pytest.mark.parametrize(
        "operation,mock_method,business_function,args",
        [
            ("submit", "post", "submit_coupon_code", ("example.com", "TEST123")),
            ("replace", "put", "replace_coupon_code", ("example.com", "OLD", "NEW")),
            ("delete", "delete", "delete_coupon_code", ("example.com", "TEST123")),
        ],
    )
    @mock.patch("koupons_miner_cli.business.codes.requests")
    def test_api_error_handling(
        self,
        mock_requests,
        mock_wallet,
        error_response,
        operation,
        mock_method,
        business_function,
        args,
    ):
        """Test API error handling across all operations."""
        # Setup the specific HTTP method mock
        getattr(mock_requests, mock_method).return_value = error_response

        # Call the business function
        func = getattr(codes_business, business_function)
        result = func(mock_wallet, *args)

        assert result["success"] is False
        assert result["error"] == "API Error"
        assert result["wallet_address"] == "test_hotkey"

    @pytest.mark.parametrize(
        "operation,mock_method,business_function,args",
        [
            ("submit", "post", "submit_coupon_code", ("example.com", "TEST123")),
            ("replace", "put", "replace_coupon_code", ("example.com", "OLD", "NEW")),
            ("delete", "delete", "delete_coupon_code", ("example.com", "TEST123")),
        ],
    )
    @mock.patch("koupons_miner_cli.business.codes.requests")
    def test_network_error_handling(
        self,
        mock_requests,
        mock_wallet,
        operation,
        mock_method,
        business_function,
        args,
    ):
        """Test network error handling across all operations."""
        # Set up the specific HTTP method mock to raise exception
        getattr(
            mock_requests, mock_method
        ).side_effect = requests.exceptions.ConnectionError("Network error")

        # Call the business function
        func = getattr(codes_business, business_function)
        result = func(mock_wallet, *args)

        assert result["success"] is False
        assert "Network error" in result["error"]
        assert result["wallet_address"] == "test_hotkey"


class TestStatusDetermination:
    """Test status determination logic."""

    @pytest.mark.parametrize(
        "coupon_data,expected_status",
        [
            ({"code": "TEST123"}, "Active"),  # No expiry
            ({"expires_at": "invalid-date"}, "Active"),  # Invalid date
            (
                {
                    "expires_at": datetime.now(timezone.utc)
                    .replace(year=2030)
                    .isoformat()
                },
                "Active",
            ),  # Future
            (
                {
                    "expires_at": datetime.now(timezone.utc)
                    .replace(year=2020)
                    .isoformat()
                },
                "Expired",
            ),  # Past
        ],
    )
    def test_determine_status(self, coupon_data, expected_status):
        """Test status determination for various scenarios."""
        result = codes_business._determine_status(coupon_data)
        assert result == expected_status

    def test_determine_status_z_suffix(self):
        """Test status determination with Z suffix in date."""
        future_date = datetime.now(timezone.utc).replace(year=2030)
        coupon = {"expires_at": future_date.isoformat().replace("+00:00", "Z")}
        result = codes_business._determine_status(coupon)
        assert result == "Active"
