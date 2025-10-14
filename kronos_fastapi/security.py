"""Security middleware for container-to-container authentication."""

import logging
import socket
from typing import Optional, Set

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Settings
from .metrics import SECURITY_EVENTS

logger = logging.getLogger(__name__)


class ContainerWhitelistMiddleware(BaseHTTPMiddleware):
    """Middleware to restrict access to whitelisted containers only."""

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.whitelist = self._parse_whitelist(settings.container_whitelist)
        self.enabled = settings.security_enabled

        if self.enabled:
            logger.info(f"Container whitelist enabled: {self.whitelist}")
        else:
            logger.warning("Container whitelist DISABLED - all containers allowed")

    def _parse_whitelist(self, whitelist_str: str) -> Set[str]:
        """Parse comma-separated whitelist into set."""
        if not whitelist_str:
            return set()
        return {name.strip() for name in whitelist_str.split(",") if name.strip()}

    def _extract_container_name(self, request: Request) -> Optional[str]:
        """Extract container name from request.

        Tries multiple methods:
        1. X-Container-Name header (if consumer sets it)
        2. Reverse DNS lookup of client IP
        3. Direct hostname from client IP
        """
        # Method 1: Check custom header
        container_name = request.headers.get("X-Container-Name")
        if container_name:
            return container_name

        # Method 2: Get client IP and do reverse DNS
        client_host = request.client.host if request.client else None
        if not client_host:
            return None

        # Allow localhost for development
        if client_host in ("127.0.0.1", "::1", "localhost"):
            return "localhost"

        try:
            # Docker containers can resolve each other by container name
            hostname, _, _ = socket.gethostbyaddr(client_host)
            return hostname
        except (socket.herror, socket.gaierror):
            # If reverse DNS fails, use IP
            logger.debug(f"Could not resolve hostname for {client_host}")
            return client_host

    async def dispatch(self, request: Request, call_next):
        """Check if requesting container is whitelisted."""

        # Skip security checks if disabled
        if not self.enabled:
            return await call_next(request)

        # Skip health checks (needed for Docker healthcheck)
        if request.url.path in ["/v1/healthz", "/v1/readyz", "/metrics", "/v1/metrics"]:
            return await call_next(request)

        # Extract container name
        container_name = self._extract_container_name(request)

        # Check whitelist
        if container_name and container_name in self.whitelist:
            logger.info(f"Authorized request from container: {container_name}")
            SECURITY_EVENTS.labels(event="authorized", container=container_name).inc()
            return await call_next(request)

        # Unauthorized access
        logger.warning(
            f"Unauthorized access attempt from container: {container_name or 'unknown'} "
            f"(IP: {request.client.host if request.client else 'unknown'})"
        )
        SECURITY_EVENTS.labels(event="unauthorized", container=container_name or "unknown").inc()

        return Response(
            content='{"error": "Forbidden", "message": "Container not whitelisted"}',
            status_code=status.HTTP_403_FORBIDDEN,
            media_type="application/json",
        )
