# === ТОРГОВЫЕ НАСТРОЙКИ ===
SYMBOL = "BTCUSDT"
IS_TESTNET = False

GRID_LEVELS = 7           # Количество уровней сетки
GRID_STEP = 0.004         # Шаг сетки (0.4%)
PROFIT_MARGIN = 0.0025    # Запас над комиссией (0.25%)

# === КОМИССИИ ===
FEE_RATE_BUY = 0.001      # 0.1% комиссия на покупку
FEE_RATE_SELL = 0.001     # 0.1% комиссия на продажу

# === ДЕПОЗИТ ===
INITIAL_DEPOSIT = 1000.0

# === ТАЙМЕРЫ ===
GRID_REFRESH_SECONDS = 180    # Обновление сетки (3 минуты)
POLL_INTERVAL = 5             # Интервал опроса цены (сек)
ERROR_COOLDOWN = 15           # Пауза после ошибки (сек)

# === АЛЕРТЫ ===
ALERT_THRESHOLD = 0.03       # Порог алерта волатильности (3%)
ALERT_WINDOW = 300           # Окно отслеживания (5 минут)

# === TRAILING STOP ===
TRAILING_ENABLED = True
TRAILING_OFFSET = 0.004      # Откат от максимума (0.4%)

# === TELEGRAM (основные — в env) ===
TELEGRAM_TOKEN = ""
CHAT_ID = ""
