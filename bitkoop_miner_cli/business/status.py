"""
Status checking business logic for the bitkoop CLI.
"""

from typing import Any


def get_coupon_status(site: str) -> list[dict[str, Any]]:
    """
    Get live status and discount % of validated codes.

    Args:
        site: The site to get status for, or 'all' for all sites

    Returns:
        List of dictionaries containing coupon status information
    """
    # TODO: Implement actual status retrieval logic
    # Sample data - replace with actual data retrieval
    if site == "all":
        return [
            {
                "code": "ABC123",
                "site": "amazon",
                "discount": "20%",
                "status": "Active",
                "last_validated": "2023-04-28 10:30:45",
            },
            {
                "code": "DEF456",
                "site": "walmart",
                "discount": "15%",
                "status": "Expired",
                "last_validated": "2023-04-27 15:20:10",
            },
            {
                "code": "GHI789",
                "site": "target",
                "discount": "10%",
                "status": "Active",
                "last_validated": "2023-04-28 09:15:30",
            },
        ]
    else:
        return [
            {
                "code": "ABC123",
                "site": site,
                "discount": "20%",
                "status": "Active",
                "last_validated": "2023-04-28 10:30:45",
            },
            {
                "code": "DEF456",
                "site": site,
                "discount": "15%",
                "status": "Expired",
                "last_validated": "2023-04-27 15:20:10",
            },
            {
                "code": "GHI789",
                "site": site,
                "discount": "10%",
                "status": "Active",
                "last_validated": "2023-04-28 09:15:30",
            },
        ]


def validate_coupon_code(site: str, code: str) -> dict[str, Any]:
    """
    Validate a coupon code.

    Args:
        site: The site the coupon is for
        code: The coupon code to validate

    Returns:
        Dictionary containing validation result
    """
    # TODO: Implement actual code validation logic
    return {
        "success": True,
        "code_id": f"{site}_{code}",
        "site": site,
        "code": code,
        "is_valid": True,
        "discount": "20%",
        "validated_at": "2023-04-28T10:30:45Z",
    }
