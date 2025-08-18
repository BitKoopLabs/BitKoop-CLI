import logging
from typing import Optional

from bitkoop_miner_cli.utils.formatting import (
    extract_wallet_names,
    parse_wallet_from_error,
    parse_wallet_path_from_error,
)
from bitkoop_miner_cli.utils.supervisor_api_client import (
    CouponInfo,
    create_supervisor_client,
)
from bitkoop_miner_cli.utils.wallet import WalletManager

logger = logging.getLogger(__name__)


class WalletValidationError(Exception):
    pass


def get_all_valid_codes(
    site: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100,
    page: Optional[int] = None,
    offset: Optional[int] = None,
) -> tuple[list[CouponInfo], int]:
    wallet_manager = WalletManager()
    return get_coupon_codes(
        wallet_manager=wallet_manager,
        site=site,
        category=category,
        active_only=active_only,
        limit=limit,
        page=page,
        offset=offset,
        miner_hotkey=None,
    )


def get_user_codes(
    args,
    site: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = False,
    limit: int = 100,
    page: Optional[int] = None,
    offset: Optional[int] = None,
) -> tuple[list[CouponInfo], int]:
    wallet_manager = _validate_wallet(args)
    return get_coupon_codes(
        wallet_manager=wallet_manager,
        site=site,
        category=category,
        active_only=active_only,
        limit=limit,
        page=page,
        offset=offset,
        miner_hotkey="default",
    )


def get_coupon_codes(
    wallet_manager: WalletManager,
    site: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100,
    page: Optional[int] = None,
    offset: Optional[int] = None,
    miner_hotkey: Optional[str] = "default",
) -> tuple[list[CouponInfo], int]:
    if miner_hotkey == "default":
        miner_hotkey = _get_wallet_hotkey_address(wallet_manager)
        if miner_hotkey is None and wallet_manager is not None:
            raise WalletValidationError(
                "Failed to validate wallet credentials. "
                "Please check that your wallet.name and wallet.hotkey are correct."
            )

    page = _calculate_page(page, offset, limit)

    try:
        with create_supervisor_client() as client:
            response = client.get_coupons_with_count(
                coupon_status=1 if active_only else None,
                miner_hotkey=miner_hotkey,
                store_domain=site if site and site != "all" else None,
                page=page,
                limit=limit,
                sort_by="date_updated",
                sort_order="desc",
            )

            coupons = response["coupons"]
            total_count = response["total_count"]

            if category and category.strip():
                coupons, total_count = _filter_by_category(
                    client,
                    coupons,
                    category,
                    active_only,
                    miner_hotkey,
                    site,
                    limit,
                    page,
                )

            logger.info(
                f"Retrieved {len(coupons)} coupons from supervisor API (total available: {total_count})"
            )
            return coupons, total_count

    except Exception as e:
        logger.error(f"Error getting coupon codes: {e}")
        return [], 0


def has_wallet_params(args) -> bool:
    try:
        wallet_manager = WalletManager.from_args_auto(args)
        return wallet_manager.is_valid()
    except Exception:
        return False


def _validate_wallet(args) -> WalletManager:
    try:
        wallet_manager = WalletManager.from_args_auto(args)

        if not wallet_manager.is_valid():
            wallet_name, hotkey_name = extract_wallet_names(args)
            raise WalletValidationError(
                f"Wallet validation failed. Please check that wallet.name '{wallet_name}' "
                f"and wallet.hotkey '{hotkey_name}' are correct."
            )

        return wallet_manager

    except FileNotFoundError as e:
        wallet_name, hotkey_name = parse_wallet_from_error(str(e), args)
        raise WalletValidationError(
            f"Wallet not found. Please check that wallet.name '{wallet_name}' "
            f"and wallet.hotkey '{hotkey_name}' are correct. The wallet or hotkey file does not exist."
        )
    except Exception as e:
        if "FileNotFound" in str(e) or "does not exist" in str(e):
            wallet_name, hotkey_name = parse_wallet_from_error(str(e), args)
            raise WalletValidationError(
                f"Wallet not found. Please check that wallet.name '{wallet_name}' "
                f"and wallet.hotkey '{hotkey_name}' are correct. The wallet or hotkey file does not exist."
            )
        raise


def _get_wallet_hotkey_address(wallet_manager: WalletManager) -> Optional[str]:
    try:
        if not wallet_manager or not wallet_manager.is_valid():
            logger.warning("Wallet manager is not valid")
            return None
        return wallet_manager.hotkey_address
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error getting wallet hotkey address: {e}")

        if any(
            keyword in error_msg
            for keyword in [
                "Failed to get hotkey",
                "does not exist",
                "FileNotFound",
                "Keyfile at:",
            ]
        ):
            wallet_name, hotkey_name = parse_wallet_path_from_error(error_msg)
            raise WalletValidationError(
                f"Wallet not found. Please check that wallet.name '{wallet_name}' "
                f"and wallet.hotkey '{hotkey_name}' are correct."
            )

        return None


def _calculate_page(page: Optional[int], offset: Optional[int], limit: int) -> int:
    if page is None and offset is not None:
        return (offset // limit) + 1 if offset > 0 else 1
    return page or 1


def _filter_by_category(
    client,
    coupons: list[CouponInfo],
    category: str,
    active_only: bool,
    miner_hotkey: Optional[str],
    site: Optional[str],
    limit: int,
    page: int,
) -> tuple[list[CouponInfo], int]:
    original_count = len(coupons)
    filtered_coupons = [
        coupon
        for coupon in coupons
        if category.lower() in (coupon.category_name or "").lower()
    ]

    if len(filtered_coupons) < original_count:
        logger.info(
            f"Category filter applied: {original_count} -> {len(filtered_coupons)} coupons"
        )

        if len(filtered_coupons) == 0 and page == 1:
            filtered_coupons = _search_category_across_pages(
                client, category, active_only, miner_hotkey, site, limit
            )

    total_count = (
        len(filtered_coupons) + 1
        if len(filtered_coupons) == limit
        else len(filtered_coupons)
    )
    return filtered_coupons, total_count


def _search_category_across_pages(
    client,
    category: str,
    active_only: bool,
    miner_hotkey: Optional[str],
    site: Optional[str],
    limit: int,
    max_pages: int = 5,
) -> list[CouponInfo]:
    all_matching_coupons = []

    for current_page in range(2, max_pages + 1):
        response = client.get_coupons_with_count(
            coupon_status=1 if active_only else None,
            miner_hotkey=miner_hotkey,
            store_domain=site if site and site != "all" else None,
            page=current_page,
            limit=limit,
            sort_by="date_updated",
            sort_order="desc",
        )

        additional_coupons = response["coupons"]
        matching = [
            coupon
            for coupon in additional_coupons
            if category.lower() in (coupon.category_name or "").lower()
        ]

        all_matching_coupons.extend(matching)

        if all_matching_coupons or not additional_coupons:
            break

    if all_matching_coupons:
        logger.info(
            f"Found {len(all_matching_coupons)} category matches across multiple pages"
        )

    return all_matching_coupons[:limit]
