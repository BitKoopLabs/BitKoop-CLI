"""
Metagraph models for BitKoop Miner CLI
Contains data models for validators, networks, and metagraph information
"""

import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Network constants from bittensor implementation
FINNEY_NETWORK = "finney"
FINNEY_TEST_NETWORK = "test"
FINNEY_SUBTENSOR_ADDRESS = "wss://entrypoint-finney.opentensor.ai:443"
FINNEY_TEST_SUBTENSOR_ADDRESS = "wss://test.finney.opentensor.ai:443/"

FINNEY_NETUID = 16
FINNEY_TEST_NETUID = 368

SS58_FORMAT = 42


@dataclass
class NetworkConfig:
    """Network configuration for bittensor networks"""

    name: str
    netuid: int
    subtensor_address: str
    ss58_format: int = SS58_FORMAT
    description: str = ""


class NetworkType(Enum):
    """
    Supported bittensor networks with their configurations
    """

    FINNEY = NetworkConfig(
        name=FINNEY_NETWORK,
        netuid=FINNEY_NETUID,
        subtensor_address=FINNEY_SUBTENSOR_ADDRESS,
        description="Finney mainnet - production network",
    )

    TEST = NetworkConfig(
        name=FINNEY_TEST_NETWORK,
        netuid=FINNEY_TEST_NETUID,
        subtensor_address=FINNEY_TEST_SUBTENSOR_ADDRESS,
        description="Finney testnet - for development and testing",
    )

    @property
    def config(self) -> NetworkConfig:
        """Get network configuration"""
        return self.value

    @property
    def name(self) -> str:
        """Get network name"""
        return self.value.name

    @property
    def netuid(self) -> int:
        """Get network UID"""
        return self.value.netuid

    @property
    def subtensor_address(self) -> str:
        """Get subtensor WebSocket address"""
        return self.value.subtensor_address

    @property
    def description(self) -> str:
        """Get network description"""
        return self.value.description

    @property
    def is_testnet(self) -> bool:
        """Check if this is a test network"""
        return self == NetworkType.TEST

    @classmethod
    def from_name(cls, name: str) -> "NetworkType":
        """
        Get NetworkType from network name

        Args:
            name: Network name (case-insensitive)

        Returns:
            NetworkType enum value

        Raises:
            ValueError: If network name not found
        """
        name_lower = name.lower()

        for network in cls:
            if network.name.lower() == name_lower:
                return network

        # Handle common aliases
        aliases = {
            "main": cls.FINNEY,
            "mainnet": cls.FINNEY,
            "testnet": cls.TEST,
            "dev": cls.TEST,
        }

        if name_lower in aliases:
            return aliases[name_lower]

        available = [network.name for network in cls]
        raise ValueError(f"Unknown network '{name}'. Available networks: {available}")

    def get_chain_endpoint(self, custom_address: Optional[str] = None) -> str:
        """
        Get chain endpoint

        Args:
            custom_address: Optional custom subtensor address

        Returns:
            Subtensor address to use
        """
        return custom_address if custom_address else self.subtensor_address


class ValidatorStatus(Enum):
    """Validator status for multi-validator operations"""

    UNKNOWN = "unknown"
    CHECKING = "checking"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BITKOOP_CONFIRMED = "bitkoop_confirmed"
    NON_BITKOOP = "non_bitkoop"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"


