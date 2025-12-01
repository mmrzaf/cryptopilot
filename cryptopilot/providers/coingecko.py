import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from cryptopilot.providers.base import (
    OHLCV,
    DataProviderBase,
    InvalidSymbolError,
    ProviderError,
    ProviderInfo,
    RateLimitError,
)

logger = logging.getLogger(__name__)


_TIMEFRAME_SECONDS: dict[str, int] = {
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}


class CoinGeckoProvider(DataProviderBase):
    """CoinGecko-based data provider.

    Notes:
        - Uses vs_currency=usd and treats it as USD-equivalent for now.
        - OHLCV is derived from market_chart/range price + volume series.

    """

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(
        self,
        api_key: str | None = None,
        request_timeout: int = 30,
    ) -> None:
        self._api_key = api_key
        self._timeout = request_timeout
        self._symbol_to_id: dict[str, str] = {}

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="coingecko",
            requires_api_key=False,  # key support is optional; not enforced
            rate_limit_per_minute=50,
            supported_timeframes=list(_TIMEFRAME_SECONDS.keys()),
            max_candles_per_request=5000,
            base_url=self.BASE_URL,
        )

    async def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.BASE_URL}{path}"
        headers: dict[str, str] = {}

        if self._api_key:
            headers["x-cg-pro-api-key"] = self._api_key

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params, headers=headers)
        except httpx.RequestError as exc:
            raise ProviderError(f"Network error calling CoinGecko: {exc}") from exc

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "1"))
            raise RateLimitError(retry_after=retry_after)

        if response.status_code >= 400:
            raise ProviderError(f"CoinGecko error {response.status_code}: {response.text}")

        return response.json()

    async def _ensure_symbol_map(self) -> None:
        if self._symbol_to_id:
            return

        data = await self._request("/coins/list", params={"include_platform": "false"})
        mapping: dict[str, str] = {}

        # Build initial mapping: first id for each symbol
        for item in data:
            sym = str(item.get("symbol", "")).upper()
            cid = str(item.get("id", "")).strip()
            if not sym or not cid:
                continue
            mapping.setdefault(sym, cid)

        if not mapping:
            raise ProviderError("Failed to load symbol list from CoinGecko")

        # Canonical overrides for common base assets we care about.
        # This prevents batcat / bridged tokens from hijacking BTC/ETH/SOL.
        preferred_ids: dict[str, str] = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }

        for sym, cid in preferred_ids.items():
            # Always force our preferred id, regardless of what came first.
            if sym in mapping and mapping[sym] != cid:
                logger.debug(
                    "Overriding CoinGecko id for %s: %s -> %s",
                    sym,
                    mapping[sym],
                    cid,
                )
            mapping[sym] = cid

        self._symbol_to_id = mapping
        logger.debug("Loaded %d symbols from CoinGecko", len(mapping))

    async def _get_coin_id(self, symbol: str) -> str:
        await self._ensure_symbol_map()
        norm = self._normalize_symbol(symbol)
        coin_id = self._symbol_to_id.get(norm)
        if not coin_id:
            raise InvalidSymbolError(f"Symbol not supported by CoinGecko: {symbol}")
        return coin_id

    async def validate_symbol(self, symbol: str) -> bool:
        try:
            await self._get_coin_id(symbol)
            return True
        except InvalidSymbolError:
            return False

    async def get_supported_symbols(self) -> list[str]:
        await self._ensure_symbol_map()
        return sorted(self._symbol_to_id.keys())

    async def get_current_price(self, symbol: str) -> Decimal:
        coin_id = await self._get_coin_id(symbol)
        data = await self._request(
            "/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd"},
        )

        try:
            price = data[coin_id]["usd"]
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"Unexpected response for current price: {data}") from exc

        return Decimal(str(price))

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[OHLCV]:
        """Fetch OHLCV using market_chart/range and aggregate to requested timeframe."""
        self._validate_timeframe(timeframe)
        seconds = _TIMEFRAME_SECONDS[timeframe]

        now = datetime.now(UTC)

        if end_time is None:
            end_dt = now
        else:
            end_dt = end_time if end_time.tzinfo is not None else end_time.replace(tzinfo=UTC)

        if start_time is None:
            # If no explicit start, default to a reasonable window.
            window = timedelta(days=90 if timeframe in {"1h", "4h"} else 365)
            start_dt = end_dt - window
        else:
            start_dt = (
                start_time if start_time.tzinfo is not None else start_time.replace(tzinfo=UTC)
            )

        if start_dt >= end_dt:
            return []

        coin_id = await self._get_coin_id(symbol)

        data = await self._request(
            f"/coins/{coin_id}/market_chart/range",
            params={
                "vs_currency": "usd",
                "from": int(start_dt.timestamp()),
                "to": int(end_dt.timestamp()),
            },
        )

        prices = data.get("prices") or []
        volumes = data.get("total_volumes") or []

        if not prices:
            return []

        # Aggregate into timeframe buckets using price + volume pairs
        buckets: dict[int, dict[str, Decimal]] = {}
        for price_item, vol_item in zip(prices, volumes):
            if len(price_item) < 2 or len(vol_item) < 2:
                continue

            ts_ms, price_val = price_item
            _, vol_val = vol_item

            ts_sec = int(ts_ms // 1000)
            if ts_sec < int(start_dt.timestamp()) or ts_sec > int(end_dt.timestamp()):
                continue

            bucket_index = ts_sec // seconds
            price_dec = Decimal(str(price_val))
            vol_dec = Decimal(str(vol_val))

            bucket = buckets.get(bucket_index)
            if bucket is None:
                buckets[bucket_index] = {
                    "open": price_dec,
                    "high": price_dec,
                    "low": price_dec,
                    "close": price_dec,
                    "volume": vol_dec,
                }
            else:
                bucket["close"] = price_dec
                if price_dec > bucket["high"]:
                    bucket["high"] = price_dec
                if price_dec < bucket["low"]:
                    bucket["low"] = price_dec
                bucket["volume"] += vol_dec

        candles: list[OHLCV] = []
        for bucket_index in sorted(buckets.keys()):
            bucket_start = bucket_index * seconds
            ts = datetime.fromtimestamp(bucket_start, tz=UTC)
            agg = buckets[bucket_index]
            candles.append(
                OHLCV(
                    timestamp=ts,
                    open=agg["open"],
                    high=agg["high"],
                    low=agg["low"],
                    close=agg["close"],
                    volume=agg["volume"],
                )
            )

        if limit is not None and len(candles) > limit:
            candles = candles[-limit:]

        return candles
