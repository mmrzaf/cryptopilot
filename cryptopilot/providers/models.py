from __future__ import annotations

from enum import Enum


class Symbol(str, Enum):
    """Supported trading symbols.

    Centralized here so we don't scatter magic strings across the codebase.
    Extend this enum when you add more assets.
    """

    BTC = "BTC"
    ETH = "ETH"
    SOL = "SOL"
    BNB = "BNB"
    XRP = "XRP"
    ADA = "ADA"
    DOGE = "DOGE"
    DOT = "DOT"
    MATIC = "MATIC"
    LINK = "LINK"
    LTC = "LTC"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_string(cls, value: str) -> Symbol:
        """Parse a string into a Symbol.

        Handles things like:
        - "btc" -> BTC
        - "btc/usdt" -> BTC
        - "btc/usd" -> BTC
        """
        cleaned = value.strip().upper()
        for suffix in ("/USDT", "/USD"):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)]
                break

        try:
            return cls(cleaned)
        except ValueError as exc:
            options = ", ".join(sym.value for sym in cls)
            raise ValueError(
                f"Unsupported symbol '{value}'. "
                f"Supported symbols: {options}. "
                "Extend Symbol enum in cryptopilot.providers.models to add more."
            ) from exc

    @classmethod
    def list_values(cls) -> list[str]:
        """Return all symbol values as strings."""
        return [sym.value for sym in cls]
