"""Leaderboard command for the BitKoop CLI - shows full ranking table."""

import logging

from bitkoop_miner_cli.constants import DEFAULT_PAGE_LIMIT, NAV_HINT_EMOJI
from bitkoop_miner_cli.utils.display import display_panel, display_table
from bitkoop_miner_cli.utils.supervisor_api_client import create_supervisor_client

logger = logging.getLogger(__name__)


def list_leaderboard_command(args):
    miner_hotkey = getattr(args, "miner", None)
    store_id = getattr(args, "store_id", None)
    page = getattr(args, "page", 1)
    limit = getattr(args, "limit", DEFAULT_PAGE_LIMIT)
    sort_order = getattr(args, "sort_order", "desc")

    try:
        with create_supervisor_client() as client:
            result = client.get_rank(
                miner_hotkey=miner_hotkey,
                store_id=store_id,
                page=page,
                limit=limit,
                sort_order=sort_order,
                fetch_all=False,
            )
            ranks = result.get("ranks", [])
            total_count = result.get("total_count", len(ranks))

        if not ranks:
            filters = [
                f"miner '{miner_hotkey}'" if miner_hotkey else None,
                f"store ID {store_id}" if store_id else None,
            ]
            filters = [f for f in filters if f]
            filter_msg = f" with {' and '.join(filters)}" if filters else ""

            display_panel(
                "No Rankings Found",
                f"No rankings available{filter_msg}",
                border_style="yellow",
            )
            return

        # Show as table
        table_rows = []
        for rank_info in ranks:
            coupon_summary = (
                f"Valid Coupons: [green]{rank_info.valid_count}[/green] | "
                f"Expired/Invalid Coupons: [red]{rank_info.invalid_count}[/red] | "
                f"Coupons Awaiting Approval: [yellow]{rank_info.pending_count}[/yellow]"
            )

            hotkey_display = (
                rank_info.miner_hotkey[:8] + "..." + rank_info.miner_hotkey[-4:]
            )

            table_rows.append(
                [
                    f"#{rank_info.rank}",
                    hotkey_display,
                    f"[bold cyan]{rank_info.total_points:.0f}[/bold cyan]",
                    coupon_summary,
                ]
            )

        if len(ranks) < total_count:
            start = (page - 1) * limit + 1
            end = min(start + len(ranks) - 1, total_count)
            title = f"Miner Leaderboard (Showing {start}-{end} of {total_count})"
        else:
            title = f"Miner Leaderboard (Total: {total_count})"

        filters = [
            f"miner: '{miner_hotkey[:8]}...'" if miner_hotkey else None,
            f"store ID: {store_id}" if store_id else None,
        ]
        filters = [f for f in filters if f]
        if filters:
            title += f" - Filtered by: {', '.join(filters)}"

        display_table(
            title=title,
            columns=[
                ("Rank", "magenta"),
                ("Miner", "blue"),
                ("Points", "cyan"),
                ("Coupon Summary", "white"),
            ],
            rows=table_rows,
        )

        if total_count > len(ranks):
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
                nav_content.append(
                    f"Or use --limit {total_count} to fetch all leaderboard"
                )

                display_panel(
                    title="Navigation",
                    content="\n".join(nav_content),
                    border_style="cyan",
                )

    except Exception as error:
        display_panel(
            title="Error",
            content=f"Failed to fetch leaderboard: [red]{str(error)}[/red]",
            border_style="red",
        )
