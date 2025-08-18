"""
Authentication business logic for the Koupons CLI.
"""

import json
from pathlib import Path
from typing import Any

import requests
from bittensor_wallet import Wallet


def authenticate_user(wallet: Wallet) -> dict[str, Any]:
    """
    Authenticate the user with the Koupons service.

    Returns:
        Dictionary containing authentication result
    """
    # TODO: Implement actual authentication logic
    # For now, just simulate a delay

    init_response = requests.get(
        "http://localhost:8000/v1/auth/init",
        headers={"x-hotkey": wallet.hotkey.ss58_address},
    )

    init_response_json = init_response.json()
    payload_to_sign = init_response_json["payload_to_sign"]
    api_key = init_response_json["api_key"]

    signature = wallet.hotkey.sign(json.dumps(payload_to_sign, sort_keys=True))

    verify_response = requests.post(
        "http://localhost:8000/v1/auth/verify",
        headers={"Authorization": "Bearer " + api_key, "x-signature": signature.hex()},
    )

    # Get authentication result
    auth_result = verify_response.json()

    # Save credentials to file
    credentials_dir = Path.home() / ".koupons_subnet"
    credentials_dir.mkdir(exist_ok=True)
    credentials_file = credentials_dir / "credentials.json"

    with open(credentials_file, "w") as f:
        json.dump(auth_result, f, indent=2)

    return auth_result
