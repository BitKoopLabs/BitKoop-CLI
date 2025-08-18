"""
Recheck code logic for the BitKoop CLI - handles coupon code recheck operations.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from bitkoop_miner_cli.utils.common_utils import (
    BaseValidator,
    PayloadManager,
    ResponseFormatter,
    ValidatorClient,
)
from bitkoop_miner_cli.utils.wallet import WalletManager

logger = logging.getLogger(__name__)


def recheck_coupon_code(
    wallet_manager: WalletManager,
    site: str,
    code: str,
    max_validators: Optional[int] = None,
) -> dict[str, Any]:
    """
    Recheck a coupon code across all validators in the network.

    Args:
        wallet_manager: The wallet manager for signing requests
        site: The site the coupon is for
        code: The coupon code to recheck
        max_validators: Optional maximum number of validators to check

    Returns:
        Dictionary containing recheck result
    """
    try:
        logger.info(f"Preparing coupon recheck for code: {code}")

        site_id = BaseValidator.validate_and_get_site_id(wallet_manager, site)
        submitted_at = int(datetime.now(UTC).timestamp() * 1000)

        payload = PayloadManager.create_base_payload(
            hotkey=wallet_manager.hotkey_address,
            site_id=site_id,
            code=code,
            submitted_at=submitted_at,
        )

        typed_action_payload = PayloadManager.create_typed_action_payload(
            action=1,  # Recheck action
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
            endpoint="coupons/recheck",
            max_validators=max_validators,
        )

        logger.debug(f"Raw recheck result: {json.dumps(result, indent=2, default=str)}")

        if not result.get("success", False):
            error_msg = result.get("error", "Operation failed")
            result["error"] = error_msg

        # Format the response
        formatted_response = ResponseFormatter.format_response(
            result=result,
            site=site,
            code=code,
            success=result.get("success", False),
            additional_fields={
                "message": result.get("message", "Coupon recheck completed")
            },
            error_msg=result.get("error") if not result.get("success", False) else None,
        )

        # CRITICAL: Preserve the results field with individual validator responses
        if "results" in result:
            formatted_response["results"] = result["results"]

        # Also preserve multi_validator_stats if it exists
        if "multi_validator_stats" in result:
            formatted_response["multi_validator_stats"] = result[
                "multi_validator_stats"
            ]
        elif "total_validators" in result:
            # Create multi_validator_stats from the result data
            formatted_response["multi_validator_stats"] = {
                "total_validators": result.get("total_validators", 0),
                "successful_submissions": result.get("successful_submissions", 0),
                "failed_submissions": result.get("failed_submissions", 0),
                "success_rate": result.get("success_rate", 0.0),
                "total_time": result.get("total_time", 0.0),
            }

        return formatted_response

    except ValueError:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "code_id": f"{site}_{code}",
            "site": site,
            "code": code,
            "wallet_address": wallet_manager.hotkey_address,
        }
