""" Business logic for product categories """

import logging
from typing import Optional

from bitkoop_miner_cli.utils.supervisor_api_client import (
    create_supervisor_client,
)

logger = logging.getLogger(__name__)


def get_product_categories_paginated(
    category_name: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    sort_by: str = "category_id",
    sort_order: str = "asc",
    fetch_all: bool = False,
) -> dict:
    """
    Get product categories with pagination support

    Args:
        category_name: Filter by category name (partial match)
        page: Page number for pagination
        limit: Number of items per page
        sort_by: Field to sort by (category_id, category_name)
        sort_order: Sort direction (asc, desc)
        fetch_all: If True, fetch all pages

    Returns:
        Dictionary with 'categories' and 'total_count'
    """
    try:
        with create_supervisor_client() as client:
            result = client.get_categories_paginated(
                category_name=category_name,
                page=page,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order,
                fetch_all=fetch_all,
            )
            logger.info(
                f"Retrieved {len(result['categories'])} product categories "
                f"(total: {result['total_count']})"
            )
            return result

    except Exception as e:
        logger.error(f"Error getting product categories: {e}")
        return {"categories": [], "total_count": 0}
