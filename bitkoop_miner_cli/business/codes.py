"""
Remaining business logic for the bitkoop CLI using the network-aware validator client.
Focus on validator operations: delete, update, recheck, and data retrieval operations.
"""

import asyncio
import json
import logging
from typing import Any, Optional

from bitkoop_miner_cli.utils.supervisor_api_client import create_supervisor_client
from bitkoop_miner_cli.utils.validator_api_client import create_validator_client
from bitkoop_miner_cli.utils.wallet import WalletManager

logger = logging.getLogger(__name__)


def _determine_status(coupon: dict) -> str:
    """
    Determine the status of a coupon based on the actual API response fields.

    Args:
        coupon: Dictionary containing coupon data from supervisor API

    Returns:
        Status string
    """
    # Check if coupon is deleted
    if coupon.get("date_deleted"):
        return "Deleted"

    # Check coupon status from API
    coupon_status = coupon.get("coupon_status", 0)
    store_status = coupon.get("store_status", 0)

    # If coupon is inactive in the system
    if coupon_status == 0:
        return "Inactive"

    # If store is inactive
    if store_status == 0:
        return "Store Inactive"

    # If store is pending
    if store_status == 2:
        return "Store Pending"

    # If coupon and store are active
    if coupon_status == 1 and store_status == 1:
        return "Active"


