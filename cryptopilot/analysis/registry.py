"""Strategy registry for discovering and instantiating analysis strategies."""

from collections.abc import Mapping

from cryptopilot.analysis.strategies.base import StrategyBase
from cryptopilot.analysis.strategies.mean_reversion import MeanReversionStrategy
from cryptopilot.analysis.strategies.momentum import MomentumStrategy
from cryptopilot.analysis.strategies.trend_following import TrendFollowingStrategy

# Registry of available strategies
_STRATEGY_REGISTRY: Mapping[str, type[StrategyBase]] = {
    "trend_following": TrendFollowingStrategy,
    "mean_reversion": MeanReversionStrategy,
    "momentum": MomentumStrategy,
}


def get_strategy_class(name: str) -> type[StrategyBase]:
    """Get strategy class by name.

    Args:
        name: Strategy name (case-insensitive)

    Returns:
        Strategy class

    Raises:
        ValueError: If strategy not found
    """
    key = name.lower().strip()
    strategy_cls = _STRATEGY_REGISTRY.get(key)

    if strategy_cls is None:
        available = ", ".join(sorted(_STRATEGY_REGISTRY.keys()))
        raise ValueError(f"Unknown strategy '{name}'. Available strategies: {available}")

    return strategy_cls


def create_strategy(name: str, **kwargs: object) -> StrategyBase:
    """Create strategy instance.

    Args:
        name: Strategy name
        **kwargs: Strategy-specific parameters

    Returns:
        Instantiated strategy

    Example:
        strategy = create_strategy("trend_following", fast_period=20, slow_period=50)
    """
    strategy_cls = get_strategy_class(name)
    return strategy_cls(**kwargs)


def list_strategies() -> list[str]:
    """List all registered strategy names.

    Returns:
        Sorted list of strategy names
    """
    return sorted(_STRATEGY_REGISTRY.keys())


def get_strategy_info() -> dict[str, dict[str, object]]:
    """Get information about all strategies.

    Returns:
        Dict of {strategy_name: {class, required_periods, ...}}
    """
    info: dict[str, dict[str, object]] = {}

    for name, strategy_cls in _STRATEGY_REGISTRY.items():
        instance = strategy_cls()
        info[name] = {
            "class": strategy_cls.__name__,
            "required_periods": instance.get_required_periods(),
            "description": strategy_cls.__doc__ or "No description",
        }

    return info