@dataclass
class ValidatorInfo:
    """
    Information about a validator from metagraph
    Optimized for multi-validator operations
    """

    # Identity
    hotkey: str
    coldkey: str
    node_id: int  # uid
    netuid: int

    # Network info
    ip: str
    port: int
    ip_type: int
    protocol: int

    # Stake and economics
    incentive: float
    alpha_stake: float
    tao_stake: float
    stake: float  # total_stake
    trust: float
    vtrust: float  # dividends
    last_updated: float

    # Status tracking for multi-validator operations
    status: ValidatorStatus = ValidatorStatus.UNKNOWN
    is_bitkoop_validator: Optional[bool] = None
    response_time: Optional[float] = None
    last_check: Optional[float] = None
    last_error: Optional[str] = None

    @classmethod
    def from_metagraph_node(cls, node: dict[str, Any]) -> "ValidatorInfo":
        """
        Create ValidatorInfo from metagraph node data

        Args:
            node: Node dictionary from get_nodes_for_uid

        Returns:
            ValidatorInfo instance
        """
        return cls(
            hotkey=node["hotkey"],
            coldkey=node["coldkey"],
            node_id=node["node_id"],
            netuid=node["netuid"],
            ip=node["ip"],
            port=node["port"],
            ip_type=node["ip_type"],
            protocol=node["protocol"],
            incentive=node["incentive"],
            alpha_stake=node["alpha_stake"],
            tao_stake=node["tao_stake"],
            stake=node["stake"],
            trust=node["trust"],
            vtrust=node["vtrust"],
            last_updated=node["last_updated"],
        )

    @property
    def endpoint_url(self) -> str:
        """Get HTTP endpoint URL for this validator"""
        return f"http://{self.ip}:{self.port}"

    @property
    def has_real_ip(self) -> bool:
        """Check if validator has a real (non-zero) IP address"""
        return self.ip and self.ip not in ["0.0.0.0", "127.0.0.1"]

    @property
    def is_reachable(self) -> bool:
        """Check if validator appears reachable based on network info"""
        return self.has_real_ip and self.port > 0 and self.port < 65536

    @property
    def is_available_for_submission(self) -> bool:
        """Check if validator is available for coupon submission"""
        return (
            self.status == ValidatorStatus.BITKOOP_CONFIRMED
            and self.is_reachable
            and self.is_bitkoop_validator is True
        )

    @property
    def hotkey_short(self) -> str:
        """Get shortened hotkey for display"""
        return (
            f"{self.hotkey[:8]}...{self.hotkey[-6:]}"
            if len(self.hotkey) > 20
            else self.hotkey
        )

    @property
    def priority_score(self) -> float:
        """
        Calculate priority score for validator selection
        Higher score = higher priority
        """
        base_score = 0.0

        # Status bonus
        if self.status == ValidatorStatus.BITKOOP_CONFIRMED:
            base_score += 1000
        elif self.status == ValidatorStatus.AVAILABLE:
            base_score += 500

        # Stake bonus (normalized)
        base_score += min(self.stake / 1000.0, 100)

        # Trust bonus
        base_score += self.trust * 50

        # Response time penalty (lower is better)
        if self.response_time is not None:
            base_score -= min(self.response_time * 10, 50)

        return base_score

    def update_status(
        self,
        status: ValidatorStatus,
        is_bitkoop: Optional[bool] = None,
        response_time: Optional[float] = None,
        error: Optional[str] = None,
    ):
        """
        Update validator status information

        Args:
            status: New validator status
            is_bitkoop: Whether this is a BitKoop validator
            response_time: Response time in seconds
            error: Error message if any
        """
        self.status = status

        if is_bitkoop is not None:
            self.is_bitkoop_validator = is_bitkoop

        if response_time is not None:
            self.response_time = response_time

        if error is not None:
            self.last_error = error

        self.last_check = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "hotkey": self.hotkey,
            "coldkey": self.coldkey,
            "node_id": self.node_id,
            "netuid": self.netuid,
            "ip": self.ip,
            "port": self.port,
            "endpoint_url": self.endpoint_url,
            "stake": self.stake,
            "trust": self.trust,
            "status": self.status.value,
            "is_bitkoop_validator": self.is_bitkoop_validator,
            "response_time": self.response_time,
            "is_available": self.is_available_for_submission,
            "priority_score": self.priority_score,
        }

    def __str__(self) -> str:
        status_icons = {
            ValidatorStatus.UNKNOWN: "❓",
            ValidatorStatus.CHECKING: "🔄",
            ValidatorStatus.AVAILABLE: "🟡",
            ValidatorStatus.BITKOOP_CONFIRMED: "✅",
            ValidatorStatus.NON_BITKOOP: "❌",
            ValidatorStatus.NETWORK_ERROR: "🔴",
            ValidatorStatus.TIMEOUT: "⏰",
            ValidatorStatus.UNAVAILABLE: "💥",
        }

        icon = status_icons.get(self.status, "❓")

        return (
            f"Validator(uid={self.node_id}, "
            f"hotkey={self.hotkey_short}, "
            f"endpoint={self.endpoint_url}, "
            f"status={icon}, "
            f"stake={self.stake:.1f})"
        )


