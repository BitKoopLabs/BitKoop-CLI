"""View Product Categories command for the Koupons CLI."""

from koupons_miner_cli.business import product_categories as product_categories_business
from koupons_miner_cli.constants import DEFAULT_PAGE_LIMIT, NAV_HINT_EMOJI
from koupons_miner_cli.utils.display import display_panel, display_table


def list_categories_command(args):
    try:
        page = getattr(args, "page", 1)
        limit = getattr(args, "limit", DEFAULT_PAGE_LIMIT)
        category_name = getattr(args, "name", None)
        sort_by = getattr(args, "sort_by", "category_id")
        sort_order = getattr(args, "sort_order", "asc")

        result = product_categories_business.get_product_categories_paginated(
            category_name=category_name,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            fetch_all=False,
        )
        categories = result["categories"]
        total_count = result["total_count"]

        if not categories:
            if category_name:
                display_panel(
                    "No Categories Found",
                    f"No product categories found matching '{category_name}'",
                    border_style="yellow",
                )
            else:
                display_panel(
                    "No Categories Found",
                    "No product categories available in the supervisor API",
                    border_style="yellow",
                )
            return

        columns = [
            ("ID", "cyan"),
            ("Category Name", "blue"),
        ]

        table_rows = []
        for category in categories:
            category_id = category.id if category.id is not None else "N/A"
            category_name_display = category.name if category.name else "N/A"

            table_rows.append(
                [
                    str(category_id),
                    category_name_display,
                ]
            )

        if len(categories) < total_count:
            start = (page - 1) * limit + 1
            end = min(start + len(categories) - 1, total_count)
            title = f"Product Categories List (Showing {start}-{end} of {total_count})"
        else:
            title = f"Product Categories List (Total: {total_count})"

        if category_name:
            title += f" - Filtered by: '{category_name}'"

        display_table(title=title, columns=columns, rows=table_rows)

        if total_count > len(categories):
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
                    f"Or use --limit {total_count} to fetch all categories"
                )

                display_panel(
                    title="Navigation",
                    content="\n".join(nav_content),
                    border_style="cyan",
                )

    except Exception as error:
        display_panel(
            "Error",
            f"Failed to fetch product categories: [red]{str(error)}[/red]",
            border_style="red",
        )
