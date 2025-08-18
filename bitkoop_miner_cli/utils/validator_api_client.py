import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from bitkoop_miner_cli.utils.chain.metagraph.metagraph_client import (
    create_metagraph_client,
)

from .base_api_client import BaseAPIClient, BaseAPIConfig
from .supervisor_api_client import create_supervisor_client

logger = logging.getLogger(__name__)


class SubmissionStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"


@dataclass
class ValidatorInfo:
    url: str
    ip: str
    port: int
    hotkey: str
    hotkey_short: str
    stake: float
    priority_score: float
    status: str


@dataclass
class SubmissionResult:
    validator_url: str
    success: bool
    status: SubmissionStatus
    response_time: Optional[float] = None
    error: Optional[str] = None
    response_data: Optional[dict[str, Any]] = None


@dataclass
class ValidatorConfig:
    max_concurrent_submissions: int = 10
    base_config: Optional[BaseAPIConfig] = None
    metagraph_network: str = "finney"
    submission_endpoint: str = "coupons"
    delete_coupon_endpoint: str = "coupons/delete"
    recheck_coupon_endpoint: str = "coupons/recheck"


@dataclass
class SubmissionSummary:
    success: bool
    total_validators: int
    successful_submissions: int
    failed_submissions: int
    success_rate: float
    avg_response_time: Optional[float]
    results: list[SubmissionResult]
    total_time: float = 0.0


class ValidatorClientError(Exception):
    pass


class MetagraphError(ValidatorClientError):
    pass


