"""
Utility classes for the bitkoop CLI - common functionality across commands.
Contains shared methods to avoid code duplication between different command modules.
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from bitkoop_miner_cli.utils.supervisor_api_client import create_supervisor_client
from bitkoop_miner_cli.utils.validator_api_client import create_validator_client
from bitkoop_miner_cli.utils.wallet import WalletManager

logger = logging.getLogger(__name__)


class UserCancellationError(Exception):
    """Raised when user cancels an operation"""

    pass


class AsyncHelper:
    """Helper class for handling async operations"""

    @staticmethod
    def run_async_task(coro):
        """
        Run an async task in the current or new event loop.

        Args:
            coro: The coroutine to run

        Returns:
            The result of the coroutine
        """
        try:
            # Check if we're already in an event loop
            loop = asyncio.get_running_loop()
            logger.debug("Running in existing event loop")
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        except RuntimeError:
            # No running loop, create a new one
            logger.debug("Creating new event loop")
            return asyncio.run(coro)


class SiteManager:
    """Class for managing site operations"""

    @staticmethod
    def normalize_site_url(site: str) -> str:
        """
        Normalize site URL to ensure consistent format.

        Args:
            site: The site URL or domain

        Returns:
            Normalized site URL
        """
        if not site or site.strip() in ["/", ""]:
            return "https://localhost.com"

        site = site.strip()
        if not site.startswith(("http://", "https://")):
            return f"https://{site}"

        return site

    @staticmethod
    def get_site_id(site: str) -> int:
        """
        Get site ID from supervisor.

        Args:
            site: The site URL or domain

        Returns:
            Site ID if found

        Raises:
            ValueError: If site is not found in supervisor
            RuntimeError: If there's an error communicating with supervisor
        """
        try:
            with create_supervisor_client() as supervisor_client:
                normalized_site = site.lower().strip()
                if normalized_site.startswith(("http://", "https://")):
                    parsed = urlparse(normalized_site)
                    normalized_site = parsed.netloc or parsed.path

                page = 1
                limit = 50
                checked_domains = []

                while True:
                    result = supervisor_client.get_sites_paginated(
                        store_domain=normalized_site, page=page, limit=limit
                    )

                    sites = result["sites"]
                    total_count = result["total_count"]

                    for site_info in sites:
                        site_domain = site_info.domain.lower().strip()
                        checked_domains.append(site_domain)

                        if (
                            site_domain == normalized_site
                            or site_domain.endswith(f".{normalized_site}")
                            or normalized_site.endswith(f".{site_domain}")
                        ):
                            logger.info(
                                f"Found site ID {site_info.id} for site: {site}"
                            )
                            return site_info.id

                    if page * limit >= total_count:
                        break

                    page += 1

                logger.debug(f"Checked {len(checked_domains)} sites, no match found")

                raise ValueError(
                    f"Site '{site}' not found in supervisor. "
                    f"Please run 'bitkoop list-sites' to see available sites."
                )

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error getting site ID for {site}: {e}")
            raise RuntimeError(f"Failed to get site ID for '{site}': {str(e)}") from e


class SignatureManager:
    """Class for managing signature operations"""

    @staticmethod
    def create_signature(wallet_manager: WalletManager, payload: dict[str, Any]) -> str:
        """
        Create signature for payload.

        Args:
            wallet_manager: The wallet manager for signing
            payload: The payload to sign

        Returns:
            Signature string without '0x' prefix

        Raises:
            RuntimeError: If signature creation fails
        """
        try:
            # Create JSON exactly like the server does
            signature_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            logger.debug(f"JSON to sign: {signature_json}")
            logger.debug(f"JSON length: {len(signature_json)} characters")

            # Create signature using bittensor wallet
            logger.info("Creating signature...")
            signature = wallet_manager.create_signature(signature_json)
            logger.debug(f"Signature created: {signature}")
            logger.debug(f"Signature length: {len(signature)} characters")

            # Remove '0x' prefix if present
            if signature.startswith("0x"):
                signature = signature[2:]

            # Test signature verification locally
            SignatureManager._verify_signature_locally(
                wallet_manager.hotkey_address, signature_json, signature
            )

            return signature
        except Exception as e:
            logger.error(f"Failed to create signature: {e}")
            raise RuntimeError(f"Signature creation failed: {str(e)}") from e

    @staticmethod
    def _verify_signature_locally(
        hotkey_address: str, signature_json: str, signature: str
    ) -> None:
        """
        Verify signature locally for testing.

        Args:
            hotkey_address: The hotkey address
            signature_json: The JSON string that was signed
            signature: The signature to verify
        """
        try:
            from fiber import Keypair as FiberKeypair

            test_keypair = FiberKeypair(hotkey_address)
            is_valid = test_keypair.verify(signature_json, bytes.fromhex(signature))
            logger.info(f"🔍 Local signature verification: {is_valid}")

            if not is_valid:
                logger.error("❌ Local signature verification failed!")
            else:
                logger.info("✅ Local signature verification passed")

        except ImportError:
            logger.warning("fiber library not available for local verification")
        except Exception as e:
            logger.debug(f"Local verification test failed: {e}")


class PayloadManager:
    """Class for managing payload operations across different commands"""

    @staticmethod
    def create_typed_action_payload(
        action: int,
        code: str,
        hotkey: str,
        site_id: int,
        submitted_at: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Create typed action payload for signature.

        Args:
            action: The action type (0=submit, 1=recheck, 2=delete)
            code: The coupon code
            hotkey: The hotkey address
            site_id: The site ID
            submitted_at: Optional timestamp (will be generated if None)

        Returns:
            Dict containing the typed action payload
        """
        if submitted_at is None:
            submitted_at = int(datetime.now(UTC).timestamp() * 1000)

        return {
            "action": action,
            "code": code,
            "hotkey": hotkey,
            "site_id": site_id,
            "submitted_at": submitted_at,
        }

    @staticmethod
    def create_base_payload(
        hotkey: str,
        site_id: int,
        code: str,
        submitted_at: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Create base payload for all API operations.

        Args:
            hotkey: The hotkey address
            site_id: The site ID
            code: The coupon code
            submitted_at: Optional timestamp (will be generated if None)

        Returns:
            Dict containing the base payload
        """
        if submitted_at is None:
            submitted_at = int(datetime.now(UTC).timestamp() * 1000)

        return {
            "hotkey": hotkey,
            "site_id": site_id,
            "code": code,
            "submitted_at": submitted_at,
        }

    @staticmethod
    def prepare_headers(
        wallet_manager: WalletManager, typed_action_payload: dict[str, Any]
    ) -> dict[str, str]:
        """
        Prepare headers with signature for API requests.

        Args:
            wallet_manager: The wallet manager for signing
            typed_action_payload: The typed action payload to sign

        Returns:
            Dict containing the headers
        """
        signature = SignatureManager.create_signature(
            wallet_manager, typed_action_payload
        )

        return {
            "X-Signature": signature,
            "X-Hotkey": wallet_manager.hotkey_address,
            "Content-Type": "application/json",
        }


class ValidatorClient:
    """Class for interacting with validators"""

    @staticmethod
    async def execute_network_action(
        payload: dict,
        headers: dict,
        endpoint: str,
        max_validators: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Execute an action across the validator network.

        Args:
            payload: The payload to send
            headers: The headers to send
            endpoint: API endpoint to call (e.g., "coupons/submit", "coupons/delete", "coupons/recheck")
            max_validators: Optional maximum number of validators to interact with

        Returns:
            Dictionary containing action result
        """
        try:
            start_time = time.time()

            async with create_validator_client() as client:
                if endpoint == "coupons/submit":
                    return await client.submit_coupon_to_network(
                        payload=payload, headers=headers, max_validators=max_validators
                    )
                elif endpoint == "coupons/delete":
                    return await client.delete_coupon_across_network(
                        payload=payload, headers=headers, max_validators=max_validators
                    )
                elif endpoint == "coupons/recheck":
                    return await client.recheck_coupon_across_network(
                        payload=payload, headers=headers, max_validators=max_validators
                    )
                else:
                    raise ValueError(f"Unknown endpoint: {endpoint}")

        except Exception as e:
            logger.error(f"Error in network client action: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_validators": 0,
                "successful_submissions": 0,
                "failed_submissions": 0,
                "success_rate": 0,
                "total_time": time.time() - start_time
                if "start_time" in locals()
                else 0,
                "network": "unknown",
            }

    @staticmethod
    def execute_network_action_sync(
        payload: dict,
        headers: dict,
        endpoint: str,
        max_validators: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Synchronous wrapper for execute_network_action.

        Args:
            payload: The payload to send
            headers: The headers to send
            endpoint: API endpoint to call
            max_validators: Optional maximum number of validators

        Returns:
            Dictionary containing action result
        """
        return AsyncHelper.run_async_task(
            ValidatorClient.execute_network_action(
                payload=payload,
                headers=headers,
                endpoint=endpoint,
                max_validators=max_validators,
            )
        )


class ResponseFormatter:
    """Class for formatting responses from validator operations"""

    @staticmethod
    def format_response(
        result: dict[str, Any],
        site: str,
        code: str,
        success: bool,
        additional_fields: Optional[dict[str, Any]] = None,
        error_msg: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Format response for CLI output.

        Args:
            result: The raw result from validator operation
            site: The site name
            code: The coupon code
            success: Whether the operation was successful
            additional_fields: Optional additional fields to include
            error_msg: Optional error message to include

        Returns:
            Formatted response dictionary
        """
        response = {
            "success": success,
            "code_id": f"{site}_{code}",
            "site": site,
            "code": code,
            "multi_validator_stats": {
                "total_validators": result.get("total_validators", 0),
                "successful_submissions": result.get("successful_submissions", 0),
                "failed_submissions": result.get("failed_submissions", 0),
                "success_rate": result.get("success_rate", 0),
                "network": result.get("network", "unknown"),
                "total_time": result.get("total_time", 0),
                "avg_response_time": result.get("avg_response_time"),
            },
        }

        # Add message
        if success:
            response["message"] = result.get(
                "message",
                f"Operation completed with {result.get('successful_submissions', 0)}/{result.get('total_validators', 0)} validators",
            )
        else:
            response["error"] = error_msg or result.get("error", "Unknown error")

        # Add additional fields if provided
        if additional_fields:
            response.update(additional_fields)

        return response


class BaseValidator:
    """Base class for validator operations (submit, delete, recheck)"""

    @staticmethod
    def validate_wallet(wallet_manager: WalletManager) -> None:
        """
        Validate wallet manager.

        Args:
            wallet_manager: The wallet manager to validate

        Raises:
            ValueError: If wallet manager is invalid
        """
        if not wallet_manager.is_valid():
            raise ValueError(
                "Invalid wallet manager - wallet name and hotkey are required"
            )

    @staticmethod
    def validate_and_get_site_id(wallet_manager: WalletManager, site: str) -> int:
        """
        Validate inputs and get site ID.

        Args:
            wallet_manager: The wallet manager
            site: The site

        Returns:
            site_id: The site ID

        Raises:
            ValueError: If validation fails
        """
        # Validate wallet
        BaseValidator.validate_wallet(wallet_manager)

        # Get site ID
        return SiteManager.get_site_id(site)

    @staticmethod
    def handle_user_confirmation(
        message: str, confirm_callback: Optional[Callable] = None
    ) -> None:
        """
        Handle user confirmation for operations.

        Args:
            message: The confirmation message
            confirm_callback: The callback function for confirmation

        Raises:
            UserCancellationError: If user cancels the operation
        """
        if confirm_callback:
            user_confirmed = confirm_callback(message)
            if not user_confirmed:
                raise UserCancellationError("Operation cancelled by user")


class CategoryManager:
    """Class for managing category operations"""

    # Constants
    OTHER_CATEGORY_NAME = "Other"
    CATEGORY_NOT_FOUND_MSG = (
        "There is no such category in our database, if continue your coupon "
        'will be automatically assigned to the "Other".'
    )

    @staticmethod
    def get_categories() -> list[Any]:
        """Get all available categories from supervisor"""
        try:
            with create_supervisor_client() as supervisor_client:
                return supervisor_client.get_categories()
        except Exception as e:
            logger.warning(f"Error fetching categories: {e}")
            return []

    @staticmethod
    def find_other_category_id() -> Optional[int]:
        """Find the ID of the 'Other' category dynamically"""
        try:
            categories = CategoryManager.get_categories()
            for cat in categories:
                if (
                    cat.name.lower().strip()
                    == CategoryManager.OTHER_CATEGORY_NAME.lower()
                ):
                    return cat.id
            logger.warning(
                f"'{CategoryManager.OTHER_CATEGORY_NAME}' category not found in database"
            )
            return None
        except Exception as e:
            logger.warning(
                f"Error finding '{CategoryManager.OTHER_CATEGORY_NAME}' category: {e}"
            )
            return None

    @staticmethod
    def validate_category_id(category_id: int) -> bool:
        """Check if a category ID exists in the database"""
        try:
            categories = CategoryManager.get_categories()
            return any(cat.id == category_id for cat in categories)
        except Exception:
            return False

    @staticmethod
    def find_category_by_name(category_name: str) -> Optional[int]:
        """Find category ID by name (case-insensitive)"""
        try:
            categories = CategoryManager.get_categories()
            normalized_name = category_name.lower().strip()

            for cat in categories:
                if cat.name.lower().strip() == normalized_name:
                    logger.info(f"Matched category: {cat.name} (ID: {cat.id})")
                    return cat.id
            return None
        except Exception:
            return None

    @staticmethod
    def get_category_info(category: Optional[str]) -> tuple[Optional[int], bool, str]:
        """
        Get category ID and validate against available categories from supervisor.

        Args:
            category: The category ID or description

        Returns:
            Tuple of (category_id, requires_confirmation, message)
            - category_id: The ID to use, or None if category is None
            - requires_confirmation: Whether user confirmation is needed
            - message: Descriptive message for confirmation prompt or logging
        """
        if not category:
            return None, False, ""

        if category.isdigit():
            category_id = int(category)

            if CategoryManager.validate_category_id(category_id):
                logger.info(f"Valid category ID: {category_id}")
                return category_id, False, ""
            else:
                other_category_id = CategoryManager.find_other_category_id()
                if other_category_id:
                    logger.debug(
                        f"Category ID {category_id} not found, suggesting 'Other' (ID: {other_category_id})"
                    )
                    return (
                        other_category_id,
                        True,
                        CategoryManager.CATEGORY_NOT_FOUND_MSG,
                    )
                else:
                    logger.warning(
                        f"Category ID {category_id} not found and 'Other' category not available"
                    )
                    return None, True, CategoryManager.CATEGORY_NOT_FOUND_MSG

        matched_id = CategoryManager.find_category_by_name(category)
        if matched_id:
            return matched_id, False, ""

        other_category_id = CategoryManager.find_other_category_id()
        if other_category_id:
            logger.debug(
                f"Category '{category}' not found, suggesting 'Other' category"
            )
            return other_category_id, True, CategoryManager.CATEGORY_NOT_FOUND_MSG
        else:
            logger.warning(
                f"Category '{category}' not found and 'Other' category not available"
            )
            return None, True, CategoryManager.CATEGORY_NOT_FOUND_MSG
