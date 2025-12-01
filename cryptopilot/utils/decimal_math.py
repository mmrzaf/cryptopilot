"""Safe decimal arithmetic operations for financial calculations.

NEVER use floating-point arithmetic for money.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

PRICE_PRECISION = Decimal("0.00000001")  # 8 decimal places (crypto standard)
QUANTITY_PRECISION = Decimal("0.00000001")  # 8 decimal places
USD_PRECISION = Decimal("0.01")  # 2 decimal places for USD


class DecimalError(Exception):
    """Base exception for decimal operations."""

    pass


def to_decimal(value: int | float | str | Decimal) -> Decimal:
    """Safely convert various types to Decimal.

    Args:
        value: Value to convert

    Returns:
        Decimal representation

    Raises:
        DecimalError: If conversion fails

    """
    if isinstance(value, Decimal):
        return value

    try:
        if isinstance(value, float):
            value_str = f"{value:.8f}"
        else:
            value_str = str(value)

        return Decimal(value_str)
    except (InvalidOperation, ValueError) as e:
        raise DecimalError(f"Cannot convert {value} to Decimal: {e}")


def round_price(value: Decimal, precision: Decimal = PRICE_PRECISION) -> Decimal:
    """Round price to specified precision.

    Args:
        value: Price to round
        precision: Precision level (default: 8 decimals)

    Returns:
        Rounded price

    """
    return value.quantize(precision, rounding=ROUND_HALF_UP)


def round_quantity(value: Decimal, precision: Decimal = QUANTITY_PRECISION) -> Decimal:
    """Round quantity to specified precision.

    Args:
        value: Quantity to round
        precision: Precision level (default: 8 decimals)

    Returns:
        Rounded quantity

    """
    return value.quantize(precision, rounding=ROUND_HALF_UP)


def round_usd(value: Decimal, precision: Decimal = USD_PRECISION) -> Decimal:
    """Round USD amount to specified precision.

    Args:
        value: USD amount to round
        precision: Precision level (default: 2 decimals)

    Returns:
        Rounded USD amount

    """
    return value.quantize(precision, rounding=ROUND_HALF_UP)


def calculate_total_cost(
    quantity: Decimal,
    price: Decimal,
    fee: Decimal = Decimal("0"),
) -> Decimal:
    """Calculate total cost of a trade.

    Args:
        quantity: Amount purchased
        price: Price per unit
        fee: Transaction fee

    Returns:
        Total cost in USD

    """
    subtotal = quantity * price
    total = subtotal + fee
    return round_usd(total)


def calculate_average_cost_basis(
    existing_quantity: Decimal,
    existing_cost_basis: Decimal,
    new_quantity: Decimal,
    new_price: Decimal,
) -> Decimal:
    """Calculate new average cost basis after adding to position.

    Args:
        existing_quantity: Current holding quantity
        existing_cost_basis: Current average cost per unit
        new_quantity: Quantity being added
        new_price: Price per unit of new purchase

    Returns:
        New average cost basis

    """
    if existing_quantity < 0 or new_quantity <= 0:
        raise DecimalError("Quantities must be non-negative")

    if existing_quantity == 0:
        return round_price(new_price)

    total_cost = (existing_quantity * existing_cost_basis) + (new_quantity * new_price)
    total_quantity = existing_quantity + new_quantity

    return round_price(total_cost / total_quantity)


def calculate_unrealized_pnl(
    quantity: Decimal,
    cost_basis: Decimal,
    current_price: Decimal,
) -> tuple[Decimal, Decimal]:
    """Calculate unrealized profit/loss.

    Args:
        quantity: Current holding quantity
        cost_basis: Average cost per unit
        current_price: Current market price

    Returns:
        Tuple of (absolute_pnl, percentage_pnl)

    """
    if quantity <= 0:
        return Decimal("0"), Decimal("0")

    cost = quantity * cost_basis
    value = quantity * current_price

    absolute_pnl = round_usd(value - cost)

    if cost == 0:
        percentage_pnl = Decimal("0")
    else:
        percentage_pnl = ((value - cost) / cost) * 100
        percentage_pnl = percentage_pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return absolute_pnl, percentage_pnl


def calculate_realized_pnl(
    quantity_sold: Decimal,
    cost_basis: Decimal,
    sell_price: Decimal,
    sell_fee: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal]:
    """Calculate realized profit/loss from a sale.

    Args:
        quantity_sold: Quantity being sold
        cost_basis: Average cost per unit
        sell_price: Selling price per unit
        sell_fee: Transaction fee for the sale

    Returns:
        Tuple of (absolute_pnl, percentage_pnl)

    """
    if quantity_sold <= 0:
        raise DecimalError("Quantity sold must be positive")

    cost = quantity_sold * cost_basis
    revenue = (quantity_sold * sell_price) - sell_fee

    absolute_pnl = round_usd(revenue - cost)

    if cost == 0:
        percentage_pnl = Decimal("0")
    else:
        percentage_pnl = ((revenue - cost) / cost) * 100
        percentage_pnl = percentage_pnl.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return absolute_pnl, percentage_pnl


def calculate_portfolio_value(
    holdings: dict[str, tuple[Decimal, Decimal]],
) -> Decimal:
    """Calculate total portfolio value.

    Args:
        holdings: Dict of {symbol: (quantity, current_price)}

    Returns:
        Total portfolio value in USDT

    """
    total = Decimal("0")

    for symbol, (quantity, price) in holdings.items():
        if symbol.upper() == "USD":
            total += quantity
        else:
            total += quantity * price

    return round_usd(total)


def is_dust(quantity: Decimal, min_threshold: Decimal = Decimal("0.00000001")) -> bool:
    """Check if quantity is considered "dust" (too small to matter).

    Args:
        quantity: Quantity to check
        min_threshold: Minimum meaningful quantity

    Returns:
        True if quantity is dust

    """
    return abs(quantity) < min_threshold


def safe_divide(
    numerator: Decimal,
    denominator: Decimal,
    default: Decimal = Decimal("0"),
) -> Decimal:
    """Safely divide two decimals, returning default on division by zero.

    Args:
        numerator: Top value
        denominator: Bottom value
        default: Value to return if denominator is zero

    Returns:
        Division result or default

    """
    if denominator == 0:
        return default
    return numerator / denominator


def percentage_change(old_value: Decimal, new_value: Decimal) -> Decimal:
    """Calculate percentage change between two values.

    Args:
        old_value: Original value
        new_value: New value

    Returns:
        Percentage change (e.g., 25.00 for 25% increase)

    """
    if old_value == 0:
        return Decimal("0") if new_value == 0 else Decimal("100")

    change = ((new_value - old_value) / old_value) * 100
    return change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
