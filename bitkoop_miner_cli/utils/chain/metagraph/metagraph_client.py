"""
Metagraph client for BitKoop Miner CLI
Handles discovery and validation of validators for multi-validator operations
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

# Import your existing dependencies
try:
    import aiohttp
    from async_substrate_interface import AsyncSubstrateInterface
    from scalecodec.utils.ss58 import ss58_encode
except ImportError as e:
    logging.warning(f"Missing dependencies: {e}")
    aiohttp = None
    AsyncSubstrateInterface = None
    ss58_encode = None

from .metagraph_models import (
    SS58_FORMAT,
    MetagraphInfo,
    NetworkType,
    ValidatorInfo,
    ValidatorStatus,
    parse_ip_from_int,
)

logger = logging.getLogger(__name__)


class MetagraphClient:
    """
    Client for discovering and managing validators from bittensor metagraph
    Optimized for multi-validator coupon submission operations
    """

    def __init__(
        self,
        network: NetworkType = NetworkType.TEST,
        validator_check_timeout: int = 10,
        max_concurrent_checks: int = 10,
    ):
        self.network = network
        self.validator_check_timeout = validator_check_timeout
        self.max_concurrent_checks = max_concurrent_checks

        self._substrate: Optional[AsyncSubstrateInterface] = None
        self._validators_cache: Optional[list[ValidatorInfo]] = None
        self._last_sync_time: Optional[float] = None
        self._cache_ttl = 300  # 5 minutes cache

    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_substrate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def _ensure_substrate(self):
        """Ensure substrate connection is established"""
        if self._substrate is None:
            if AsyncSubstrateInterface is None:
                raise RuntimeError("async-substrate-interface not available")

            try:
                self._substrate = AsyncSubstrateInterface(
                    ss58_format=SS58_FORMAT,
                    use_remote_preset=True,
                    url=self.network.subtensor_address,
                )
                logger.info(f"Connected to substrate: {self.network.subtensor_address}")
            except Exception as e:
                logger.error(f"Failed to connect to substrate: {e}")
                raise

    async def _get_nodes_from_metagraph(
        self, block: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Get all nodes from metagraph (matches your existing implementation)

        Args:
            block: Optional block number

        Returns:
            List of node dictionaries
        """
        await self._ensure_substrate()

        try:
            block_hash = (
                await self._substrate.get_block_hash(block)
                if block is not None
                else None
            )

            response = await self._substrate.runtime_call(
                api="SubnetInfoRuntimeApi",
                method="get_metagraph",
                params=[self.network.netuid],
                block_hash=block_hash,
            )

            metagraph = response.value
            nodes = []

            for uid in range(len(metagraph["hotkeys"])):
                axon = metagraph["axons"][uid]
                node = dict(
                    hotkey=self._ss58_encode_address(metagraph["hotkeys"][uid]),
                    coldkey=self._ss58_encode_address(metagraph["coldkeys"][uid]),
                    node_id=uid,
                    incentive=metagraph["incentives"][uid],
                    netuid=metagraph["netuid"],
                    alpha_stake=metagraph["alpha_stake"][uid] * 10**-9,
                    tao_stake=metagraph["tao_stake"][uid] * 10**-9,
                    stake=metagraph["total_stake"][uid] * 10**-9,
                    trust=metagraph["trust"][uid],
                    vtrust=metagraph["dividends"][uid],
                    last_updated=float(metagraph["last_update"][uid]),
                    ip=parse_ip_from_int(axon["ip"]),
                    ip_type=axon["ip_type"],
                    port=axon["port"],
                    protocol=axon["protocol"],
                )
                nodes.append(node)

            logger.info(f"Retrieved {len(nodes)} nodes from metagraph")
            return nodes

        except Exception as e:
            logger.error(f"Failed to get nodes from metagraph: {e}")
            raise

    def _ss58_encode_address(self, address: list[int]) -> str:
        """
        Encode address to SS58 format (matches your implementation)

        Args:
            address: Address as list of integers

        Returns:
            SS58 encoded address string
        """
        if ss58_encode is None:
            # Fallback for testing
            return "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"

        if not isinstance(address[0], int):
            address = address[0]
        return ss58_encode(bytes(address).hex(), SS58_FORMAT)

    async def _check_bitkoop_validator(
        self, validator: ValidatorInfo
    ) -> tuple[bool, Optional[float], Optional[str]]:
        """
        Check if validator is a BitKoop validator (async version of your check)

        Args:
            validator: ValidatorInfo to check

        Returns:
            Tuple of (is_bitkoop, response_time, error_message)
        """
        if aiohttp is None:
            logger.warning("aiohttp not available - cannot check validators")
            return False, None, "aiohttp not available"

        url = f"{validator.endpoint_url}/openapi.json"
        start_time = time.time()

        try:
            timeout = aiohttp.ClientTimeout(total=self.validator_check_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response_time = time.time() - start_time

                    if response.status != 200:
                        return False, response_time, f"HTTP {response.status}"

                    try:
                        data = await response.json()
                        # Check if it's a BitKoop validator
                        title = data.get("info", {}).get("title", "")
                        is_bitkoop = (
                            "bitkoop" in title.lower() or "coupon" in title.lower()
                        )

                        logger.debug(
                            f"Validator {validator.hotkey_short} - Title: '{title}', BitKoop: {is_bitkoop}"
                        )
                        return is_bitkoop, response_time, None

                    except json.JSONDecodeError:
                        return False, response_time, "Invalid JSON response"

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            return False, response_time, "Timeout"
        except Exception as e:
            response_time = time.time() - start_time
            return False, response_time, str(e)

    async def _validate_validators_batch(
        self, validators: list[ValidatorInfo]
    ) -> list[ValidatorInfo]:
        """
        Validate multiple validators concurrently

        Args:
            validators: List of validators to check

        Returns:
            List of validated validators with updated status
        """
        # Only check validators with real IPs
        checkable_validators = [
            v for v in validators if v.has_real_ip and v.is_reachable
        ]

        if not checkable_validators:
            logger.warning("No validators with real IPs found")
            return validators

        logger.info(
            f"Checking {len(checkable_validators)} validators for BitKoop compatibility..."
        )

        # Create semaphore to limit concurrent checks
        semaphore = asyncio.Semaphore(self.max_concurrent_checks)

        async def check_single_validator(validator: ValidatorInfo) -> ValidatorInfo:
            async with semaphore:
                validator.update_status(ValidatorStatus.CHECKING)

                is_bitkoop, response_time, error = await self._check_bitkoop_validator(
                    validator
                )

                if error:
                    if "timeout" in error.lower():
                        status = ValidatorStatus.TIMEOUT
                    else:
                        status = ValidatorStatus.NETWORK_ERROR
                    validator.update_status(
                        status,
                        is_bitkoop=False,
                        response_time=response_time,
                        error=error,
                    )
                elif is_bitkoop:
                    validator.update_status(
                        ValidatorStatus.BITKOOP_CONFIRMED,
                        is_bitkoop=True,
                        response_time=response_time,
                    )
                else:
                    validator.update_status(
                        ValidatorStatus.NON_BITKOOP,
                        is_bitkoop=False,
                        response_time=response_time,
                    )

                return validator

        # Run checks concurrently
        tasks = [
            check_single_validator(validator) for validator in checkable_validators
        ]
        validated = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        for i, result in enumerate(validated):
            if isinstance(result, Exception):
                logger.error(
                    f"Error checking validator {checkable_validators[i].hotkey_short}: {result}"
                )
                checkable_validators[i].update_status(
                    ValidatorStatus.NETWORK_ERROR, is_bitkoop=False, error=str(result)
                )

        # Update validators that weren't checked
        for validator in validators:
            if not validator.has_real_ip:
                validator.update_status(
                    ValidatorStatus.UNAVAILABLE, is_bitkoop=False, error="No real IP"
                )
            elif not validator.is_reachable:
                validator.update_status(
                    ValidatorStatus.UNAVAILABLE, is_bitkoop=False, error="Not reachable"
                )

        bitkoop_count = len(
            [v for v in validators if v.status == ValidatorStatus.BITKOOP_CONFIRMED]
        )
        logger.info(
            f"Found {bitkoop_count} BitKoop validators out of {len(checkable_validators)} checked"
        )

        return validators

    async def discover_validators(
        self, validate_immediately: bool = True, block: Optional[int] = None
    ) -> list[ValidatorInfo]:
        """
        Discover all validators from metagraph and optionally validate them

        Args:
            validate_immediately: Whether to check validators for BitKoop compatibility
            block: Optional block number for historical data

        Returns:
            List of ValidatorInfo objects
        """
        start_time = time.time()

        try:
            # Get nodes from metagraph
            nodes = await self._get_nodes_from_metagraph(block)

            # Convert to ValidatorInfo objects
            validators = [ValidatorInfo.from_metagraph_node(node) for node in nodes]

            logger.info(f"Discovered {len(validators)} validators from metagraph")

            # Validate if requested
            if validate_immediately:
                validators = await self._validate_validators_batch(validators)

            # Cache results
            self._validators_cache = validators
            self._last_sync_time = time.time()

            discovery_time = time.time() - start_time
            logger.info(f"Validator discovery completed in {discovery_time:.2f}s")

            return validators

        except Exception as e:
            logger.error(f"Failed to discover validators: {e}")
            raise

    async def get_validators(
        self,
        force_refresh: bool = False,
        only_bitkoop: bool = False,
        only_available: bool = False,
    ) -> list[ValidatorInfo]:
        """
        Get validators with caching and filtering options

        Args:
            force_refresh: Force refresh from metagraph
            only_bitkoop: Return only confirmed BitKoop validators
            only_available: Return only available validators for submission

        Returns:
            List of ValidatorInfo objects
        """
        # Check cache
        if (
            not force_refresh
            and self._validators_cache is not None
            and self._last_sync_time is not None
            and time.time() - self._last_sync_time < self._cache_ttl
        ):
            validators = self._validators_cache
            logger.debug("Using cached validators")
        else:
            validators = await self.discover_validators()

        # Apply filters
        if only_available:
            validators = [v for v in validators if v.is_available_for_submission]
        elif only_bitkoop:
            validators = [
                v for v in validators if v.status == ValidatorStatus.BITKOOP_CONFIRMED
            ]

        return validators

    async def get_primary_validator(self) -> Optional[ValidatorInfo]:
        """
        Get the primary (best) validator for single submissions

        Returns:
            Best ValidatorInfo or None if no validators available
        """
        validators = await self.get_validators(only_available=True)

        if not validators:
            return None

        validators.sort(key=lambda v: v.priority_score, reverse=True)
        return validators[0]

    async def get_submission_validators(
        self, max_validators: Optional[int] = None
    ) -> list[ValidatorInfo]:
        """
        Get validators suitable for multi-validator submission

        Args:
            max_validators: Maximum number of validators to return

        Returns:
            List of ValidatorInfo objects sorted by priority
        """
        validators = await self.get_validators(only_available=True)

        validators.sort(key=lambda v: v.priority_score, reverse=True)

        if max_validators is not None:
            validators = validators[:max_validators]

        logger.info(f"Selected {len(validators)} validators for submission")
        return validators

    async def get_metagraph_info(self) -> MetagraphInfo:
        """
        Get comprehensive metagraph information

        Returns:
            MetagraphInfo object with network statistics
        """
        try:
            validators = await self.get_validators()

            total_validators = len(validators)
            reachable_validators = len(
                [v for v in validators if v.has_real_ip and v.is_reachable]
            )
            bitkoop_validators = len(
                [v for v in validators if v.status == ValidatorStatus.BITKOOP_CONFIRMED]
            )
            available_validators = len(
                [v for v in validators if v.is_available_for_submission]
            )

            total_stake = sum(v.stake for v in validators)

            response_times = [
                v.response_time for v in validators if v.response_time is not None
            ]
            avg_response_time = (
                sum(response_times) / len(response_times) if response_times else None
            )

            current_block = 0
            if self._substrate:
                try:
                    current_block = await self._substrate.get_block_number()
                except Exception:
                    pass

            return MetagraphInfo(
                netuid=self.network.netuid,
                network=self.network.name,
                block=current_block,
                sync_time=self._last_sync_time or time.time(),
                total_validators=total_validators,
                reachable_validators=reachable_validators,
                bitkoop_validators=bitkoop_validators,
                available_validators=available_validators,
                total_stake=total_stake,
                avg_response_time=avg_response_time,
                last_validation_time=time.time(),
            )

        except Exception as e:
            logger.error(f"Failed to get metagraph info: {e}")
            return MetagraphInfo(
                netuid=self.network.netuid,
                network=self.network.name,
                block=0,
                sync_time=time.time(),
                total_validators=0,
                reachable_validators=0,
                bitkoop_validators=0,
                available_validators=0,
                total_stake=0.0,
            )

    async def close(self):
        """Close substrate connection"""
        if self._substrate:
            try:
                await self._substrate.close()
                logger.debug("Substrate connection closed")
            except Exception as e:
                logger.warning(f"Error closing substrate: {e}")
            finally:
                self._substrate = None

    def clear_cache(self):
        """Clear validator cache"""
        self._validators_cache = None
        self._last_sync_time = None
        logger.debug("Validator cache cleared")


def create_metagraph_client(
    network_name: str = "finney",
    validator_check_timeout: int = 10,
    max_concurrent_checks: int = 10,
) -> MetagraphClient:
    """
    Create MetagraphClient instance

    Args:
        network_name: Network name (test/finney)
        validator_check_timeout: Timeout for validator checks in seconds
        max_concurrent_checks: Max concurrent validator checks

    Returns:
        MetagraphClient instance
    """
    network = NetworkType.from_name(network_name)
    return MetagraphClient(
        network=network,
        validator_check_timeout=validator_check_timeout,
        max_concurrent_checks=max_concurrent_checks,
    )