def _get_site_id_sync(site: str) -> int:
    """
    Synchronous wrapper to get site ID from supervisor.

    Args:
        site: The site URL or domain

    Returns:
        Site ID if found

    Raises:
        ValueError: If site is not found in supervisor
        RuntimeError: If there's an error communicating with supervisor
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def get_site_id():
            async with create_supervisor_client() as supervisor_client:
                return await supervisor_client.get_site_id_by_url(site)

        try:
            site_id = loop.run_until_complete(get_site_id())
            if site_id:
                logger.info(f"Found site ID {site_id} for site: {site}")
                return site_id
            else:
                raise ValueError(f"Site '{site}' not found in supervisor")
        finally:
            loop.close()

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error getting site ID for {site}: {e}")
        raise RuntimeError(f"Failed to get site ID for '{site}': {str(e)}") from e


def replace_coupon_code(
    wallet_manager: WalletManager,
    site: str,
    old_code: str,
    new_code: str,
    max_validators: Optional[int] = None,
) -> dict[str, Any]:
    """
    Replace an existing coupon code with a new one across all validators.

    Args:
        wallet_manager: The wallet manager for signing requests
        site: The site the coupon is for
        old_code: The old coupon code to replace
        new_code: The new coupon code
        max_validators: Optional maximum number of validators to update

    Returns:
        Dictionary containing replacement result
    """
    try:
        logger.info(f"Preparing coupon replacement: {old_code} -> {new_code}")

        site_id = _get_site_id_sync(site)

        payload = {
            "hotkey": wallet_manager.hotkey_address,
            "site_id": site_id,
            "old_code": old_code,
            "new_code": new_code,
        }

        json_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = wallet_manager.create_signature(json_payload)

        if signature.startswith("0x"):
            signature = signature[2:]

        headers = {
            "X-Signature": signature,
            "X-Hotkey": wallet_manager.hotkey_address,
            "Content-Type": "application/json",
        }

        logger.info("Replacing coupon across network validators...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                _replace_coupon_with_network_client(
                    payload=payload, headers=headers, max_validators=max_validators
                )
            )
        finally:
            loop.close()

        return {
            "success": result["success"],
            "message": result.get("message", "Coupon replacement completed"),
            "old_code_id": f"{site}_{old_code}",
            "new_code_id": f"{site}_{new_code}",
            "site": site,
            "old_code": old_code,
            "new_code": new_code,
            "multi_validator_stats": {
                "total_validators": result["total_validators"],
                "successful_submissions": result["successful_submissions"],
                "failed_submissions": result["failed_submissions"],
                "success_rate": result.get("success_rate", 0),
                "network": result["network"],
            },
        }

    except Exception as e:
        logger.error(f"Coupon replacement error: {e}")
        return {
            "success": False,
            "error": f"Replacement error: {str(e)}",
            "old_code_id": f"{site}_{old_code}",
            "new_code_id": f"{site}_{new_code}",
            "site": site,
            "old_code": old_code,
            "new_code": new_code,
            "wallet_address": wallet_manager.hotkey_address,
        }


def delete_coupon_code(
    wallet_manager: WalletManager,
    site: str,
    code: str,
    max_validators: Optional[int] = None,
) -> dict[str, Any]:
    """
    Delete a coupon code across all validators.

    Args:
        wallet_manager: The wallet manager for signing requests
        site: The site the coupon is for
        code: The coupon code to delete
        max_validators: Optional maximum number of validators to update

    Returns:
        Dictionary containing deletion result
    """
    try:
        logger.info(f"Preparing coupon deletion for code: {code}")

        site_id = _get_site_id_sync(site)

        payload = {
            "hotkey": wallet_manager.hotkey_address,
            "site_id": site_id,
            "code": code,
        }

        json_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = wallet_manager.create_signature(json_payload)

        if signature.startswith("0x"):
            signature = signature[2:]

        headers = {
            "X-Signature": signature,
            "X-Hotkey": wallet_manager.hotkey_address,
            "Content-Type": "application/json",
        }

        logger.info("Deleting coupon across network validators...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                _delete_coupon_with_network_client(
                    payload=payload, headers=headers, max_validators=max_validators
                )
            )
        finally:
            loop.close()

        return {
            "success": result["success"],
            "message": result.get("message", "Coupon deletion completed"),
            "code_id": f"{site}_{code}",
            "site": site,
            "code": code,
            "multi_validator_stats": {
                "total_validators": result["total_validators"],
                "successful_submissions": result["successful_submissions"],
                "failed_submissions": result["failed_submissions"],
                "success_rate": result.get("success_rate", 0),
                "network": result["network"],
            },
        }

    except Exception as e:
        logger.error(f"Coupon deletion error: {e}")
        return {
            "success": False,
            "error": f"Deletion error: {str(e)}",
            "code_id": f"{site}_{code}",
            "site": site,
            "code": code,
            "wallet_address": wallet_manager.hotkey_address,
        }


def recheck_coupon_code(
    wallet_manager: WalletManager,
    site: str,
    code: str,
    max_validators: Optional[int] = None,
) -> dict[str, Any]:
    """
    Recheck a coupon code across all validators.

    Args:
        wallet_manager: The wallet manager for signing requests
        site: The site the coupon is for
        code: The coupon code to recheck
        max_validators: Optional maximum number of validators to recheck

    Returns:
        Dictionary containing recheck result
    """
    try:
        logger.info(f"Preparing coupon recheck for code: {code}")

        site_id = _get_site_id_sync(site)

        payload = {
            "hotkey": wallet_manager.hotkey_address,
            "site_id": site_id,
            "code": code,
        }

        json_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = wallet_manager.create_signature(json_payload)

        if signature.startswith("0x"):
            signature = signature[2:]

        headers = {
            "X-Signature": signature,
            "X-Hotkey": wallet_manager.hotkey_address,
            "Content-Type": "application/json",
        }

        logger.info("Rechecking coupon across network validators...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                _recheck_coupon_with_network_client(
                    payload=payload, headers=headers, max_validators=max_validators
                )
            )
            logger.error(f"MY MYMYMYDEBUG: {result}")
        finally:
            loop.close()

        return {
            "success": result["success"],
            "message": result.get("message", "Coupon recheck completed"),
            "code_id": f"{site}_{code}",
            "site": site,
            "code": code,
            "multi_validator_stats": {
                "total_validators": result["total_validators"],
                "successful_submissions": result["successful_submissions"],
                "failed_submissions": result["failed_submissions"],
                "success_rate": result.get("success_rate", 0),
                "network": result["network"],
            },
        }

    except Exception as e:
        logger.error(f"Coupon recheck error: {e}")
        return {
            "success": False,
            "error": f"Recheck error: {str(e)}",
            "code_id": f"{site}_{code}",
            "site": site,
            "code": code,
            "wallet_address": wallet_manager.hotkey_address,
        }


def recheck_validators(max_validators: Optional[int] = None) -> dict[str, Any]:
    """
    Recheck all validators for health and BitKoop compatibility.

    Args:
        max_validators: Optional maximum number of validators to check

    Returns:
        Dictionary containing recheck results
    """
    try:
        logger.info("Rechecking validators on network...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                _recheck_validators_with_network_client(max_validators=max_validators)
            )
        finally:
            loop.close()

        return {
            "success": result["success"],
            "message": result.get("message", "Validator recheck completed"),
            "network": result["network"],
            "recheck_stats": result.get("recheck_stats", {}),
        }

    except Exception as e:
        logger.error(f"Validator recheck error: {e}")
        return {
            "success": False,
            "error": f"Recheck error: {str(e)}",
            "network": "unknown",
        }


def get_coupon_codes(
    wallet_manager: WalletManager,
    site: str,
    category: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
    miner_hotkey: Optional[str] = "default",
) -> list[dict[str, Any]]:
    """
    Get current and historical coupon codes for a site using the supervisor client.

    Args:
        wallet_manager: The wallet manager for hotkey identification
        site: The site to get codes for, or 'all' for all sites
        category: Optional category filter
        active_only: Whether to return only active (non-expired) coupons
        limit: Maximum number of coupons to return
        offset: Number of coupons to skip (for pagination)
        miner_hotkey: Miner hotkey filter. Use "default" for your own codes,
                     None for all codes, or specific hotkey for that miner

    Returns:
        List of dictionaries containing coupon code information
    """
    if miner_hotkey == "default":
        miner_hotkey = wallet_manager.hotkey_address

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                _get_coupon_codes_from_supervisor(
                    wallet_manager=wallet_manager,
                    site=site,
                    category=category,
                    active_only=active_only,
                    limit=limit,
                    offset=offset,
                    miner_hotkey=miner_hotkey,
                )
            )
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error getting coupon codes: {e}")
        return []


def get_validator_urls(max_validators: Optional[int] = None) -> list[str]:
    """
    Get validator URLs from the configured network.

    Args:
        max_validators: Optional maximum number of validators to return

    Returns:
        List of validator endpoint URLs
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_get_validator_urls_async(max_validators))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error getting validator URLs: {e}")
        return []


