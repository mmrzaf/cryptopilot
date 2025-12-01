from collections.abc import Mapping

from cryptopilot.providers.base import DataProviderBase
from cryptopilot.providers.coingecko import CoinGeckoProvider

_PROVIDER_REGISTRY: Mapping[str, type[DataProviderBase]] = {
    "coingecko": CoinGeckoProvider,
}


def get_provider_class(name: str) -> type[DataProviderBase]:
    """Resolve provider class by name (case-insensitive)."""
    key = name.lower()
    provider_cls = _PROVIDER_REGISTRY.get(key)
    if provider_cls is None:
        available = ", ".join(sorted(_PROVIDER_REGISTRY))
        raise ValueError(f"Unknown data provider '{name}'. Available: {available}")
    return provider_cls


def create_provider(
    name: str,
    api_key: str | None = None,
    *,
    request_timeout: int | None = None,
) -> DataProviderBase:
    """Instantiate a provider with common configuration hooks."""
    provider_cls = get_provider_class(name)

    session_kwargs: dict[str, object] = {}
    if request_timeout is not None:
        session_kwargs["request_timeout"] = float(request_timeout)

    return provider_cls(api_key=api_key, **session_kwargs)


def list_providers() -> list[str]:
    """List registered provider names."""
    return sorted(_PROVIDER_REGISTRY)
