"""
Base API client with basic HTTP methods for BitKoop
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None
    logging.warning("aiohttp not available - API client will not work")


logger = logging.getLogger(__name__)


@dataclass
class BaseAPIConfig:
    """Configuration for base API client"""

    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    user_agent: str = "BitKoop-Miner-CLI/1.0"

    def __post_init__(self):
        """Validate configuration"""
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.retry_delay < 0:
            raise ValueError("retry_delay must be non-negative")


class BaseAPIClient:
    """
    Base API client with basic HTTP methods (GET, POST, PUT, DELETE)
    """

    def __init__(self, config: Optional[BaseAPIConfig] = None):
        self.config = config or BaseAPIConfig()
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def _ensure_session(self):
        """Ensure HTTP session is created"""
        if self._session is None:
            if aiohttp is None:
                raise RuntimeError("aiohttp not available")

            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": self.config.user_agent,
                },
            )

    def _extract_error_message(
        self, response_data: dict[str, Any], status_code: int
    ) -> str:
        """Extract meaningful error message from response"""
        if isinstance(response_data, dict):
            # Try common error fields
            for field in ["error", "message", "detail"]:
                if field in response_data:
                    return str(response_data[field])

            # Handle validation errors
            if "errors" in response_data:
                errors = response_data["errors"]
                if isinstance(errors, dict):
                    error_parts = []
                    for field, messages in errors.items():
                        if isinstance(messages, list):
                            error_parts.extend([f"{field}: {msg}" for msg in messages])
                        else:
                            error_parts.append(f"{field}: {messages}")
                    return "; ".join(error_parts)

        return f"HTTP {status_code} error"

    async def _make_request(
        self,
        method: str,
        url: str,
        payload: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        timeout_override: Optional[int] = None,
        retry_on_client_errors: bool = False,
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry logic

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Request URL
            payload: Request payload for POST/PUT requests
            headers: Additional headers
            params: URL parameters for GET requests
            timeout_override: Override default timeout
            retry_on_client_errors: Whether to retry 4xx errors

        Returns:
            Dictionary with response data and metadata
        """
        await self._ensure_session()

        # Merge headers
        request_headers = {}
        if headers:
            request_headers.update(headers)

        start_time = time.time()

        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug(
                    f"Making {method} request to {url} (attempt {attempt + 1})"
                )

                session_method = getattr(self._session, method.lower())

                request_kwargs = {"headers": request_headers}

                if payload and method.upper() in ["POST", "PUT", "PATCH"]:
                    request_kwargs["json"] = payload
                elif params and method.upper() == "GET":
                    request_kwargs["params"] = params

                if timeout_override:
                    request_kwargs["timeout"] = aiohttp.ClientTimeout(
                        total=timeout_override
                    )

                async with session_method(url, **request_kwargs) as response:
                    response_time = time.time() - start_time

                    try:
                        if response.content_length and response.content_length > 0:
                            response_data = await response.json()
                        else:
                            response_data = {}
                    except json.JSONDecodeError:
                        response_data = {"raw_response": await response.text()}

                    if response.status < 400:
                        logger.debug(
                            f"✅ {method} {url} - {response.status} ({response_time:.3f}s)"
                        )
                        return {
                            "success": True,
                            "data": response_data,
                            "status_code": response.status,
                            "response_time": response_time,
                            "headers": dict(response.headers),
                        }
                    else:
                        error_msg = self._extract_error_message(
                            response_data, response.status
                        )
                        logger.warning(f"❌ {method} {url} - {error_msg}")

                        if 400 <= response.status < 500 and not retry_on_client_errors:
                            return {
                                "success": False,
                                "data": response_data,
                                "error": error_msg,
                                "status_code": response.status,
                                "response_time": response_time,
                                "headers": dict(response.headers),
                            }

                        if attempt < self.config.max_retries:
                            await asyncio.sleep(self.config.retry_delay * (2**attempt))
                            continue

                        return {
                            "success": False,
                            "data": response_data,
                            "error": error_msg,
                            "status_code": response.status,
                            "response_time": response_time,
                            "headers": dict(response.headers),
                        }

            except asyncio.TimeoutError:
                response_time = time.time() - start_time
                error_msg = f"Timeout after {timeout_override or self.config.timeout}s"

                if attempt < self.config.max_retries:
                    logger.warning(f"🔄 {method} {url} - {error_msg} - retrying...")
                    await asyncio.sleep(self.config.retry_delay)
                    continue

                logger.error(f"❌ {method} {url} - {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "response_time": response_time,
                }

            except Exception as e:
                response_time = time.time() - start_time
                error_msg = f"Network error: {str(e)}"

                if attempt < self.config.max_retries:
                    logger.warning(f"🔄 {method} {url} - {error_msg} - retrying...")
                    await asyncio.sleep(self.config.retry_delay)
                    continue

                logger.error(f"❌ {method} {url} - {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "response_time": response_time,
                }

        return {
            "success": False,
            "error": "Max retries exceeded",
            "response_time": time.time() - start_time,
        }

    async def get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout_override: Optional[int] = None,
    ) -> dict[str, Any]:
        """Make GET request"""
        return await self._make_request(
            "GET",
            url,
            params=params,
            headers=headers,
            timeout_override=timeout_override,
        )

    async def post(
        self,
        url: str,
        payload: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout_override: Optional[int] = None,
    ) -> dict[str, Any]:
        """Make POST request"""
        return await self._make_request(
            "POST",
            url,
            payload=payload,
            headers=headers,
            timeout_override=timeout_override,
        )

    async def put(
        self,
        url: str,
        payload: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout_override: Optional[int] = None,
    ) -> dict[str, Any]:
        """Make PUT request"""
        return await self._make_request(
            "PUT",
            url,
            payload=payload,
            headers=headers,
            timeout_override=timeout_override,
        )

    async def delete(
        self,
        url: str,
        payload: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout_override: Optional[int] = None,
    ) -> dict[str, Any]:
        """Make DELETE request"""
        return await self._make_request(
            "DELETE",
            url,
            payload=payload,
            headers=headers,
            timeout_override=timeout_override,
        )

    async def close(self):
        """Close HTTP session"""
        if self._session:
            await self._session.close()
            self._session = None
            logger.debug("HTTP session closed")


def create_base_client(
    timeout: int = 30,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    user_agent: str = "BitKoop-Miner-CLI/1.0",
) -> BaseAPIClient:
    """
    Create BaseAPIClient with configuration

    Args:
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries
        user_agent: User agent string

    Returns:
        BaseAPIClient instance for basic HTTP operations
    """
    config = BaseAPIConfig(
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
        user_agent=user_agent,
    )
    return BaseAPIClient(config)
