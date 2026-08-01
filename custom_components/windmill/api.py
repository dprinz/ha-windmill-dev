"""Asynchronous, Home Assistant-independent Windmill API client."""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import aiohttp

from .const import DEFAULT_CONNECT_TIMEOUT, DEFAULT_REQUEST_TIMEOUT, MAX_RESPONSE_BYTES


class WindmillError(Exception):
    """Base exception for the Windmill client."""


class WindmillUrlError(WindmillError):
    """Raised when a base URL is invalid or unsafe."""


class WindmillConnectionError(WindmillError):
    """Raised when Windmill cannot be reached."""


class WindmillTimeoutError(WindmillConnectionError):
    """Raised when a Windmill request exceeds its deadline."""


class WindmillAuthenticationError(WindmillError):
    """Raised when Windmill rejects the token."""


class WindmillAuthorizationError(WindmillError):
    """Raised when the token lacks permission for an operation."""


class WindmillWorkspaceError(WindmillError):
    """Raised when the configured workspace is unavailable."""


class WindmillRequestError(WindmillError):
    """Raised when Windmill rejects a request."""


class WindmillRateLimitError(WindmillError):
    """Raised when Windmill rate-limits a request."""


class WindmillServerError(WindmillError):
    """Raised when Windmill reports a server failure."""


class WindmillProtocolError(WindmillError):
    """Raised when Windmill returns an unexpected response contract."""


@dataclass(frozen=True, slots=True)
class WindmillIdentity:
    """Bounded identity fields returned by the Windmill whoami endpoint."""

    username: str
    is_admin: bool
    is_super_admin: bool


def _is_loopback(host: str) -> bool:
    """Return whether a hostname is unambiguously local to the HA host."""
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def normalize_base_url(value: str) -> str:
    """Normalize and validate a Windmill base URL without weakening TLS."""
    if not isinstance(value, str) or not value.strip():
        raise WindmillUrlError("Base URL is required")

    raw_value = value.strip()
    try:
        parts = urlsplit(raw_value)
        port = parts.port
    except ValueError as err:
        raise WindmillUrlError("Base URL is invalid") from err

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.hostname:
        raise WindmillUrlError("Base URL must use HTTP or HTTPS")
    if parts.username is not None or parts.password is not None:
        raise WindmillUrlError("Base URL must not contain credentials")
    if parts.query or parts.fragment:
        raise WindmillUrlError("Base URL must not contain a query or fragment")

    try:
        host = parts.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as err:
        raise WindmillUrlError("Base URL hostname is invalid") from err
    if not host:
        raise WindmillUrlError("Base URL hostname is required")
    if scheme == "http" and not _is_loopback(host):
        raise WindmillUrlError("Remote Windmill instances must use HTTPS")

    path_segments: list[str] = []
    for raw_segment in parts.path.split("/"):
        if not raw_segment:
            continue
        try:
            segment = unquote(raw_segment, errors="strict")
        except UnicodeDecodeError as err:
            raise WindmillUrlError("Base URL path encoding is invalid") from err
        if (
            segment in {".", ".."}
            or "/" in segment
            or "\\" in segment
            or any(ord(char) < 32 or ord(char) == 127 for char in segment)
        ):
            raise WindmillUrlError("Base URL path contains an unsafe segment")
        path_segments.append(quote(segment, safe="!$&'()*+,-.:;=@_~"))
    path = f"/{'/'.join(path_segments)}" if path_segments else ""

    default_port = 443 if scheme == "https" else 80
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port in {None, default_port} else f"{display_host}:{port}"
    return urlunsplit((scheme, netloc, path, "", ""))


def normalize_workspace(value: str) -> str:
    """Normalize a workspace identifier for storage and URL construction."""
    if not isinstance(value, str):
        raise WindmillWorkspaceError("Workspace is required")
    workspace = value.strip()
    if not workspace or len(workspace) > 256 or any(ord(char) < 32 for char in workspace):
        raise WindmillWorkspaceError("Workspace is invalid")
    return workspace


