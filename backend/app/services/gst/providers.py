"""Provider boundary for GST filing and e-invoice/e-way bill integrations."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
import uuid
import httpx


class GstProvider(Protocol):
    """Contract implemented by sandbox/mock and deployment-specific providers."""

    async def submit(self, return_type: str, payload: dict[str, Any], idempotency_key: str) -> "ProviderResult":
        ...


@dataclass(frozen=True)
class ProviderResult:
    status: str
    provider: str
    correlation_id: str
    response: dict[str, Any]


class MockGstProvider:
    """Deterministic provider used for local development and automated tests."""

    async def submit(self, return_type: str, payload: dict[str, Any], idempotency_key: str) -> ProviderResult:
        correlation_id = f"MOCK-{idempotency_key[:20]}"
        return ProviderResult(
            status="accepted",
            provider="mock",
            correlation_id=correlation_id,
            response={
                "status": "accepted",
                "return_type": return_type,
                "acknowledgement_number": correlation_id,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "payload_hash_key": idempotency_key,
            },
        )


class HttpGstProvider:
    """Deployment-configured live adapter for a GSTN/GSP connector."""

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def submit(self, return_type: str, payload: dict[str, Any], idempotency_key: str) -> ProviderResult:
        headers = {"Idempotency-Key": idempotency_key, "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/returns/{return_type}/submit",
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise RuntimeError("GST provider could not be reached.") from exc
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text[:500]}
        if response.is_error:
            raise RuntimeError(f"GST provider rejected submission ({response.status_code}).")
        return ProviderResult(
            status="accepted",
            provider="live",
            correlation_id=str(body.get("correlation_id") or body.get("acknowledgement_number") or uuid.uuid4()),
            response=body,
        )


def make_idempotency_key(company_id: int, period_id: int, payload_hash: str) -> str:
    """Build a stable key so retries cannot submit a changed payload as the same filing."""
    return f"{company_id}:{period_id}:{payload_hash}"


def create_provider(environment: str, *, base_url: str | None = None, api_key: str | None = None) -> GstProvider:
    """Resolve a provider by environment; live adapters are intentionally deployment-bound."""
    if environment in {"mock", "sandbox"}:
        return MockGstProvider()
    if environment == "production" and base_url:
        return HttpGstProvider(base_url, api_key)
    raise RuntimeError("No live GST provider is configured for this deployment.")