def get_network_info() -> dict[str, Any]:
    """
    Get comprehensive network information.

    Returns:
        Dictionary containing network information
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_get_network_info_async())
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error getting network info: {e}")
        return {"error": str(e), "network": "unknown"}


def get_sites(supervisor_url: str = "http://91.99.203.36/api/") -> list[dict[str, Any]]:
    """
    Get available sites from supervisor API.

    Args:
        supervisor_url: Supervisor API base URL

    Returns:
        List of site dictionaries
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(_get_sites_async(supervisor_url))
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error getting sites: {e}")
        return []


async def _replace_coupon_with_network_client(
    payload: dict, headers: dict, max_validators: Optional[int] = None
) -> dict[str, Any]:
    """Replace coupon using network-aware validator client"""
    async with create_validator_client() as client:
        return await client.replace_coupon_across_network(
            payload=payload, headers=headers, max_validators=max_validators
        )


async def _delete_coupon_with_network_client(
    payload: dict, headers: dict, max_validators: Optional[int] = None
) -> dict[str, Any]:
    """Delete coupon using network-aware validator client"""
    async with create_validator_client() as client:
        return await client.delete_coupon_across_network(
            payload=payload, headers=headers, max_validators=max_validators
        )


async def _recheck_coupon_with_network_client(
    payload: dict, headers: dict, max_validators: Optional[int] = None
) -> dict[str, Any]:
    """Recheck coupon using network-aware validator client"""
    async with create_validator_client() as client:
        return await client.recheck_coupon_across_network(
            payload=payload, headers=headers, max_validators=max_validators
        )


async def _recheck_validators_with_network_client(
    max_validators: Optional[int] = None,
) -> dict[str, Any]:
    """Recheck validators using network-aware validator client"""
    async with create_validator_client() as client:
        return await client.recheck_network_validators(max_validators=max_validators)


async def _get_validator_urls_async(max_validators: Optional[int] = None) -> list[str]:
    """Get validator URLs using network-aware validator client"""
    async with create_validator_client() as client:
        return await client.get_validator_urls(max_validators=max_validators)


async def _get_network_info_async() -> dict[str, Any]:
    """Get network info using network-aware validator client"""
    async with create_validator_client() as client:
        validators = await client.discover_validators()

        if client._metagraph_client:
            metagraph_info = await client._metagraph_client.get_metagraph_info()

            return {
                "network": client.config.metagraph_network,
                "total_validators": metagraph_info.total_validators,
                "bitkoop_validators": metagraph_info.bitkoop_validators,
                "available_validators": metagraph_info.available_validators,
                "total_stake": metagraph_info.total_stake,
                "health_score": metagraph_info.health_score,
                "block": metagraph_info.block,
                "avg_response_time": metagraph_info.avg_response_time,
            }
        else:
            return {
                "network": client.config.metagraph_network,
                "total_validators": len(validators),
                "error": "MetagraphClient not available",
            }


