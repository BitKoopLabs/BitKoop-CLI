"""
Network selection utilities for BitKoop CLI.

- Stores the selected network (finney/test)
- Provides supervisor base URL mapping per network
- Initializes selected network from CLI args or environment
"""

import os
from typing import Optional


# Allowed networks
_ALLOWED_NETWORKS = {"finney", "test"}


# Mapping from network to Supervisor API base URL
_SUPERVISOR_URLS = {
    "finney": "http://49.13.237.126/api",
    "test": "http://91.99.203.36/api",
}


# Selected network (process-wide). Default to finney
_selected_network: str = os.environ.get("SUBTENSOR_NETWORK", "finney").strip().lower()
if _selected_network not in _ALLOWED_NETWORKS:
    _selected_network = "finney"


def set_network(network_name: str) -> str:
    """
    Set the selected network.

    Args:
        network_name: Network name ("finney" or "test")

    Returns:
        The normalized network name actually set
    """
    global _selected_network
    if not isinstance(network_name, str):
        return _selected_network

    normalized = network_name.strip().lower()
    if normalized not in _ALLOWED_NETWORKS:
        # Ignore unknown values; keep current
        return _selected_network

    _selected_network = normalized
    return _selected_network


def get_network() -> str:
    """Get the currently selected network ("finney" or "test")."""
    return _selected_network


def get_supervisor_base_url() -> str:
    """
    Get the Supervisor API base URL for the selected network.
    """
    return _SUPERVISOR_URLS.get(get_network(), _SUPERVISOR_URLS["finney"])  # fallback


def init_network_from_args(args: Optional[object]) -> str:
    """
    Initialize the selected network from parsed CLI args and environment.

    Order of precedence:
    1) args.subtensor.network (if present)
    2) args.subtensor_network (underscore variant)
    3) args.network
    4) env SUBTENSOR_NETWORK

    Returns:
        The selected network after initialization
    """
    # Try to get from args
    candidate: Optional[str] = None
    if args is not None:
        for attr in ("subtensor.network", "subtensor_network", "network"):
            try:
                value = getattr(args, attr)
            except Exception:
                value = None
            if value:
                candidate = str(value)
                break

    # Fallback to env if not provided on args
    if not candidate:
        candidate = os.environ.get("SUBTENSOR_NETWORK")

    # Apply, defaulting to finney if invalid
    if candidate:
        set_network(candidate)

    return get_network()


