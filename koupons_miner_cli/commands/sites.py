"""Sites command for the BitKoop CLI."""

from koupons_miner_cli.constants import DEFAULT_PAGE_LIMIT, NAV_HINT_EMOJI, SiteStatus
from koupons_miner_cli.utils.display import display_panel, display_table
from koupons_miner_cli.utils.supervisor_api_client import create_supervisor_client


def list_sites_command(args):
    store_domain = getattr(args, "domain", None)
    store_id = getattr(args, "site_id", None)
    miner_hotkey = getattr(args, "miner", None)
    page = getattr(args, "page", 1)
    limit = getattr(args, "limit", DEFAULT_PAGE_LIMIT)
    sort_by = getattr(args, "sort_by", "store_status")
    sort_order = getattr(args, "sort_order", "asc") or "asc"

    try:
        with create_supervisor_client() as client:
            if hasattr(client, "get_sites_paginated"):
                result = client.get_sites_paginated(
                    store_domain=store_domain,
                    store_id=store_id,
                    miner_hotkey=miner_hotkey,
                    page=page,
                    limit=limit,
                    sort_by=sort_by,
                    sort_order=sort_order,
                    fetch_all=False,
                )
                sites = result.get("sites", [])
                total_count = result.get("total_count", len(sites))
            else:
                sites = client.get_sites()
                total_count = len(sites)

        if not sites:
            filters = [
                f"domain containing '{store_domain}'" if store_domain else None,
                f"ID {store_id}" if store_id else None,
                f"miner '{miner_hotkey}'" if miner_hotkey else None,
            ]
            filters = [f for f in filters if f]
            filter_msg = f" with {' and '.join(filters)}" if filters else ""

            display_panel(
                "No Sites Found",
                f"No sites available{filter_msg}",
                border_style="yellow",
            )
            return

        sites.sort(key=lambda x: (SiteStatus(x.status).sort_priority, x.id))

        table_rows = []
        for site in sites:
            status = SiteStatus(site.status)
            table_rows.append(
                [
                    str(site.id or "N/A"),
                    site.domain or "N/A",
                    f"[{status.color}]{status.display_text}[/{status.color}]",
                ]
            )

        if len(sites) < total_count:
            start = (page - 1) * limit + 1
            end = min(start + len(sites) - 1, total_count)
            title = (
                f"All Websites (Stores) List (Showing {start}-{end} of {total_count})"
            )
        else:
            title = f"All Websites (Stores) List (Total: {total_count})"

        filters = [
            f"domain: '{store_domain}'" if store_domain else None,
            f"ID: {store_id}" if store_id else None,
            f"miner: '{miner_hotkey}'" if miner_hotkey else None,
        ]
        filters = [f for f in filters if f]
        if filters:
            title += f" - Filtered by: {', '.join(filters)}"

        display_table(
            title=title,
            columns=[("ID", "cyan"), ("Domain", "blue"), ("Status", "green")],
            rows=table_rows,
        )

        if total_count > len(sites):
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
                nav_content.append(f"Or use --limit {total_count} to fetch all sites")

                display_panel(
                    title="Navigation",
                    content="\n".join(nav_content),
                    border_style="cyan",
                )

        statuses = [SiteStatus.ACTIVE, SiteStatus.COMING_SOON, SiteStatus.INACTIVE]
        legend_lines = [
            f"[{status.color}]{status.display_text}[/{status.color}]: "
            f"{status.description}"
            for status in statuses
        ]

        display_panel(
            title="Status Legend",
            content="\n".join(legend_lines),
            border_style="dim",
        )

    except Exception as error:
        display_panel(
            title="Error",
            content=f"Failed to fetch sites: [red]{str(error)}[/red]",
            border_style="red",
        )