@dataclass
class MetagraphInfo:
    """
    Summary information about the metagraph for multi-validator operations
    """

    netuid: int
    network: str
    block: int
    sync_time: float

    # Validator counts
    total_validators: int
    reachable_validators: int
    bitkoop_validators: int
    available_validators: int

    # Network health
    total_stake: float
    avg_response_time: Optional[float] = None

    # Validation summary
    last_validation_time: Optional[float] = None
    validation_errors: list[str] = field(default_factory=list)

    @property
    def health_score(self) -> float:
        """
        Calculate network health score (0-100)
        Based on validator availability and response times
        """
        if self.total_validators == 0:
            return 0.0

        # Base score from availability
        availability_ratio = self.available_validators / self.total_validators
        base_score = availability_ratio * 70  # Max 70 points for availability

        # Response time bonus (max 20 points)
        if self.avg_response_time is not None:
            if self.avg_response_time < 0.5:
                response_score = 20
            elif self.avg_response_time < 1.0:
                response_score = 15
            elif self.avg_response_time < 2.0:
                response_score = 10
            else:
                response_score = 5
        else:
            response_score = 0

        # BitKoop validator ratio bonus (max 10 points)
        if self.reachable_validators > 0:
            bitkoop_ratio = self.bitkoop_validators / self.reachable_validators
            bitkoop_score = bitkoop_ratio * 10
        else:
            bitkoop_score = 0

        return min(base_score + response_score + bitkoop_score, 100.0)

    @property
    def is_healthy(self) -> bool:
        """Check if network is healthy (at least 1 available validator)"""
        return self.available_validators > 0

    def __str__(self) -> str:
        return (
            f"Metagraph(netuid={self.netuid}, network={self.network}, "
            f"validators={self.available_validators}/{self.total_validators}, "
            f"health={self.health_score:.1f}%)"
        )


@dataclass
class ValidatorSubmissionResult:
    """
    Result of submitting to a single validator
    Used for multi-validator submission tracking
    """

    validator: ValidatorInfo
    success: bool
    response_data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    response_time: Optional[float] = None
    status_code: Optional[int] = None

    @property
    def validator_endpoint(self) -> str:
        """Get validator endpoint"""
        return self.validator.endpoint_url

    @property
    def validator_hotkey_short(self) -> str:
        """Get shortened validator hotkey"""
        return self.validator.hotkey_short

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "validator_hotkey": self.validator.hotkey,
            "validator_endpoint": self.validator_endpoint,
            "success": self.success,
            "response_data": self.response_data,
            "error": self.error,
            "response_time": self.response_time,
            "status_code": self.status_code,
        }


@dataclass
class MultiValidatorSubmissionResult:
    """
    Aggregated result of submitting to multiple validators
    """

    total_validators: int
    successful_submissions: int
    failed_submissions: int
    results: list[ValidatorSubmissionResult]
    total_time: float

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage"""
        if self.total_validators == 0:
            return 0.0
        return (self.successful_submissions / self.total_validators) * 100

    @property
    def is_successful(self) -> bool:
        """Check if submission was overall successful (>50% success rate)"""
        return self.success_rate > 50.0

    @property
    def avg_response_time(self) -> Optional[float]:
        """Get average response time of successful submissions"""
        successful_times = [
            r.response_time
            for r in self.results
            if r.success and r.response_time is not None
        ]

        if not successful_times:
            return None

        return sum(successful_times) / len(successful_times)

    def get_successful_results(self) -> list[ValidatorSubmissionResult]:
        """Get only successful submission results"""
        return [r for r in self.results if r.success]

    def get_failed_results(self) -> list[ValidatorSubmissionResult]:
        """Get only failed submission results"""
        return [r for r in self.results if not r.success]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_validators": self.total_validators,
            "successful_submissions": self.successful_submissions,
            "failed_submissions": self.failed_submissions,
            "success_rate": self.success_rate,
            "is_successful": self.is_successful,
            "avg_response_time": self.avg_response_time,
            "total_time": self.total_time,
            "results": [r.to_dict() for r in self.results],
        }


# Legacy compatibility
NETWORK_TO_NETUID = {
    FINNEY_NETWORK: FINNEY_NETUID,
    FINNEY_TEST_NETWORK: FINNEY_TEST_NETUID,
}

SUBTENSOR_NETWORK_TO_SUBTENSOR_ADDRESS = {
    FINNEY_NETWORK: FINNEY_SUBTENSOR_ADDRESS,
    FINNEY_TEST_NETWORK: FINNEY_TEST_SUBTENSOR_ADDRESS,
}


def parse_ip_from_int(ip_int: int) -> str:
    """
    Parse IP address from integer (matches substrate implementation)

    Args:
        ip_int: IP address as integer

    Returns:
        IP address as string
    """
    try:
        ip_bytes = struct.pack(">I", ip_int)
        return socket.inet_ntoa(ip_bytes)
    except (struct.error, OSError) as e:
        logger.warning(f"Failed to parse IP {ip_int}: {e}")
        return "0.0.0.0"