class WindmillClient:
    """Small asynchronous client for the verified Windmill setup contract."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        workspace: str,
        token: str,
        *,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize the client with normalized non-secret connection identity."""
        self._session = session
        self.base_url = normalize_base_url(base_url)
        self.workspace = normalize_workspace(workspace)
        if not isinstance(token, str) or not token:
            raise WindmillAuthenticationError("Token is required")
        self._token = token
        self._timeout = aiohttp.ClientTimeout(total=request_timeout, connect=connect_timeout)

    @property
    def identity_key(self) -> tuple[str, str]:
        """Return the stable non-secret identity used for duplicate detection."""
        return (self.base_url, self.workspace)

    async def async_validate(self) -> WindmillIdentity:
        """Validate the token and workspace through the verified whoami endpoint."""
        await self._async_validate_version()
        url = f"{self.base_url}/api/w/{quote(self.workspace, safe='')}/users/whoami"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }

        status, content_type, payload = await self._async_get_bounded(url, headers)
        self._raise_for_status(status)
        if content_type != "application/json" and not content_type.endswith("+json"):
            raise WindmillProtocolError("Windmill returned an unexpected content type")

        try:
            data: Any = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise WindmillProtocolError("Windmill returned invalid JSON") from err
        return self._parse_identity(data)

    async def _async_validate_version(self) -> None:
        """Confirm the base deployment before classifying workspace-scoped failures."""
        status, content_type, payload = await self._async_get_bounded(
            f"{self.base_url}/api/version",
            {"Accept": "text/plain"},
        )
        if status == 429:
            raise WindmillRateLimitError("Windmill rate limited the request")
        if 500 <= status <= 599:
            raise WindmillServerError("Windmill server error")
        if status != 200:
            raise WindmillProtocolError("Windmill version endpoint is unavailable")
        if content_type != "text/plain":
            raise WindmillProtocolError("Windmill returned an unexpected version content type")
        try:
            version = payload.decode("utf-8").strip()
        except UnicodeDecodeError as err:
            raise WindmillProtocolError("Windmill returned an invalid version") from err
        if not re.fullmatch(r"(?:CE|EE)\s+\S+", version):
            raise WindmillProtocolError("Windmill returned an invalid version")

    async def _async_get_bounded(self, url: str, headers: dict[str, str]) -> tuple[int, str, bytes]:
        """GET one bounded response without following credential-sensitive redirects."""

        try:
            async with self._session.get(
                url,
                headers=headers,
                timeout=self._timeout,
                allow_redirects=False,
            ) as response:
                status = response.status
                if status != 200:
                    return status, "", b""
                content_type = (
                    response.headers.get("Content-Type", "").partition(";")[0].strip().lower()
                )
                content_length = response.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        if int(content_length) > MAX_RESPONSE_BYTES:
                            raise WindmillProtocolError("Windmill response is too large")
                    except ValueError as err:
                        raise WindmillProtocolError(
                            "Windmill returned an invalid content length"
                        ) from err
                payload = await response.content.read(MAX_RESPONSE_BYTES + 1)
        except TimeoutError as err:
            raise WindmillTimeoutError("Windmill request timed out") from err
        except aiohttp.ClientError as err:
            raise WindmillConnectionError("Unable to connect to Windmill") from err

        if len(payload) > MAX_RESPONSE_BYTES:
            raise WindmillProtocolError("Windmill response is too large")
        return status, content_type, payload

    @staticmethod
    def _raise_for_status(status: int) -> None:
        """Map HTTP statuses to the stable typed client taxonomy."""
        if status == 200:
            return
        if status == 401:
            raise WindmillAuthenticationError("Windmill rejected the token")
        if status == 403:
            raise WindmillAuthorizationError("Windmill denied workspace access")
        if status == 404:
            raise WindmillWorkspaceError("Windmill workspace was not found")
        if status == 429:
            raise WindmillRateLimitError("Windmill rate limited the request")
        if status in {400, 409, 422}:
            raise WindmillRequestError("Windmill rejected the request")
        if 500 <= status <= 599:
            raise WindmillServerError("Windmill server error")
        raise WindmillProtocolError("Windmill returned an unexpected status")

    @staticmethod
    def _parse_identity(data: Any) -> WindmillIdentity:
        """Allowlist and validate the bounded whoami response."""
        if not isinstance(data, dict):
            raise WindmillProtocolError("Windmill returned an invalid identity")
        username = data.get("username")
        is_admin = data.get("is_admin", False)
        is_super_admin = data.get("is_super_admin", False)
        if not isinstance(username, str) or not username.strip():
            raise WindmillProtocolError("Windmill returned an invalid identity")
        if not isinstance(is_admin, bool) or not isinstance(is_super_admin, bool):
            raise WindmillProtocolError("Windmill returned invalid role fields")
        return WindmillIdentity(
            username=username.strip(),
            is_admin=is_admin,
            is_super_admin=is_super_admin,
        )
