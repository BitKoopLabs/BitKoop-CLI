import logging
import re
import sys
from typing import Optional

from bitkoop_miner_cli.business import view_codes_logic
from bitkoop_miner_cli.constants import DEFAULT_PAGE_LIMIT, NAV_HINT_EMOJI, CouponStatus
from bitkoop_miner_cli.utils.display import display_panel, display_table
from bitkoop_miner_cli.utils.formatting import (
    format_coupon_data,
    get_store_status_color_for_coupon,
)
from bitkoop_miner_cli.utils.supervisor_api_client import CouponInfo

logger = logging.getLogger(__name__)


def clean_status_text(status_text: str) -> str:
    return re.sub(r"\s*\(\d+\)", "", str(status_text))


def format_coupon_row(coupon: CouponInfo, show_coupon_status: bool = False) -> tuple:
    formatted = list(
        format_coupon_data(coupon, include_coupon_status=show_coupon_status)
    )

    if show_coupon_status and len(formatted) > 3:
        formatted[3] = clean_status_text(formatted[3])

    if len(formatted) > 1:
        color = get_store_status_color_for_coupon(coupon)
        formatted[1] = f"[{color}]{formatted[1]}[/{color}]"

    if len(formatted) > 2:
        try:
            coupon_status = CouponStatus(coupon.status)
            if coupon_status == CouponStatus.VALID:
                formatted[2] = f"[green]{formatted[2]}[/green]"
            elif coupon_status == CouponStatus.INVALID:
                formatted[2] = f"[red]{formatted[2]}[/red]"
            else:
                formatted[2] = f"[yellow]{formatted[2]}[/yellow]"
        except ValueError:
            pass

    return tuple(formatted)


def get_display_columns(is_user: bool) -> list[tuple[str, Optional[str]]]:
    columns = [
        ("Store Domain", "blue"),
        ("Store Status", None),
        ("Coupon", "cyan"),
    ]

    if is_user:
        columns.append(("Coupon Status", "bold"))

    columns.extend(
        [
            ("Submitted At", "dim"),
            ("Last Checked", "dim"),
            ("Coupon Details", None),
            ("Expires At", "magenta"),
        ]
    )

    return columns


def has_wallet_params() -> bool:
    return "--wallet.name" in sys.argv and "--wallet.hotkey" in sys.argv


def view_codes_command(args):
    site = getattr(args, "site", "all") or "all"
    category = getattr(args, "category", None)

    if "--limit" in sys.argv:
        limit = args.limit
    else:
        limit = DEFAULT_PAGE_LIMIT

    page = getattr(args, "page", 1)
    offset = getattr(args, "offset", 0)

    if not hasattr(args, "page") and offset > 0:
        page = (offset // limit) + 1

    is_user = has_wallet_params()

    site_param = None if site == "all" else site
    site_display = "all websites" if site == "all" else site
    category_display = f" in category '{category}'" if category else ""

    if is_user:
        if site == "all" and not category:
            fetch_msg = "Getting all your coupons..."
        else:
            fetch_msg = f"Getting your coupons from [bold]{site_display}[/bold]{category_display}..."
    else:
        fetch_msg = f"Getting valid coupons from [bold]{site_display}[/bold]{category_display}..."

    display_panel("Fetching Coupons", fetch_msg, border_style="blue")

    try:
        if is_user:
            codes, total_count = view_codes_logic.get_user_codes(
                args=args,
                site=site_param,
                category=category,
                active_only=False,
                limit=limit,
                page=page,
            )
        else:
            codes, total_count = view_codes_logic.get_all_valid_codes(
                site=site_param,
                category=category,
                active_only=True,
                limit=limit,
                page=page,
            )
            codes = [c for c in codes if c.status == 1]

        if not codes:
            if is_user:
                if site == "all" and not category:
                    msg = "No codes found for your wallet"
                else:
                    msg = f"No codes found for your wallet for [bold]{site_display}{category_display}[/bold]"
            else:
                msg = f"No valid codes found for [bold]{site_display}{category_display}[/bold]"

            display_panel("No Codes Found", msg, border_style="yellow")
            return

        columns = get_display_columns(is_user)
        rows = [format_coupon_row(c, is_user) for c in codes]

        title_base = "All My Coupons" if is_user else "Valid Coupons"

        if len(codes) < total_count:
            start = (page - 1) * limit + 1
            end = min(start + len(codes) - 1, total_count)
            title = f"{title_base} (Showing {start}-{end} of {total_count})"
        else:
            title = title_base

        filters = []
        if site != "all":
            filters.append(f"site: '{site}'")
        if category:
            filters.append(f"category: '{category}'")

        if filters:
            title += f" - Filtered by: {', '.join(filters)}"

        display_table(title, columns, rows)

        if total_count > len(codes):
            total_pages = (total_count + limit - 1) // limit
            if total_pages > 1:
                nav_hints = []
                if page < total_pages:
                    nav_hints.append(f"Use --page {page + 1} for next page")
                if page > 1:
                    nav_hints.append(f"Use --page {page - 1} for previous page")

                nav_content = []
                if nav_hints:
                    nav_content.append(f"{NAV_HINT_EMOJI} {' | '.join(nav_hints)}")
                nav_content.append(f"Or use --limit {total_count} to fetch all codes")

                display_panel(
                    "Navigation",
                    "\n".join(nav_content),
                    border_style="cyan",
                )

    except view_codes_logic.WalletValidationError as e:
        display_panel("Wallet Error", f"[red]{str(e)}[/red]", border_style="red")
    except Exception as e:
        error_msg = str(e)

        if any(
            x in error_msg
            for x in ["FileNotFound", "does not exist", "Failed to get hotkey"]
        ):
            wallet_name = getattr(getattr(args, "wallet", None), "name", "unknown")
            hotkey_name = getattr(getattr(args, "wallet", None), "hotkey", "unknown")

            display_panel(
                "Wallet Error",
                f"[red]Wallet not found. Please check that wallet.name '{wallet_name}' "
                f"and wallet.hotkey '{hotkey_name}' are correct.[/red]",
                border_style="red",
            )
        else:
            display_panel(
                "Error",
                f"Failed to fetch codes: [red]{error_msg}[/red]",
                border_style="red",
            )
