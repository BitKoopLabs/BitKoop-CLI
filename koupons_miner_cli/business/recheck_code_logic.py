import json
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from koupons_miner_cli.utils.common_utils import (
    BaseValidator,
    PayloadManager,
    ResponseFormatter,
    ValidatorClient,
)
from koupons_miner_cli.utils.wallet import WalletManager

logger = logging.getLogger(__name__)


def recheck_coupon_code(
    wallet_manager: WalletManager,
    site: str,
    code: str,
    max_validators: Optional[int] = None,
) -> dict[str, Any]:
    try:
        logger.info(f"Preparing coupon recheck for code: {code}")

        site_id = BaseValidator.validate_and_get_site_id(wallet_manager, site, code)
        submitted_at = int(datetime.now(UTC).timestamp() * 1000)

        payload = PayloadManager.create_base_payload(
            hotkey=wallet_manager.hotkey_address,
            site_id=site_id,
            code=code,
            submitted_at=submitted_at,
        )

        typed_action_payload = PayloadManager.create_typed_action_payload(
            action=1,
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

        return ResponseFormatter.format_response(
            result=result,
            site=site,
            code=code,
            success=result.get("success", False),
            additional_fields={
                "message": result.get("message", "Coupon recheck completed")
            },
            error_msg=result.get("error") if not result.get("success", False) else None,
        )

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
