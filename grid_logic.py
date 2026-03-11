import grid_config as config


def build_grid(current_price: float) -> list:
    """
    Строит сетку из N уровней ниже текущей цены.
    Каждый уровень — словарь с ценой покупки, статусом и данными сделки.
    """
    grid = []
    for i in range(1, config.GRID_LEVELS + 1):
        buy_price = current_price * (1 - config.GRID_STEP * i)
        sell_target = buy_price * (1 + config.GRID_STEP + config.PROFIT_MARGIN)
        grid.append({
            "level": i,
            "buy_price": round(buy_price, 2),
            "sell_target": round(sell_target, 2),
            "status": "waiting",       # waiting -> bought -> sold
            "buy_volume_btc": 0.0,
            "actual_buy_price": 0.0,
            "price_high": 0.0,
            "trailing_stop": 0.0,
        })
    return grid


def calculate_trade_amount(deposit: float) -> float:
    """Размер одной сделки = депозит / кол-во уровней."""
    return deposit / config.GRID_LEVELS
