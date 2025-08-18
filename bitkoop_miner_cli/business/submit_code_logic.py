"""
Submit code logic for the bitkoop CLI - handles coupon code submission operations.
Contains all methods related to submitting coupon codes to validators.
"""
import io
import json
import logging
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Optional

from bitkoop_miner_cli.utils.common_utils import (
    BaseValidator,
    CategoryManager,
    PayloadManager,
    ResponseFormatter,
    UserCancellationError,
    ValidatorClient,
)
from bitkoop_miner_cli.utils.wallet import WalletManager

logger = logging.getLogger(__name__)

MAX_RESTRICTIONS_LENGTH = 1000
SUBMIT_ACTION_CODE = 0

MESSAGES = {
    "submission_success": " Coupon Successfully Submitted for Validation",
    "submission_failed": "Multi-validator submission failed: {error}",
    "system_error": "Failed to submit coupon due to system error",
    "category_matched": "Matched category: {name} (ID: {id})",
    "category_id_valid": "Valid category ID: {id}",
    "category_error": "Error checking category: {error}, suggesting 'Other' category",
    "category_not_found_log": "Category '{category}' not found, suggesting 'Other' category",
    "submission_completed": "Submission completed: {successful}/{total} validators succeeded",
    "preparing_submission": "Preparing coupon submission for code: {code}",
}


@dataclass
class CouponPayload:
    """Data class for coupon submission payload"""

    hotkey: str
    site_id: int
    code: str
    category_id: Optional[int] = None
    restrictions: Optional[str] = None
    country_code: Optional[str] = None
    discount_value: Optional[str] = None
    discount_percentage: Optional[int] = None
    is_global: bool = True
    valid_until: Optional[str] = None
    used_on_product_url: Optional[str] = None
    submitted_at: int = field(
        default_factory=lambda: int(datetime.now(UTC).timestamp() * 1000)
    )

    def __post_init__(self):
        """Validate fields after initialization"""
        pass

    def validate_and_sanitize(self) -> None:
        """Validate and sanitize payload fields"""
        if self.restrictions and len(self.restrictions) > MAX_RESTRICTIONS_LENGTH:
            logger.warning(
                f"Restrictions too long, truncating to {MAX_RESTRICTIONS_LENGTH} characters"
            )
            self.restrictions = self.restrictions[:MAX_RESTRICTIONS_LENGTH]

    def get_typed_action_payload(self) -> dict[str, Any]:
        """Get the typed action payload for signature"""
        return PayloadManager.create_typed_action_payload(
            action=SUBMIT_ACTION_CODE,
            code=self.code,
            hotkey=self.hotkey,
            site_id=self.site_id,
            submitted_at=self.submitted_at,
        )