async def _get_coupon_codes_from_supervisor(
    wallet_manager: WalletManager,
    site: str,
    category: Optional[str] = None,
    active_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    miner_hotkey: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Get coupon codes using direct API call to supervisor"""
    async with create_supervisor_client() as supervisor_client:
        try:
            url = f"{supervisor_client.config.base_url.rstrip('/')}/coupons"
            headers = {"X-Hotkey": wallet_manager.hotkey_address}

            logger.info("Fetching coupons from supervisor")
            logger.info(f"API URL: {url}")
            logger.info(f"Headers: {headers}")
            logger.info(
                f"Request parameters: site={site}, category={category}, active_only={active_only}, "
                f"limit={limit}, offset={offset}, miner_hotkey={miner_hotkey}"
            )

            result = await supervisor_client._base_client.get(url, headers=headers)

            logger.debug(f"Raw API result: {result}")
            logger.info(f"API response type: {type(result)}")

            all_coupons = []
            if isinstance(result, dict) and result.get("success"):
                all_coupons = result.get("data", [])
                logger.info(
                    f"Structured API response, coupons received: {len(all_coupons)}"
                )
            elif isinstance(result, list):
                all_coupons = result
                logger.info(
                    f"Raw list API response, coupons received: {len(all_coupons)}"
                )
            else:
                logger.error(f"Unexpected API response format: {type(result)}")
                logger.error(f"Response content: {result}")
                return []

            logger.info(f"Total coupons before filtering: {len(all_coupons)}")
            store_domains = [c.get("store_domain") for c in all_coupons]
            logger.debug(f"All store domains: {set(store_domains)}")

            filtered_coupons = []
            skipped = 0
            for coupon in all_coupons:
                # Filter by site
                if site != "all":
                    coupon_domain = coupon.get("store_domain", "")
                    if coupon_domain != site:
                        logger.debug(
                            f"Skipping due to site mismatch: {coupon_domain} != {site}"
                        )
                        skipped += 1
                        continue

                # Filter by miner hotkey
                if miner_hotkey:
                    coupon_hotkey = coupon.get("miner_hotkey", "")
                    if coupon_hotkey != miner_hotkey:
                        logger.debug(
                            f"Skipping due to hotkey mismatch: {coupon_hotkey} != {miner_hotkey}"
                        )
                        skipped += 1
                        continue

                # Filter by category
                if category:
                    coupon_category = coupon.get("product_category_name", "") or ""
                    if category.lower() not in coupon_category.lower():
                        logger.debug(
                            f"Skipping due to category mismatch: {coupon_category}"
                        )
                        skipped += 1
                        continue

                filtered_coupons.append(coupon)

            logger.info(f"Filtered coupons: {len(filtered_coupons)}")
            logger.debug(f"Skipped coupons: {skipped}")

            # Format the results
            formatted_coupons = []
            for coupon in filtered_coupons:
                created_date = ""
                if coupon.get("date_created"):
                    try:
                        created_date = coupon.get("date_created").split("T")[0]
                    except Exception as e:
                        logger.warning(f"Error parsing created date: {e}")
                        created_date = coupon.get("date_created", "")

                status = "Active"
                if coupon.get("date_deleted"):
                    status = "Deleted"
                elif coupon.get("coupon_status") == 0:
                    status = "Inactive"
                elif coupon.get("store_status") == 0:
                    status = "Store Inactive"
                elif coupon.get("store_status") == 2:
                    status = "Store Pending"

                formatted_coupon = {
                    "code": coupon.get("coupon_title"),
                    "site": coupon.get("store_domain", ""),
                    "discount": None,
                    "expires_at": None,
                    "category": coupon.get("product_category_name") or "No Category",
                    "status": status,
                    "created_at": created_date,
                    "updated_at": coupon.get("date_updated"),
                    "miner_hotkey": coupon.get("miner_hotkey"),
                    "coupon_id": coupon.get("coupon_id"),
                    "store_id": coupon.get("store_id"),
                    "coupon_status": coupon.get("coupon_status"),
                    "store_status": coupon.get("store_status"),
                    "category_id": coupon.get("product_category_id"),
                }
                formatted_coupons.append(formatted_coupon)

            logger.info(
                f"Formatted coupons before pagination: {len(formatted_coupons)}"
            )
            logger.debug(f"Applying pagination: offset={offset}, limit={limit}")
            paginated = formatted_coupons[offset : offset + limit]
            logger.info(f"Returning {len(paginated)} coupons after pagination")

            return paginated

        except Exception as e:
            logger.error(f"Error in coupon fetch: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return []


async def _get_sites_async(supervisor_url: str) -> list[dict[str, Any]]:
    """Get sites using supervisor client"""
    async with create_supervisor_client(base_url=supervisor_url) as supervisor_client:
        try:
            sites = await supervisor_client.get_sites()
            result = [
                {
                    "id": site.id,
                    "domain": site.domain,
                    "status": site.status,
                }
                for site in sites
            ]
            logger.debug(f"Returning sites data: {result}")  # Add this debug line
            return result
        except Exception as e:
            logger.error(f"Error getting sites from supervisor: {e}")
            return []
