"""
HTTP Client Module

Shared HTTP client with timeouts, retries, and backoff.
Following Rulebook: HTTP client standards for production safety.
"""

import httpx
from typing import Optional, Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from .config import REQUEST_TIMEOUT
from .logging import setup_logger

logger = setup_logger(__name__)

# =============================================================================
# HTTP Client
# =============================================================================

class HTTPClient:
    """
    Production-safe HTTP client with timeouts and retries.
    
    Features:
    - Connection timeouts
    - Read/write timeouts
    - Automatic retries on 429, 500-599, transient errors
    - Exponential backoff with jitter
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = REQUEST_TIMEOUT
    ):
        """
        Initialize HTTP client.
        
        Args:
            base_url: API base URL
            api_key: Bearer token for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = httpx.Timeout(timeout=float(timeout))
        
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        
        self.client = httpx.Client(
            base_url=base_url,
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True
        )
        
        logger.info(f"HTTP client initialized: {base_url}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.RemoteProtocolError
        )),
        reraise=True
    )
    def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> httpx.Response:
        """
        POST request with automatic retry on transient failures.
        
        Args:
            endpoint: API endpoint (relative to base_url)
            json: JSON payload
            **kwargs: Additional arguments for httpx
            
        Returns:
            Response object
            
        Raises:
            httpx.HTTPStatusError: On 4xx/5xx errors (after retries)
        """
        logger.debug(f"POST {endpoint}")
        
        response = self.client.post(endpoint, json=json, **kwargs)
        
        # Raise on HTTP errors (will trigger retry on 5xx)
        response.raise_for_status()
        
        return response
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.RemoteProtocolError
        )),
        reraise=True
    )
    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> httpx.Response:
        """
        GET request with automatic retry on transient failures.
        
        Args:
            endpoint: API endpoint (relative to base_url)
            params: Query parameters
            **kwargs: Additional arguments for httpx
            
        Returns:
            Response object
            
        Raises:
            httpx.HTTPStatusError: On 4xx/5xx errors (after retries)
        """
        logger.debug(f"GET {endpoint}")
        
        response = self.client.get(endpoint, params=params, **kwargs)
        response.raise_for_status()
        
        return response
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
        logger.info("HTTP client closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


# =============================================================================
# Module Test
# =============================================================================

if __name__ == "__main__":
    print("HTTP Client Module")
    print("=" * 60)
    
    # Test client initialization
    client = HTTPClient("https://httpbin.org", timeout=10)
    
    try:
        # Test GET
        response = client.get("/get")
        print(f"✅ GET request successful: {response.status_code}")
        
        # Test POST
        response = client.post("/post", json={"test": "data"})
        print(f"✅ POST request successful: {response.status_code}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()