class CouponSubmitter:
    """Class for managing coupon submission operations"""

    @staticmethod
    def parse_discount(discount: str) -> tuple[str, Optional[int]]:
        """Parse discount string and extract percentage if applicable"""
        discount_value = discount
        discount_percentage = None

        if discount.endswith("%"):
            try:
                percentage = int(discount.rstrip("%"))
                discount_percentage = percentage
                logger.debug(f"Set discount percentage: {percentage}")
            except ValueError:
                logger.debug(f"Discount value with % sign: {discount}")

        return discount_value, discount_percentage

    @staticmethod
    def append_category_to_restrictions(
        restrictions: Optional[str],
        category_id: Optional[int],
        original_category: Optional[str],
    ) -> Optional[str]:
        """Append original category to restrictions if using 'Other' category"""
        other_category_id = CategoryManager.find_other_category_id()

        if (
            other_category_id
            and category_id == other_category_id
            and original_category
            and (
                not original_category.isdigit()
                or int(original_category) != other_category_id
            )
        ):
            category_text = f"Category: {original_category}"
            if restrictions:
                return f"{restrictions} | {category_text}"
            return category_text

        return restrictions

    @staticmethod
    def create_coupon_payload(
        wallet_manager: WalletManager,
        site_id: int,
        code: str,
        category_id: Optional[int],
        original_category: Optional[str],
        discount: Optional[str] = None,
        expires_at: Optional[str] = None,
        restrictions: Optional[str] = None,
        country_code: Optional[str] = None,
        product_url: Optional[str] = None,
        is_global: Optional[bool] = None,
    ) -> CouponPayload:
        """
        Create coupon payload for submission.

        Args:
            wallet_manager: The wallet manager for signing requests
            site_id: The site ID
            code: The coupon code
            category_id: Category ID to use
            original_category: Original category value from user (for restrictions)
            discount: Optional discount percentage or amount
            expires_at: Optional expiration date - passed as-is to backend
            restrictions: Optional restrictions or terms
            country_code: Optional country code
            product_url: Optional product URL where coupon was used
            is_global: Optional global applicability flag

        Returns:
            CouponPayload object
        """
        updated_restrictions = CouponSubmitter.append_category_to_restrictions(
            restrictions, category_id, original_category
        )

        payload = CouponPayload(
            hotkey=wallet_manager.hotkey_address,
            site_id=site_id,
            code=code,
            category_id=category_id,
            restrictions=updated_restrictions,
            country_code=country_code,
            is_global=is_global if is_global is not None else True,
            used_on_product_url=product_url,
        )

        if discount:
            discount_value, discount_percentage = CouponSubmitter.parse_discount(
                discount
            )
            payload.discount_value = discount_value
            if discount_percentage is not None:
                payload.discount_percentage = discount_percentage

        if expires_at:
            payload.valid_until = expires_at
            logger.debug(f"Set expiration date: {expires_at}")

        payload.validate_and_sanitize()

        return payload

    @staticmethod
    def clean_result_dict(result: dict[str, Any]) -> dict[str, Any]:
        """Remove unwanted fields from result dictionary"""
        fields_to_remove = ["network", "avg_response_time", "code_id"]
        for field in fields_to_remove:
            if field in result:
                del result[field]
        return result

    @staticmethod
    def format_successful_response(
        result: dict[str, Any],
        site: str,
        code: str,
        discount: Optional[str],
        expires_at: Optional[str],
        category: Optional[str],
        restrictions: Optional[str],
        country_code: Optional[str],
        product_url: Optional[str],
        is_global: Optional[bool],
    ) -> dict[str, Any]:
        """Format successful response"""
        additional_fields = {
            "coupon": result.get("first_success_data", {}),
            "discount": discount,
            "expires_at": expires_at,
            "category": category,
            "restrictions": restrictions,
            "country_code": country_code,
            "product_url": product_url,
            "is_global": is_global,
        }

        if "message" in result:
            result["message"] = MESSAGES["submission_success"]

        formatted_response = ResponseFormatter.format_response(
            result=result,
            site=site,
            code=code,
            success=True,
            additional_fields=additional_fields,
        )

        if "message" not in formatted_response:
            formatted_response["message"] = MESSAGES["submission_success"]

        return formatted_response

    @staticmethod
    def format_error_response(
        result: dict[str, Any],
        site: str,
        code: str,
        discount: Optional[str],
        expires_at: Optional[str],
        category: Optional[str],
        restrictions: Optional[str],
        country_code: Optional[str],
        product_url: Optional[str],
        is_global: Optional[bool],
        wallet_address: str,
    ) -> dict[str, Any]:
        """Format error response"""
        additional_fields = {
            "discount": discount,
            "expires_at": expires_at,
            "category": category,
            "restrictions": restrictions,
            "country_code": country_code,
            "product_url": product_url,
            "is_global": is_global,
            "wallet_address": wallet_address,
        }

        raw_error = result.get("error", "Unknown error")
        error_msg = raw_error if isinstance(raw_error, str) else str(raw_error)

        formatted_response = ResponseFormatter.format_response(
            result=result,
            site=site,
            code=code,
            success=False,
            additional_fields=additional_fields,
            error_msg=error_msg,
        )

        if "results" in result:
            formatted_response["results"] = result["results"]

        return formatted_response


def validate_and_prepare_submission(
    wallet_manager: WalletManager,
    site: str,
    category: Optional[str] = None,
) -> tuple[int, Optional[int], bool, str]:
    """
    Validate inputs and prepare for submission.

    Args:
        wallet_manager: The wallet manager for signing requests
        site: The site the coupon is for

    Returns:
        Tuple of (site_id, category_id, requires_confirmation, confirmation_message)

    Raises:
        ValueError: If site is not found or validation fails
        RuntimeError: If there's a system/connection error
    """
    site_id = BaseValidator.validate_and_get_site_id(wallet_manager, site)

    (
        category_id,
        requires_confirmation,
        confirmation_message,
    ) = CategoryManager.get_category_info(category)

    return site_id, category_id, requires_confirmation, confirmation_message


