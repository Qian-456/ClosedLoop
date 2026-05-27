import socket
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx

from closedloop.core.logger import logger


PlanSubNetworkMode = Literal["local", "docker"]


def _extract_plan_sub_base_url(configured_url: str) -> str:
    """Extract the plan_sub service base URL from a configured endpoint."""
    normalized = (configured_url or "").strip().rstrip("/")
    if not normalized:
        return ""
    parsed = urlsplit(normalized)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return normalized


def _build_default_plan_sub_bases(network_mode: PlanSubNetworkMode) -> list[str]:
    """Build environment-specific default base URLs for plan_sub service."""
    if network_mode == "docker":
        return [
            "http://plan_sub_backend:8001",
        ]
    return [
        "http://localhost:8001",
        "http://127.0.0.1:8001",
    ]


def build_plan_sub_candidate_urls(
    configured_url: str,
    target_path: str,
    network_mode: PlanSubNetworkMode = "local",
) -> list[str]:
    """Build ordered candidate URLs for plan_sub service requests."""
    normalized_target = target_path if target_path.startswith("/") else f"/{target_path}"
    seen: set[str] = set()
    candidates: list[str] = []

    raw_bases = [_extract_plan_sub_base_url(configured_url), *_build_default_plan_sub_bases(network_mode)]

    for raw_base in raw_bases:
        base_url = (raw_base or "").strip().rstrip("/")
        if not base_url:
            continue
        full_url = f"{base_url}{normalized_target}"
        if full_url not in seen:
            seen.add(full_url)
            candidates.append(full_url)

    return candidates


def request_plan_sub_json(
    method: str,
    configured_url: str,
    target_path: str,
    phase: str,
    timeout: float,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    network_mode: PlanSubNetworkMode = "local",
) -> dict[str, Any]:
    """Request plan_sub JSON with multi-address fallback."""
    candidate_urls = build_plan_sub_candidate_urls(configured_url, target_path, network_mode=network_mode)
    request_method = method.upper()
    last_error: Exception | None = None

    with httpx.Client(timeout=timeout, trust_env=False, proxy=None) as client:
        for candidate_url in candidate_urls:
            try:
                logger.info(
                    f"phase={phase} | msg=plan_sub_api_attempt | method={request_method} | url={candidate_url}"
                )
                response = client.request(
                    request_method,
                    candidate_url,
                    json=json,
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()
                logger.info(
                    f"phase={phase} | msg=plan_sub_api_success | method={request_method} | url={candidate_url}"
                )
                return payload
            except socket.gaierror as error:
                last_error = error
                logger.warning(
                    f"phase={phase} | msg=plan_sub_api_dns_failed | method={request_method} | url={candidate_url} | error={error}"
                )
            except httpx.ConnectError as error:
                last_error = error
                logger.warning(
                    f"phase={phase} | msg=plan_sub_api_connect_failed | method={request_method} | url={candidate_url} | error={error}"
                )
            except httpx.HTTPError as error:
                last_error = error
                logger.warning(
                    f"phase={phase} | msg=plan_sub_api_http_failed | method={request_method} | url={candidate_url} | error={error}"
                )
            except Exception as error:
                last_error = error
                logger.warning(
                    f"phase={phase} | msg=plan_sub_api_failed | method={request_method} | url={candidate_url} | error={error}"
                )

    raise RuntimeError(last_error or "plan_sub_api_all_candidates_failed")
