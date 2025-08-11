from typing import Optional

from koupons_miner_cli.constants import CouponStatus, SiteStatus
from koupons_miner_cli.utils.supervisor_api_client import CouponInfo


def format_coupon_data(coupon: CouponInfo, user_format: bool = True) -> tuple:
    store_domain = coupon.store_domain or "N/A"

    try:
        store_status = SiteStatus(coupon.store_status)
        store_status_text = store_status.display_text
    except ValueError:
        store_status_text = "Unknown"

    coupon_code = coupon.title or "N/A"

    expires_at = format_date(coupon.valid_until, date_only=True)
    submitted_at = format_date(coupon.date_created)
    last_checked_at = format_date(getattr(coupon, "last_checked_at", None))

    discount = format_discount(coupon)
    category = coupon.category_name or "No Category"

    base_data = (
        store_domain,
        store_status_text,
        coupon_code,
        expires_at,
        discount,
        category,
        submitted_at,
        last_checked_at,
    )

    if user_format:
        try:
            coupon_status = CouponStatus(coupon.status).display_text
        except ValueError:
            coupon_status = "Unknown"
        return base_data[:3] + (coupon_status,) + base_data[3:]

    return base_data


def format_date(date_str: Optional[str], date_only: bool = False) -> str:
    if not date_str:
        return "N/A"

    try:
        if "T" in str(date_str):
            date_part, time_part = str(date_str).split("T")

            if date_only:
                return date_part

            time_part = (
                time_part.split(".")[0]
                if "." in time_part
                else time_part.replace("Z", "")
            )
            return f"{date_part} {time_part}"

        return str(date_str)
    except (ValueError, AttributeError):
        return str(date_str)


def format_discount(coupon: CouponInfo) -> str:
    if coupon.discount_value:
        return coupon.discount_value
    elif coupon.discount_percentage:
        return f"{coupon.discount_percentage}%"
    return "N/A"


def get_store_status_color_for_coupon(coupon: CouponInfo) -> str:
    try:
        return SiteStatus(coupon.store_status).color
    except ValueError:
        return "red"


def extract_wallet_names(args) -> tuple[str, str]:
    wallet_name = getattr(args, "wallet", {}).get("name", "unknown")
    hotkey_name = getattr(args, "wallet", {}).get("hotkey", "unknown")

    if hasattr(args, "wallet_name"):
        wallet_name = args.wallet_name
    if hasattr(args, "wallet_hotkey"):
        hotkey_name = args.wallet_hotkey

    return wallet_name, hotkey_name


def parse_wallet_from_error(error_msg: str, args) -> tuple[str, str]:
    wallet_name, hotkey_name = extract_wallet_names(args)

    if "wallets/" in error_msg and "/hotkeys/" in error_msg:
        parts = error_msg.split("/")
        for i, part in enumerate(parts):
            if part == "wallets" and i + 1 < len(parts):
                wallet_name = parts[i + 1]
            if part == "hotkeys" and i + 1 < len(parts):
                hotkey_name = parts[i + 1]

    return wallet_name, hotkey_name


def parse_wallet_path_from_error(error_msg: str) -> tuple[str, str]:
    import re

    wallet_name = "unknown"
    hotkey_name = "unknown"

    if "wallets/" in error_msg and "/hotkeys/" in error_msg:
        wallet_match = re.search(r"/wallets/([^/]+)/", error_msg)
        hotkey_match = re.search(r"/hotkeys/([^/\s]+)", error_msg)

        if wallet_match:
            wallet_name = wallet_match.group(1)
        if hotkey_match:
            hotkey_name = hotkey_match.group(1)

    return wallet_name, hotkey_name
