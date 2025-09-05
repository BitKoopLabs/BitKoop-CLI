"""
Supervisor API client for BitKoop supervisor operations
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional, Union

import requests

logger = logging.getLogger(__name__)


@dataclass
class SiteInfo:
    """Data class for site information."""

    id: int
    domain: str
    status: int
    miner_hotkey: Optional[str]
    config: Optional[dict] = None


@dataclass
class CouponInfo:
    """Data class for coupon information."""

    id: int
    title: str
    status: int
    store_id: int
    store_domain: str
    store_status: int
    miner_hotkey: str
    discount_value: Optional[str] = None
    discount_percentage: Optional[str] = None
    valid_until: Optional[str] = None
    date_created: Optional[str] = None
    date_updated: Optional[str] = None
    category_name: Optional[str] = None
    last_checked_at: Optional[str] = None


@dataclass
class ProductCategoryInfo:
    """Data class for product category information."""

    id: int
    name: str


@dataclass
class RankInfo:
    """Data class for rank information."""

    miner_hotkey: str
    total_points: float
    valid_count: int
    invalid_count: int
    pending_count: int
    expired_count: int
    used_count: int
    rank: int
    store_id: Optional[int] = None
    store_domain: Optional[str] = None


@dataclass
class SupervisorConfig:
    """Configuration for Supervisor client"""

    supervisor_timeout: int = 10
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    user_agent: str = "BitKoop-Miner-CLI/1.0"
    base_url: Optional[str] = None


try:
    # Lazy import to avoid dependency cycles in some test contexts
    from .network import get_supervisor_base_url
except Exception:
    def get_supervisor_base_url() -> str:  # type: ignore
        return "http://49.13.237.126/api"


class SupervisorClient:
    """
    Sync API client for BitKoop Supervisor operations
    """

    def __init__(self, config: Optional[SupervisorConfig] = None):
        self.config = config or SupervisorConfig()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.config.user_agent})
        self._sites_cache: Optional[list[SiteInfo]] = None

        # Determine base URL from config or network mapping
        resolved_base_url = (self.config.base_url or get_supervisor_base_url()).rstrip("/")
        # Persist the resolved base URL in config for external access
        self.config.base_url = resolved_base_url
        self.sites_endpoint = f"{resolved_base_url}/sites"
        self.coupons_endpoint = f"{resolved_base_url}/coupons"
        self.categories_endpoint = f"{resolved_base_url}/product-categories"
        self.rank_endpoint = f"{resolved_base_url}/rank"

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.session.close()

    def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
        params: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """Make HTTP request with retry logic and parameter support"""
        timeout = timeout or self.config.request_timeout
        headers = headers or {}
        params = params or {}

        clean_params = {k: v for k, v in params.items() if v is not None}

        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug(
                    f"Making {method} request to {url} with params: {clean_params}"
                )

                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=timeout,
                    params=clean_params,
                    **kwargs,
                )
                response.raise_for_status()

                logger.debug(f"Request successful, status: {response.status_code}")
                result = response.json()

                if isinstance(result, dict):
                    logger.debug(f"Response is dict with keys: {list(result.keys())}")
                elif isinstance(result, list) and result:
                    logger.debug(
                        f"Response is list with {len(result)} items, first item type: {type(result[0])}"
                    )
                    if isinstance(result[0], dict):
                        logger.debug(f"First item keys: {list(result[0].keys())}")

                return result

            except requests.exceptions.RequestException as e:
                if attempt == self.config.max_retries:
                    logger.error(
                        f"Request failed after {self.config.max_retries + 1} attempts: {e}"
                    )
                    raise

                logger.warning(f"Request attempt {attempt + 1} failed, retrying: {e}")
                if self.config.retry_delay > 0:
                    time.sleep(self.config.retry_delay)

    def get_sites(self, force_refresh: bool = False) -> list[SiteInfo]:
        """
        Get available sites from supervisor API (legacy method for backward compatibility)

        Args:
            force_refresh: Force refresh of cached sites data

        Returns:
            List of SiteInfo objects

        Raises:
            RuntimeError: If supervisor API is unavailable or returns invalid data
        """
        if self._sites_cache is not None and not force_refresh:
            return self._sites_cache

        logger.info("Fetching sites from supervisor API...")

        try:
            result = self._make_request(
                "GET", self.sites_endpoint, timeout=self.config.supervisor_timeout
            )

            sites = []
            if isinstance(result, dict) and "data" in result:
                result = result.get("data", [])

            for site_data in result:
                site = SiteInfo(
                    id=site_data.get("store_id"),
                    domain=site_data.get("store_domain", ""),
                    status=site_data.get("store_status", 0),
                    miner_hotkey=site_data.get("miner_hotkey"),
                    config=site_data.get("config"),
                )
                sites.append(site)

            self._sites_cache = sites
            logger.info(f"Retrieved {len(sites)} sites from supervisor API")
            return sites

        except Exception as e:
            logger.error(f"Failed to fetch sites from supervisor API: {e}")
            raise RuntimeError(f"Supervisor API unavailable: {str(e)}") from e

    def get_sites_paginated(
        self,
        store_domain: Optional[str] = None,
        store_id: Optional[int] = None,
        miner_hotkey: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
        sort_by: str = "store_id",
        sort_order: str = "asc",
        fetch_all: bool = False,
    ) -> dict[str, Union[list[SiteInfo], int]]:
        """
        Get sites from supervisor API with pagination and filtering

        Args:
            store_domain: Filter by store domain (partial match)
            store_id: Filter by store ID (exact match)
            miner_hotkey: Filter by miner hotkey (partial match)
            page: Page number for pagination
            limit: Number of items per page
            sort_by: Field to sort by (store_id, store_domain, store_status, miner_hotkey)
            sort_order: Sort direction (asc, desc)
            fetch_all: If True, fetch all pages and return complete list

        Returns:
            Dictionary with 'sites' (list of SiteInfo objects) and 'total_count' (int)

        Raises:
            RuntimeError: If API call fails
        """
        all_sites = []
        current_page = page
        total_count = 0

        while True:
            try:
                params = {
                    "store_domain": store_domain,
                    "store_id": store_id,
                    "miner_hotkey": miner_hotkey,
                    "page": current_page,
                    "limit": limit,
                    "sort_by": sort_by,
                    "sort_order": sort_order,
                }

                logger.debug(
                    f"Fetching sites from {self.sites_endpoint} with params: {params}"
                )
                result = self._make_request("GET", self.sites_endpoint, params=params)

                logger.debug(f"Raw sites API response type: {type(result)}")
                if isinstance(result, dict):
                    logger.debug(f"Response dict keys: {list(result.keys())}")
                elif isinstance(result, list) and result:
                    logger.debug(f"Response is list with {len(result)} items")
                    if result:
                        logger.debug(f"First site data: {result[0]}")

                sites_data = []
                current_total = 0
                has_next_page = False

                if isinstance(result, dict):
                    if "data" in result:
                        sites_data = result.get("data", [])
                        current_total = result.get("total", 0)
                        has_next_page = result.get("hasNextPage", False)
                        logger.debug(
                            f"Parsed paginated response: {len(sites_data)} sites, total: {current_total}, hasNextPage: {has_next_page}"
                        )
                    else:
                        for key, value in result.items():
                            if (
                                isinstance(value, list)
                                and value
                                and isinstance(value[0], dict)
                                and "store_id" in value[0]
                            ):
                                sites_data = value
                                break
                        current_total = result.get("total", len(sites_data))
                elif isinstance(result, list):
                    sites_data = result
                    current_total = len(sites_data)
                    has_next_page = False

                total_count = max(total_count, current_total)

                for site_data in sites_data:
                    site = SiteInfo(
                        id=site_data.get("store_id"),
                        domain=site_data.get("store_domain", ""),
                        status=site_data.get("store_status", 0),
                        miner_hotkey=site_data.get("miner_hotkey"),  # Can be None
                        config=site_data.get("config"),
                    )
                    all_sites.append(site)

                if not fetch_all or not has_next_page:
                    break

                current_page += 1

            except Exception as e:
                logger.error(f"Failed to fetch sites from supervisor API: {e}")
                raise RuntimeError(f"Supervisor API unavailable: {str(e)}") from e

        if not fetch_all:
            return {"sites": all_sites, "total_count": total_count}
        else:
            return {"sites": all_sites, "total_count": len(all_sites)}

    def get_coupons_with_count(
        self,
        coupon_status: Optional[int] = None,
        coupon_title: Optional[str] = None,
        miner_hotkey: Optional[str] = None,
        store_domain: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
        sort_by: str = "date_updated",
        sort_order: str = "desc",
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Union[list[CouponInfo], int]]:
        """
        Get coupons from supervisor API with total count information

        Args:
            coupon_status: Filter by coupon status (0-6)
            coupon_title: Filter by coupon title (partial match)
            miner_hotkey: Filter by miner hotkey
            store_domain: Filter by store domain
            page: Page number for pagination
            limit: Number of items per page
            sort_by: Field to sort by (date_updated, coupon_status)
            sort_order: Sort direction (asc, desc)
            headers: Additional headers for the request

        Returns:
            Dictionary with 'coupons' (list of CouponInfo objects) and 'total_count' (int)

        Raises:
            RuntimeError: If API call fails
        """
        try:
            # Make the request to get coupons
            coupons, total_count = self._get_coupons_with_total_count(
                coupon_status=coupon_status,
                coupon_title=coupon_title,
                miner_hotkey=miner_hotkey,
                store_domain=store_domain,
                page=page,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order,
                headers=headers,
            )

            return {"coupons": coupons, "total_count": total_count}

        except Exception as e:
            logger.error(f"Failed to get coupons from supervisor: {e}")
            raise RuntimeError(f"Supervisor API unavailable: {str(e)}") from e

    def _get_coupons_with_total_count(
        self,
        coupon_status: Optional[int] = None,
        coupon_title: Optional[str] = None,
        miner_hotkey: Optional[str] = None,
        store_domain: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
        sort_by: str = "date_updated",
        sort_order: str = "desc",
        headers: Optional[dict[str, str]] = None,
    ) -> tuple[list[CouponInfo], int]:
        """
        Internal helper method to get coupons with total count.

        Returns:
            Tuple of (coupons list, total count)
        """
        params = {
            "coupon_status": coupon_status,
            "coupon_title": coupon_title,
            "miner_hotkey": miner_hotkey,
            "store_domain": store_domain,
            "page": page,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }

        logger.debug(
            f"Fetching coupons from {self.coupons_endpoint} with params: {params}"
        )

        result = self._make_request(
            "GET", self.coupons_endpoint, headers=headers, params=params
        )

        coupons_data = []
        total_count = 0

        if isinstance(result, dict):
            if "data" in result and "metadata" in result:
                coupons_data = result.get("data", [])
                total_count = result.get("metadata", {}).get("total_count", 0)
                logger.debug(
                    f"API returned structured data with {len(coupons_data)} coupons and total_count: {total_count}"
                )
            elif "coupons" in result and "total_count" in result:
                coupons_data = result.get("coupons", [])
                total_count = result.get("total_count", 0)
                logger.debug(
                    f"API returned {len(coupons_data)} coupons with total_count: {total_count}"
                )
            elif "data" in result:
                coupons_data = result.get("data", [])
                total_count = result.get("total", 0)
                logger.debug(
                    f"API returned {len(coupons_data)} coupons with total: {total_count}"
                )
            else:
                for key, value in result.items():
                    if (
                        isinstance(value, list)
                        and value
                        and isinstance(value[0], dict)
                        and "coupon_id" in value[0]
                    ):
                        coupons_data = value
                        break

                for key, value in result.items():
                    if isinstance(value, int) and key.lower().endswith("count"):
                        total_count = value
                        break

                if not coupons_data:
                    logger.warning(
                        f"Could not extract coupon data from response: {result}"
                    )
                    return [], 0

                logger.debug(
                    f"Extracted {len(coupons_data)} coupons from unknown structure"
                )
        elif isinstance(result, list):
            coupons_data = result
            total_count = len(coupons_data)

            if len(coupons_data) >= limit:
                try:
                    count_params = params.copy()
                    count_params["limit"] = 1
                    count_params["page"] = 1
                    count_result = self._make_request(
                        "GET",
                        self.coupons_endpoint,
                        headers=headers,
                        params=count_params,
                    )

                    if "x-total-count" in self.session.headers:
                        total_count = int(self.session.headers.get("x-total-count"))
                    elif (
                        isinstance(count_result, dict) and "total_count" in count_result
                    ):
                        total_count = count_result.get("total_count", 0)
                    else:
                        total_count = limit * page + limit
                except Exception as e:
                    logger.debug(f"Failed to get total count: {e}")
                    total_count = limit * page + limit

            logger.debug(
                f"API returned {len(coupons_data)} coupons as direct list, estimated total: {total_count}"
            )
        else:
            logger.warning(f"Unexpected response type: {type(result)}")
            return [], 0

        coupons = []
        for coupon_data in coupons_data:
            try:
                coupon = CouponInfo(
                    id=coupon_data.get("coupon_id"),
                    title=coupon_data.get("coupon_title", ""),
                    status=coupon_data.get("coupon_status", 0),
                    store_id=coupon_data.get("store_id"),
                    store_domain=coupon_data.get("store_domain", ""),
                    store_status=coupon_data.get("store_status", 0),
                    miner_hotkey=coupon_data.get("miner_hotkey", ""),
                    discount_value=coupon_data.get("discount_value"),
                    discount_percentage=coupon_data.get("discount_percentage"),
                    valid_until=coupon_data.get("valid_until"),
                    date_created=coupon_data.get("date_created"),
                    date_updated=coupon_data.get("date_updated"),
                    category_name=coupon_data.get("product_category_name"),
                    last_checked_at=coupon_data.get("last_checked_at"),
                )
                coupons.append(coupon)
            except Exception as e:
                logger.warning(f"Failed to parse coupon data: {e}")
                continue

        logger.info(
            f"Retrieved {len(coupons)} coupons from supervisor API (total: {total_count})"
        )
        return coupons, total_count

    def get_categories(self, fetch_all: bool = True) -> list[ProductCategoryInfo]:
        """
        Get available categories from supervisor API

        Args:
            fetch_all: If True, fetch all pages of categories

        Returns:
            List of ProductCategoryInfo objects
        """
        try:
            logger.info("Fetching categories from supervisor API...")

            if fetch_all:
                result = self.get_categories_paginated(fetch_all=True)
                return result["categories"]
            else:
                result = self.get_categories_paginated(
                    page=1, limit=100, fetch_all=False
                )
                return result["categories"]

        except Exception as e:
            logger.warning(f"Supervisor API categories unavailable: {e}")
            return []

    def get_categories_paginated(
        self,
        category_name: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
        sort_by: str = "category_id",
        sort_order: str = "asc",
        fetch_all: bool = False,
    ) -> dict[str, Union[list[ProductCategoryInfo], int]]:
        """
        Get categories from supervisor API with pagination and filtering

        Args:
            category_name: Filter by category name (partial match)
            page: Page number for pagination
            limit: Number of items per page
            sort_by: Field to sort by (category_id, category_name)
            sort_order: Sort direction (asc, desc)
            fetch_all: If True, fetch all pages and return complete list

        Returns:
            Dictionary with 'categories' (list of ProductCategoryInfo objects) and 'total_count' (int)

        Raises:
            RuntimeError: If API call fails
        """
        all_categories = []
        current_page = page
        total_count = 0

        while True:
            try:
                params = {
                    "category_name": category_name,
                    "page": current_page,
                    "limit": limit,
                    "sort_by": sort_by,
                    "sort_order": sort_order,
                }

                logger.debug(
                    f"Fetching categories from {self.categories_endpoint} with params: {params}"
                )
                result = self._make_request(
                    "GET", self.categories_endpoint, params=params
                )

                categories_data = []
                current_total = 0
                has_next_page = False

                if isinstance(result, dict):
                    categories_data = result.get("data", [])
                    current_total = result.get("total", 0)
                    has_next_page = result.get("hasNextPage", False)
                    logger.debug(
                        f"Parsed paginated response: {len(categories_data)} categories, "
                        f"total: {current_total}, hasNextPage: {has_next_page}"
                    )
                elif isinstance(result, list):
                    categories_data = result
                    current_total = len(categories_data)
                    has_next_page = False

                total_count = max(total_count, current_total)

                # Convert raw data to ProductCategoryInfo objects
                for category_data in categories_data:
                    category = ProductCategoryInfo(
                        id=category_data.get("category_id"),
                        name=category_data.get("category_name", ""),
                    )
                    all_categories.append(category)

                # If not fetching all or no more pages, break
                if not fetch_all or not has_next_page:
                    break

                current_page += 1

            except Exception as e:
                logger.error(f"Failed to fetch categories from supervisor API: {e}")
                raise RuntimeError(f"Supervisor API unavailable: {str(e)}") from e

        return {"categories": all_categories, "total_count": total_count}

    def get_rank(
        self,
        miner_hotkey: Optional[str] = None,
        store_id: Optional[int] = None,
        page: int = 1,
        limit: int = 10,
        sort_order: str = "desc",
        fetch_all: bool = False,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Union[list[RankInfo], int]]:
        """
        Get rank information from supervisor API

        Args:
            miner_hotkey: Filter by miner hotkey (partial match)
            store_id: Filter by store ID (exact match)
            page: Page number for pagination
            limit: Number of items per page
            sort_order: Order by total_points (asc, desc)
            fetch_all: If True, fetch all pages and return complete list
            headers: Additional headers for the request

        Returns:
            Dictionary with 'ranks' (list of RankInfo objects) and 'total_count' (int)

        Raises:
            RuntimeError: If API call fails
        """
        all_ranks = []
        current_page = page
        total_count = 0

        while True:
            try:
                params = {
                    "miner_hotkey": miner_hotkey,
                    "store_id": store_id,
                    "page": current_page,
                    "limit": limit,
                    "sort_order": sort_order,
                }

                logger.debug(
                    f"Fetching rank from {self.rank_endpoint} with params: {params}"
                )
                result = self._make_request(
                    "GET", self.rank_endpoint, headers=headers, params=params
                )

                ranks_data = result.get("data", [])
                current_total = result.get("total", 0)
                has_next_page = result.get("hasNextPage", False)

                total_count = max(total_count, current_total)

                for rank_data in ranks_data:
                    rank = RankInfo(
                        miner_hotkey=rank_data.get("miner_hotkey", ""),
                        total_points=float(rank_data.get("total_points", 0)),
                        valid_count=int(rank_data.get("valid_count", 0)),
                        invalid_count=int(rank_data.get("invalid_count", 0)),
                        pending_count=int(rank_data.get("pending_count", 0)),
                        expired_count=int(rank_data.get("expired_count", 0)),
                        used_count=int(rank_data.get("used_count", 0)),
                        rank=int(rank_data.get("rank", 0)),
                        store_id=rank_data.get("store_id"),
                        store_domain=rank_data.get("store_domain"),
                    )
                    all_ranks.append(rank)

                if not fetch_all or not has_next_page:
                    break

                current_page += 1

            except Exception as e:
                logger.error(f"Failed to fetch rank from supervisor API: {e}")
                raise RuntimeError(f"Supervisor API unavailable: {str(e)}") from e

        return {"ranks": all_ranks, "total_count": total_count}

    def close(self):
        """Close the session"""
        self.session.close()


def create_supervisor_client(
    supervisor_timeout: int = 10,
    request_timeout: int = 30,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    user_agent: str = "BitKoop-Miner-CLI/1.0",
    base_url: Optional[str] = None,
) -> SupervisorClient:
    """
    Create SupervisorClient with configuration

    Args:
        supervisor_timeout: Timeout for supervisor operations
        request_timeout: General request timeout in seconds
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries
        user_agent: User agent string

    Returns:
        SupervisorClient instance
    """
    config = SupervisorConfig(
        supervisor_timeout=supervisor_timeout,
        request_timeout=request_timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
        user_agent=user_agent,
        base_url=base_url,
    )

    return SupervisorClient(config)
