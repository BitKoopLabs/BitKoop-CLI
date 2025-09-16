from typing import Optional

from bitkoop_miner_cli.constants import CouponStatus, SiteStatus
from bitkoop_miner_cli.utils.supervisor_api_client import CouponInfo


def parse_coupon_details(rule: Optional[dict]) -> str:
    """Parse coupon restrictions from rule field into readable text."""
    if not rule:
        return "There are no special limitations for this coupon."

    if not isinstance(rule, dict):
        return "There are no special limitations for this coupon."

    details = []

    discount = rule.get("discount", {})
    if isinstance(discount, dict) and discount.get("target") == "shipping":
        details.append("Applies to shipping price.")

    if rule.get("ends_at") is not None:
        ends_at = format_date(rule["ends_at"], date_only=True)
        details.append(f"This coupon will be valid till {ends_at}.")

    applies_to = rule.get("applies_to", {})
    if applies_to and isinstance(applies_to, dict):
        if applies_to.get("products"):
            products = applies_to["products"]
            product_names = ", ".join(
                p["title"] for p in products if isinstance(p, dict) and "title" in p
            )
            if product_names:
                details.append(f"The discount applies to {product_names}.")
        elif applies_to.get("collections"):
            collections = applies_to["collections"]
            collection_names = ", ".join(
                c["title"] for c in collections if isinstance(c, dict) and "title" in c
            )
            if collection_names:
                details.append(f"The discount applies to {collection_names}.")
    elif applies_to == "All products":
        details.append("The discount applies to All products.")

    conditions = rule.get("conditions", {})
    if isinstance(conditions, dict):
        if conditions.get("usage_limit") is not None:
            details.append("Hurry up! The coupon has a limited number of uses!")

        if conditions.get("once_per_customer") is True:
            details.append("This is a one-time-per-customer use coupon.")

        if conditions.get("minimum_subtotal") is not None:
            amount = conditions["minimum_subtotal"]
            currency = (
                discount.get("currency", "") if isinstance(discount, dict) else ""
            )
            currency_text = f" {currency}" if currency else ""
            details.append(
                f"The total for the purchase must be {amount}{currency_text} or higher for the coupon to apply."
            )

        if conditions.get("minimum_quantity") is not None:
            qty = conditions["minimum_quantity"]
            details.append(
                f"You need to have at least {qty} items in your order to use this coupon."
            )

        if conditions.get("shipping_price_condition") is not None:
            details.append("Has a restriction on the shipping price to work.")

        entitled_countries = conditions.get("entitled_country_ids")
        if entitled_countries and (
            not isinstance(entitled_countries, list) or len(entitled_countries) > 0
        ):
            details.append("Can be used in specific countries only.")

    if not details:
        return "There are no special limitations for this coupon."

    return "\n".join(details)


def format_coupon_data(
    coupon: CouponInfo, include_coupon_status: bool = False
) -> tuple:
    """Format coupon data for table structure."""
    store_domain = coupon.store_domain or "N/A"

    try:
        store_status = SiteStatus(coupon.store_status)
        store_status_text = store_status.display_text
    except ValueError:
        store_status_text = "Unknown"

    coupon_code = coupon.title or "N/A"
    submitted_at = format_date(coupon.date_created)
    last_checked_at = format_date(getattr(coupon, "last_checked_at", None))

    coupon_details = parse_coupon_details(getattr(coupon, "rule", None))

    expires_at = "N/A"
    if hasattr(coupon, "rule") and coupon.rule and coupon.rule.get("ends_at"):
        expires_at = format_date(coupon.rule["ends_at"], date_only=True)
    elif coupon.valid_until:
        expires_at = format_date(coupon.valid_until, date_only=True)

    base_data = (
        store_domain,
        store_status_text,
        coupon_code,
    )

    if include_coupon_status:
        try:
            coupon_status = CouponStatus(coupon.status).display_text
        except ValueError:
            coupon_status = "Unknown"
        return base_data + (
            coupon_status,
            submitted_at,
            last_checked_at,
            coupon_details,
            expires_at,
        )

    return base_data + (submitted_at, last_checked_at, coupon_details, expires_at)


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