def execute_submission(
    wallet_manager: WalletManager,
    site: str,
    site_id: int,
    code: str,
    category_id: Optional[int],
    category: Optional[str],
    discount: Optional[str] = None,
    expires_at: Optional[str] = None,
    restrictions: Optional[str] = None,
    country_code: Optional[str] = None,
    product_url: Optional[str] = None,
    is_global: Optional[bool] = None,
    max_validators: Optional[int] = None,
) -> dict[str, Any]:
    """
    Execute the actual submission process.

    Args:
        wallet_manager: The wallet manager for signing requests
        site: The site name (for response)
        site_id: The validated site ID
        code: The coupon code
        category_id: The validated category ID
        category: The original category (for response)
        discount: Optional discount percentage or amount
        expires_at: Optional expiration date
        restrictions: Optional restrictions or terms
        country_code: Optional country code
        product_url: Optional product URL where coupon was used
        is_global: Optional global applicability flag
        max_validators: Optional maximum number of validators to submit to

    Returns:
        Dictionary containing submission result

    Raises:
        RuntimeError: If there's a system/connection error
    """
    try:
        payload = CouponSubmitter.create_coupon_payload(
            wallet_manager=wallet_manager,
            site_id=site_id,
            code=code,
            category_id=category_id,
            original_category=category,
            discount=discount,
            expires_at=expires_at,
            restrictions=restrictions,
            country_code=country_code,
            product_url=product_url,
            is_global=is_global,
        )

        typed_action_payload = payload.get_typed_action_payload()

        headers = PayloadManager.prepare_headers(wallet_manager, typed_action_payload)

        logger.debug(
            f"🔑 SIGNED: {json.dumps(typed_action_payload, sort_keys=True, separators=(',', ':'))}"
        )
        logger.debug(f"📤 SENDING: {json.dumps(asdict(payload), indent=2)}")

        captured_output = io.StringIO()
        captured_errors = io.StringIO()

        with redirect_stdout(captured_output), redirect_stderr(captured_errors):
            result = ValidatorClient.execute_network_action_sync(
                payload=asdict(payload),
                headers=headers,
                endpoint="coupons/submit",
                max_validators=max_validators,
            )

        output_text = captured_output.getvalue()
        error_text = captured_errors.getvalue()
        if output_text:
            logger.debug(f"Validator output: {output_text}")
        if error_text:
            logger.debug(f"Validator errors: {error_text}")

        logger.info(
            MESSAGES["submission_completed"].format(
                successful=result.get("successful_submissions", 0),
                total=result.get("total_validators", 0),
            )
        )

        logger.debug(
            f"Full submission result: {json.dumps(result, indent=2, default=str)}"
        )

        if result.get("success", False):
            result = CouponSubmitter.clean_result_dict(result)

            return CouponSubmitter.format_successful_response(
                result=result,
                site=site,
                code=code,
                discount=discount,
                expires_at=expires_at,
                category=category,
                restrictions=restrictions,
                country_code=country_code,
                product_url=product_url,
                is_global=is_global,
            )
        else:
            return CouponSubmitter.format_error_response(
                result=result,
                site=site,
                code=code,
                discount=discount,
                expires_at=expires_at,
                category=category,
                restrictions=restrictions,
                country_code=country_code,
                product_url=product_url,
                is_global=is_global,
                wallet_address=wallet_manager.hotkey_address,
            )

    except Exception as e:
        logger.error(f"System error during coupon submission for {site}: {e}")
        logger.debug(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(MESSAGES["system_error"]) from e


def submit_coupon_code(
    wallet_manager: WalletManager,
    site: str,
    code: str,
    discount: Optional[str] = None,
    expires_at: Optional[str] = None,
    category: Optional[str] = None,
    restrictions: Optional[str] = None,
    country_code: Optional[str] = None,
    product_url: Optional[str] = None,
    is_global: Optional[bool] = None,
    max_validators: Optional[int] = None,
    confirm_callback: Optional[Callable[[str], bool]] = None,
) -> dict[str, Any]:
    """
    Submit a new coupon code to all BitKoop validators in the network.

    Args:
        wallet_manager: The wallet manager for signing requests
        site: The site the coupon is for
        code: The coupon code
        discount: Optional discount percentage or amount
        expires_at: Optional expiration date
        category: Optional category ID (integer) or description
        restrictions: Optional restrictions or terms
        country_code: Optional country code
        product_url: Optional product URL where coupon was used
        is_global: Optional global applicability flag
        max_validators: Optional maximum number of validators to submit to
        confirm_callback: Optional callback for user confirmation prompts

    Returns:
        Dictionary containing submission result

    Raises:
        ValueError: If site is not found or validation fails
        RuntimeError: If there's a system/connection error
        UserCancellationError: If user cancels the operation when prompted
    """
    try:
        logger.info(MESSAGES["preparing_submission"].format(code=code))

        (
            site_id,
            category_id,
            requires_confirmation,
            confirmation_message,
        ) = validate_and_prepare_submission(
            wallet_manager=wallet_manager,
            site=site,
            category=category,
        )

        if requires_confirmation and confirm_callback:
            BaseValidator.handle_user_confirmation(
                confirmation_message, confirm_callback
            )

        return execute_submission(
            wallet_manager=wallet_manager,
            site=site,
            site_id=site_id,
            code=code,
            category_id=category_id,
            category=category,
            discount=discount,
            expires_at=expires_at,
            restrictions=restrictions,
            country_code=country_code,
            product_url=product_url,
            is_global=is_global,
            max_validators=max_validators,
        )

    except (ValueError, UserCancellationError):
        raise

    except Exception as e:
        logger.error(f"System error during coupon submission for {site}: {e}")
        logger.debug(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(MESSAGES["system_error"]) from e
