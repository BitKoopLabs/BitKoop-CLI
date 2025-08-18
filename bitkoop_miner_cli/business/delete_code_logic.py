"""
Delete code logic for the BitKoop CLI - handles coupon code deletion operations.
"""

import json
import logging
import traceback
from datetime import UTC, datetime
from typing import Any, Optional

from bitkoop_miner_cli.constants import CouponAction
from bitkoop_miner_cli.utils.common_utils import (
    BaseValidator,
    PayloadManager,
    ResponseFormatter,
    UserCancellationError,
    ValidatorClient,
)
from bitkoop_miner_cli.utils.wallet import WalletManager

logger = logging.getLogger(__name__)


def delete_coupon_code(
    wallet_manager: WalletManager,
    site: str,
    code: str,
    confirm_callback: Optional[callable] = None,
    max_validators: Optional[int] = None,
) -> dict[str, Any]:
    """
    Delete a coupon code across all validators in the network.

    Args:
        wallet_manager: The wallet manager for signing requests
        site: The site the coupon is for
        code: The coupon code to delete
        max_validators: Optional maximum number of validators to update
        confirm_callback: Optional callback for user confirmation prompts

    Returns:
        Dictionary containing deletion result
    """
    try:
        logger.info(f"Preparing coupon deletion for code: {code}")

        site_id = BaseValidator.validate_and_get_site_id(wallet_manager, site)

        if confirm_callback:
            BaseValidator.handle_user_confirmation(
                f"Are you sure you want to delete coupon code '{code}' from site '{site}'? "
                "This action cannot be undone.",
                confirm_callback,
            )

        return execute_deletion(wallet_manager, site, site_id, code, max_validators)

    except UserCancellationError as e:
        return error_response(wallet_manager, site, code, f"Deletion cancelled: {e}")
    except Exception as e:
        logger.error(f"Error during coupon deletion for {site}: {e}")
        logger.debug(f"Full traceback: {traceback.format_exc()}")
        return error_response(wallet_manager, site, code, f"Deletion error: {e}")


def execute_deletion(
    wallet_manager: WalletManager,
    site: str,
    site_id: int,
    code: str,
    max_validators: Optional[int] = None,
) -> dict[str, Any]:
    """Execute the actual deletion process."""
    submitted_at = int(datetime.now(UTC).timestamp() * 1000)

    payload = PayloadManager.create_base_payload(
        hotkey=wallet_manager.hotkey_address,
        site_id=site_id,
        code=code,
        submitted_at=submitted_at,
    )

    typed_action_payload = PayloadManager.create_typed_action_payload(
        action=CouponAction.DELETE,
        code=code,
        hotkey=wallet_manager.hotkey_address,
        site_id=site_id,
        submitted_at=submitted_at,
    )

    headers = PayloadManager.prepare_headers(wallet_manager, typed_action_payload)

    logger.debug(
        f"🔑 SIGNED: {json.dumps(typed_action_payload, sort_keys=True, separators=(',', ':'))}"
    )
    logger.debug(f"📤 SENDING: {json.dumps(payload, indent=2)}")

    result = ValidatorClient.execute_network_action_sync(
        payload=payload,
        headers=headers,
        endpoint="coupons/delete",
        max_validators=max_validators,
    )

    logger.info(
        f"Deletion completed: {result['successful_submissions']}/{result['total_validators']} validators succeeded"
    )

    formatted_response = ResponseFormatter.format_response(
        result=result,
        site=site,
        code=code,
        success=result["success"],
        additional_fields={
            "message": result.get("message", "Coupon deletion completed")
        },
    )

    if "results" in result:
        formatted_response["results"] = result["results"]

    if "multi_validator_stats" in result:
        formatted_response["multi_validator_stats"] = result["multi_validator_stats"]

    if not result.get("success", False) and result.get("error"):
        formatted_response["error"] = result["error"]

    return formatted_response


def error_response(
    wallet_manager: WalletManager, site: str, code: str, error_msg: str
) -> dict[str, Any]:
    """Create a standardized error response."""
    return {
        "success": False,
        "error": error_msg,
        "code_id": f"{site}_{code}",
        "site": site,
        "code": code,
        "wallet_address": wallet_manager.hotkey_address,
    }