class ValidatorClient:
    def __init__(self, config: Optional[ValidatorConfig] = None):
        self.config = config or ValidatorConfig()
        self._base_client = BaseAPIClient(self.config.base_config)

    async def __aenter__(self):
        await self._base_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def get_validator_urls(
        self, max_validators: Optional[int] = None
    ) -> list[str]:
        try:
            async with create_metagraph_client(
                self.config.metagraph_network
            ) as metagraph_client:
                validators = await metagraph_client.get_submission_validators(
                    max_validators
                )
                urls = [v.endpoint_url for v in validators if v.endpoint_url]
                # Remove duplicates while preserving order
                seen = set()
                unique_urls = []
                for url in urls:
                    if url not in seen:
                        seen.add(url)
                        unique_urls.append(url)

                logger.info(
                    f"Retrieved {len(unique_urls)} unique validator URLs from metagraph"
                )
                return unique_urls
        except Exception as e:
            logger.error(f"Failed to get validator URLs: {e}")
            raise MetagraphError(f"Failed to retrieve validator URLs: {e}") from e

    async def get_validator_details(
        self, max_validators: Optional[int] = None
    ) -> list[ValidatorInfo]:
        try:
            async with create_metagraph_client(
                self.config.metagraph_network
            ) as metagraph_client:
                validators = await metagraph_client.get_submission_validators(
                    max_validators
                )
                return [
                    ValidatorInfo(
                        url=v.endpoint_url,
                        ip=v.ip,
                        port=v.port,
                        hotkey=v.hotkey,
                        hotkey_short=v.hotkey_short,
                        stake=v.stake,
                        priority_score=v.priority_score,
                        status=getattr(v.status, "value", str(v.status)),
                    )
                    for v in validators
                ]
        except Exception as e:
            logger.error(f"Failed to get validator details: {e}")
            raise MetagraphError(f"Failed to retrieve validator details: {e}") from e

    def get_sites_sync(self) -> list[dict[str, Any]]:
        try:
            with create_supervisor_client() as supervisor_client:
                sites = supervisor_client.get_sites()
                return [
                    {
                        "id": site.id,
                        "domain": site.domain,
                        "status": site.status,
                        "miner_hotkey": site.miner_hotkey,
                    }
                    for site in sites
                ]
        except Exception as e:
            logger.error(f"Error getting sites: {e}")
            return []

    async def get_sites(self) -> list[dict[str, Any]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_sites_sync)

    async def _make_validator_request(
        self,
        validator_url: str,
        endpoint: str,
        method: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> SubmissionResult:
        url = f"{validator_url.rstrip('/')}/{endpoint}"
        start_time = time.time()

        try:
            logger.debug(f"{method} request to {validator_url}")
            logger.debug(f"Request URL: {url}")
            logger.debug(f"Request headers: {headers}")
            logger.debug(f"Request payload: {payload}")

            if method.upper() == "PUT":
                result = await self._base_client.put(
                    url, payload=payload, headers=headers
                )
            elif method.upper() == "POST":
                result = await self._base_client.post(
                    url, payload=payload, headers=headers
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response_time = time.time() - start_time
            logger.debug(f"Response received in {response_time:.2f}s: {result}")

            if result.get("success"):
                logger.info(
                    f"✅ {method} success: {validator_url} ({response_time:.2f}s)"
                )
                return SubmissionResult(
                    validator_url=validator_url,
                    success=True,
                    status=SubmissionStatus.SUCCESS,
                    response_time=response_time,
                    response_data=result,
                )
            else:
                error_msg = result.get("error", result.get("detail", "Unknown error"))
                logger.debug(f"Full error response: {result}")
                return SubmissionResult(
                    validator_url=validator_url,
                    success=False,
                    status=SubmissionStatus.FAILED,
                    response_time=response_time,
                    error=error_msg,
                    response_data=result,
                )

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            error_msg = f"Request timeout after {response_time:.2f}s"
            logger.error(f"⏰ Timeout: {validator_url}")
            return SubmissionResult(
                validator_url=validator_url,
                success=False,
                status=SubmissionStatus.TIMEOUT,
                response_time=response_time,
                error=error_msg,
            )
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"💥 Exception for {validator_url}: {e}")
            return SubmissionResult(
                validator_url=validator_url,
                success=False,
                status=SubmissionStatus.CONNECTION_ERROR,
                response_time=response_time,
                error=str(e),
            )

    async def _execute_on_validators(
        self,
        validator_urls: list[str],
        endpoint: str,
        method: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> list[SubmissionResult]:
        if not validator_urls:
            return []

        semaphore = asyncio.Semaphore(self.config.max_concurrent_submissions)

        async def execute_with_semaphore(url: str) -> SubmissionResult:
            async with semaphore:
                return await self._make_validator_request(
                    url, endpoint, method, payload, headers
                )

        tasks = [execute_with_semaphore(url) for url in validator_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Unexpected exception for {validator_urls[i]}: {result}")
                final_results.append(
                    SubmissionResult(
                        validator_url=validator_urls[i],
                        success=False,
                        status=SubmissionStatus.CONNECTION_ERROR,
                        error=f"Unexpected error: {str(result)}",
                    )
                )
            else:
                final_results.append(result)

        return final_results

    def _create_submission_summary(
        self, results: list[SubmissionResult], total_time: float
    ) -> SubmissionSummary:
        successful_results = [r for r in results if r.success]

        response_times = [
            r.response_time for r in successful_results if r.response_time is not None
        ]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else None
        )
        success_rate = (
            (len(successful_results) / len(results)) * 100 if results else 0.0
        )

        logger.info(
            f"Operation complete: {len(successful_results)}/{len(results)} successful ({success_rate:.1f}%) in {total_time:.2f}s"
        )

        return SubmissionSummary(
            success=len(successful_results) > 0,
            total_validators=len(results),
            successful_submissions=len(successful_results),
            failed_submissions=len(results) - len(successful_results),
            success_rate=success_rate,
            avg_response_time=avg_response_time,
            results=results,
            total_time=total_time,
        )

    async def submit_coupon_to_network(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        max_validators: Optional[int] = None,
    ) -> dict[str, Any]:
        start_time = time.time()

        try:
            validator_urls = await self.get_validator_urls(max_validators)
        except MetagraphError as e:
            logger.error(f"Failed to get validators: {e}")
            return self._create_error_response(
                "Failed to get validators", e, start_time
            )

        if not validator_urls:
            logger.warning("No validators available for submission")
            return self._create_error_response(
                "No validators available", "No validators found", start_time
            )

        coupon_code = payload.get("code", "unknown")
        logger.info(
            f"Submitting coupon '{coupon_code}' to {len(validator_urls)} validators"
        )

        results = await self._execute_on_validators(
            validator_urls, self.config.submission_endpoint, "PUT", payload, headers
        )
        summary = self._create_submission_summary(results, time.time() - start_time)

        return self._convert_summary_to_dict(summary)

    async def replace_coupon_across_network(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        max_validators: Optional[int] = None,
    ) -> dict[str, Any]:
        return await self._execute_network_operation(
            "replacement",
            self.config.submission_endpoint,
            "PATCH",
            payload,
            headers,
            max_validators,
        )

    async def delete_coupon_across_network(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        max_validators: Optional[int] = None,
    ) -> dict[str, Any]:
        return await self._execute_network_operation(
            "deletion",
            self.config.delete_coupon_endpoint,
            "POST",
            payload,
            headers,
            max_validators,
        )

    async def recheck_coupon_across_network(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
        max_validators: Optional[int] = None,
    ) -> dict[str, Any]:
        start_time = time.time()

        try:
            validator_urls = await self.get_validator_urls(max_validators)
        except MetagraphError as e:
            logger.error(f"Failed to get validators for recheck: {e}")
            return self._create_error_response(
                "Failed to get validators for recheck", e, start_time
            )

        if not validator_urls:
            return self._create_error_response(
                "No validators available for recheck",
                "No validators found",
                start_time,
            )

        logger.info(f"Executing recheck across {len(validator_urls)} validators")
        results = await self._execute_on_validators(
            validator_urls,
            self.config.recheck_coupon_endpoint,
            "POST",
            payload,
            headers,
        )

        total_time = time.time() - start_time
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]

        last_error = None
        if failed_results:
            error_messages = [r.error for r in failed_results if r.error]
            if error_messages:
                last_error = error_messages[0]

        # Format results array like submit does
        formatted_results = []
        for submission_result in results:
            formatted_results.append(
                {
                    "success": submission_result.success,
                    "validator_url": submission_result.validator_url,
                    "response_time": submission_result.response_time,
                    "error": submission_result.error,
                    "data": submission_result.response_data,
                }
            )

        return {
            "success": len(successful_results) > 0,
            "message": f"Coupon recheck completed: {len(successful_results)}/{len(results)} validators",
            "error": last_error,
            "total_validators": len(results),
            "successful_submissions": len(successful_results),
            "failed_submissions": len(failed_results),
            "success_rate": (len(successful_results) / len(results)) * 100
            if results
            else 0.0,
            "network": self.config.metagraph_network,
            "total_time": total_time,
            "results": formatted_results,  # ADD THIS for recheck
        }

    async def recheck_network_validators(
        self, max_validators: Optional[int] = None
    ) -> dict[str, Any]:
        start_time = time.time()

        try:
            validator_details = await self.get_validator_details(max_validators)
        except MetagraphError as e:
            logger.error(f"Failed to get validators for recheck: {e}")
            return {
                "success": False,
                "error": f"Failed to get validators: {e}",
                "network": self.config.metagraph_network,
                "total_time": time.time() - start_time,
            }

        if not validator_details:
            return {
                "success": False,
                "error": "No validators available for recheck",
                "network": self.config.metagraph_network,
                "recheck_stats": {
                    "total_validators": 0,
                    "healthy_validators": 0,
                    "unhealthy_validators": 0,
                },
                "total_time": time.time() - start_time,
            }

        logger.info(f"Rechecking {len(validator_details)} validators")
        results = await self._perform_health_checks(validator_details)
        total_time = time.time() - start_time
        healthy_count = sum(1 for r in results if r.get("healthy", False))

        return {
            "success": True,
            "message": f"Validator recheck completed: {healthy_count}/{len(results)} validators healthy",
            "network": self.config.metagraph_network,
            "recheck_stats": {
                "total_validators": len(results),
                "healthy_validators": healthy_count,
                "unhealthy_validators": len(results) - healthy_count,
                "health_percentage": (healthy_count / len(results)) * 100
                if results
                else 0.0,
                "details": results,
            },
            "total_time": total_time,
        }

    async def discover_validators(
        self, max_validators: Optional[int] = None
    ) -> list[ValidatorInfo]:
        return await self.get_validator_details(max_validators)

    async def _execute_network_operation(
        self,
        operation_name: str,
        endpoint: str,
        method: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        max_validators: Optional[int] = None,
    ) -> dict[str, Any]:
        start_time = time.time()

        try:
            validator_urls = await self.get_validator_urls(max_validators)
        except MetagraphError as e:
            logger.error(f"Failed to get validators for {operation_name}: {e}")
            return self._create_error_response(
                f"Failed to get validators for {operation_name}", e, start_time
            )

        if not validator_urls:
            return self._create_error_response(
                f"No validators available for {operation_name}",
                "No validators found",
                start_time,
            )

        logger.info(
            f"Executing {operation_name} across {len(validator_urls)} validators"
        )
        results = await self._execute_on_validators(
            validator_urls, endpoint, method, payload, headers
        )
        total_time = time.time() - start_time
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]

        last_error = None
        if failed_results:
            error_messages = [r.error for r in failed_results if r.error]
            if error_messages:
                last_error = error_messages[0]

        # Format results array like submit does
        formatted_results = []
        for submission_result in results:
            formatted_results.append(
                {
                    "success": submission_result.success,
                    "validator_url": submission_result.validator_url,
                    "response_time": submission_result.response_time,
                    "error": submission_result.error,
                    "data": submission_result.response_data,
                }
            )

        return {
            "success": len(successful_results) > 0,
            "message": f"Coupon {operation_name} completed: {len(successful_results)}/{len(results)} validators",
            "error": last_error,
            "total_validators": len(results),
            "successful_submissions": len(successful_results),
            "failed_submissions": len(results) - len(successful_results),
            "success_rate": (len(successful_results) / len(results)) * 100
            if results
            else 0.0,
            "network": self.config.metagraph_network,
            "total_time": total_time,
            "results": formatted_results,  # ADD THIS - include individual validator results
        }

    async def _perform_health_checks(
        self, validator_details: list[ValidatorInfo]
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(self.config.max_concurrent_submissions)

        async def check_validator_health(validator: ValidatorInfo) -> dict[str, Any]:
            async with semaphore:
                start_time = time.time()
                try:
                    health_url = f"{validator.url.rstrip('/')}/health"
                    result = await self._base_client.get(health_url)
                    response_time = time.time() - start_time
                    is_healthy = result.get("success", False) and response_time < 10.0

                    return {
                        "validator_url": validator.url,
                        "ip": validator.ip,
                        "port": validator.port,
                        "hotkey_short": validator.hotkey_short,
                        "stake": validator.stake,
                        "healthy": is_healthy,
                        "response_time": response_time,
                        "status": validator.status,
                        "error": None
                        if is_healthy
                        else result.get("error", "Health check failed"),
                    }
                except Exception as e:
                    response_time = time.time() - start_time
                    return {
                        "validator_url": validator.url,
                        "ip": validator.ip,
                        "port": validator.port,
                        "hotkey_short": validator.hotkey_short,
                        "stake": validator.stake,
                        "healthy": False,
                        "response_time": response_time,
                        "status": validator.status,
                        "error": str(e),
                    }

        tasks = [check_validator_health(validator) for validator in validator_details]
        return await asyncio.gather(*tasks, return_exceptions=False)

    def _create_error_response(
        self, message: str, error: Any, start_time: float
    ) -> dict[str, Any]:
        return {
            "success": False,
            "error": f"{message}: {error}",
            "total_validators": 0,
            "successful_submissions": 0,
            "failed_submissions": 0,
            "success_rate": 0.0,
            "network": self.config.metagraph_network,
            "total_time": time.time() - start_time,
        }

    def _convert_summary_to_dict(self, summary: SubmissionSummary) -> dict[str, Any]:
        result = {
            "success": summary.success,
            "total_validators": summary.total_validators,
            "successful_submissions": summary.successful_submissions,
            "failed_submissions": summary.failed_submissions,
            "success_rate": summary.success_rate,
            "avg_response_time": summary.avg_response_time,
            "total_time": summary.total_time,
            "network": self.config.metagraph_network,
            "results": [],
        }

        for submission_result in summary.results:
            result["results"].append(
                {
                    "success": submission_result.success,
                    "validator_url": submission_result.validator_url,
                    "response_time": submission_result.response_time,
                    "error": submission_result.error,
                    "data": submission_result.response_data,
                }
            )

        return result

    async def close(self):
        try:
            await self._base_client.close()
        except Exception as e:
            logger.error(f"Error closing base client: {e}")


def create_validator_client(
    max_concurrent_submissions: int = 10,
    timeout: int = 30,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    user_agent: str = "BitKoop-Miner-CLI/1.0",
) -> ValidatorClient:
    base_config = BaseAPIConfig(
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
        user_agent=user_agent,
    )

    validator_config = ValidatorConfig(
        max_concurrent_submissions=max_concurrent_submissions,
        base_config=base_config,
    )

    return ValidatorClient(validator_config)
