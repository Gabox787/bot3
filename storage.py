import json
import os
import logging
from threading import Lock

logger = logging.getLogger(__name__)

STATS_FILE = "stats.json"
_lock = Lock()

DEFAULT_STATS = {
    "balance_usd": 1000.0,
    "total_profit_net": 0.0,
    "trades_count": 0,
    "wins_count": 0,
    "current_price": 0.0,
    "target_sell": 0.0,
    "target_buy": 0.0,
    "is_paused": False,
    "last_grid_update": 0.0,
    "last_buy_price": None,
    "last_buy_volume_btc": 0.0,
    "price_high": 0.0,
    "trailing_stop": 0.0,
    "closed_trades": []
}


def load_stats(initial_deposit: float) -> dict:
    """Загружает статистику из файла или создаёт дефолтную."""
    with _lock:
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, "r") as f:
                    loaded = json.load(f)
                # Дополняем недостающие ключи дефолтами
                for key, value in DEFAULT_STATS.items():
                    if key not in loaded:
                        loaded[key] = value
                logger.info(
                    f"Статистика загружена: {loaded['trades_count']} сделок, "
                    f"профит {loaded['total_profit_net']}$"
                )
                return loaded
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Ошибка чтения {STATS_FILE}: {e}. Создаю новый.")

        stats = DEFAULT_STATS.copy()
        stats["balance_usd"] = initial_deposit
        stats["closed_trades"] = []
        return stats


def save_stats(stats: dict):
    """Сохраняет статистику в файл (потокобезопасно)."""
    with _lock:
        try:
            with open(STATS_FILE, "w") as f:
                json.dump(stats, f, indent=2)
        except IOError as e:
            logger.error(f"Ошибка записи {STATS_FILE}: {e}")
