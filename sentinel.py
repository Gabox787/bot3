import asyncio
import os
import logging
import time
from functools import wraps
from datetime import datetime
from threading import Thread

import grid_config as config
from grid_logic import build_grid, calculate_trade_amount
from storage import load_stats, save_stats
from pybit.unified_trading import HTTP
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask

# ─── Логи ───
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("sentinel")

# ─── Flask keep-alive ───
flask_app = Flask('')
start_time_dt = datetime.now()

@flask_app.route('/')
def home():
    uptime = datetime.now() - start_time_dt
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes = remainder // 60
    return f"Bybit Sentinel alive | Uptime: {hours}h {minutes}m"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ─── Глобальное состояние ───
stats = load_stats(config.INITIAL_DEPOSIT)
grid = []
price_history = []


# ─── Декоратор доступа ───
def restricted(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        allowed = str(os.getenv("CHAT_ID", config.CHAT_ID))
        if chat_id != allowed:
            await update.message.reply_text("⛔ Доступ запрещён.")
            return
        return await func(update, context)
    return wrapper


# ══════════════════════════════════════
#           КОМАНДЫ TELEGRAM
# ══════════════════════════════════════

@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - start_time_dt
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes = remainder // 60
    active = sum(1 for o in grid if o["status"] == "bought")
    waiting = sum(1 for o in grid if o["status"] == "waiting")
    msg = (
        f"🤖 <b>Bybit Sentinel</b> — онлайн\n"
        f"⏱ Аптайм: {hours}ч {minutes}мин\n"
        f"💰 Депозит: <code>{round(stats['balance_usd'], 2)}$</code>\n"
        f"📊 Пара: {config.SYMBOL}\n"
        f"📶 Сетка: {active} активных / {waiting} ожидают\n"
        f"{'⏸ БОТ НА ПАУЗЕ' if stats.get('is_paused') else '▶️ Торговля активна'}"
    )
    await update.message.reply_text(msg, parse_mode='HTML')


@restricted
async def trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = round(stats['current_price'], 2)
    header = f"🪙 <b>{config.SYMBOL}:</b> <code>{price}</code> USDT\n"
    header += f"💰 Депозит: <code>{round(stats['balance_usd'], 2)}$</code>\n\n"

    if not grid:
        await update.message.reply_text(
            header + "📭 Сетка пуста. Ожидание инициализации...",
            parse_mode='HTML'
        )
        return

    lines = []
    for order in grid:
        if order["status"] == "bought":
            pnl = ((price - order["actual_buy_price"]) / order["actual_buy_price"]) * 100
            sign = "📈" if pnl >= 0 else "📉"
            lines.append(
                f"{sign} <b>Ур.{order['level']}</b> | "
                f"Вход: <code>{order['actual_buy_price']}</code> → "
                f"Цель: <code>{order['sell_target']}</code> "
                f"({round(pnl, 2)}%)"
            )
        elif order["status"] == "waiting":
            lines.append(
                f"⏳ <b>Ур.{order['level']}</b> | "
                f"BUY на <code>{order['buy_price']}</code>"
            )

    if not lines:
        lines.append("📭 Нет активных ордеров.")

    await update.message.reply_text(header + "\n".join(lines), parse_mode='HTML')


@restricted
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = stats["trades_count"]
    w = stats["wins_count"]
    winrate = (w / t * 100) if t > 0 else 0

    floating_pnl = 0.0
    trade_amount = calculate_trade_amount(config.INITIAL_DEPOSIT)
    for order in grid:
        if order["status"] == "bought":
            current_value = order["buy_volume_btc"] * stats["current_price"]
            floating_pnl += current_value - trade_amount

    last_trades = stats.get("closed_trades", [])[-5:]
    history = ""
    if last_trades:
        history = "\n\n📋 <b>Последние сделки:</b>\n"
        for tr in last_trades:
            emoji = "✅" if tr["profit"] > 0 else "❌"
            history += (
                f"{emoji} {tr['date']} | "
                f"+<code>{round(tr['profit'], 4)}$</code>\n"
            )

    msg = (
        f"📈 <b>СТАТИСТИКА</b>\n\n"
        f"🏆 Винрейт: <code>{round(winrate, 1)}%</code> ({w}/{t})\n"
        f"💵 Зафиксировано: <code>{round(stats['total_profit_net'], 4)}$</code>\n"
        f"📊 Плавающий PnL: <code>{round(floating_pnl, 4)}$</code>\n"
        f"💰 Баланс: <code>{round(stats['balance_usd'], 2)}$</code>"
        f"{history}"
    )
    await update.message.reply_text(msg, parse_mode='HTML')


@restricted
async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats["is_paused"] = True
    save_stats(stats)
    await update.message.reply_text("⏸ Бот на паузе. Новые сделки не открываются.")


@restricted
async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats["is_paused"] = False
    save_stats(stats)
    await update.message.reply_text("▶️ Торговля возобновлена!")


@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 <b>Команды Bybit Sentinel</b>\n\n"
        "/start — статус бота и аптайм\n"
        "/trades — активные ордера и сетка\n"
        "/stats — статистика и история сделок\n"
        "/pause — приостановить торговлю\n"
        "/resume — возобновить торговлю\n"
        "/help — эта справка"
    )
    await update.message.reply_text(msg, parse_mode='HTML')


# ══════════════════════════════════════
#         МОНИТОРИНГ РЫНКА
# ══════════════════════════════════════

async def check_volatility(bot, current_price: float):
    now = time.time()
    price_history.append((now, current_price))

    cutoff = now - config.ALERT_WINDOW
    while price_history and price_history[0][0] < cutoff:
        price_history.pop(0)

    if len(price_history) >= 2:
        oldest_price = price_history[0][1]
        change = abs(current_price - oldest_price) / oldest_price
        if change >= config.ALERT_THRESHOLD:
            direction = "🟢 рост" if current_price > oldest_price else "🔴 падение"
            await bot.send_message(
                chat_id=os.getenv("CHAT_ID", config.CHAT_ID),
                text=(
                    f"⚠️ <b>Алерт волатильности!</b>\n"
                    f"{direction} <code>{round(change * 100, 1)}%</code> "
                    f"за {config.ALERT_WINDOW // 60} мин\n"
                    f"Цена: <code>{round(current_price, 2)}</code>"
                ),
                parse_mode='HTML'
            )
            price_history.clear()


async def monitor_market(bot):
    global grid

    chat_id = os.getenv("CHAT_ID", config.CHAT_ID)
    session = HTTP(testnet=config.IS_TESTNET)
    trade_amount = calculate_trade_amount(config.INITIAL_DEPOSIT)

    res = session.get_tickers(category="spot", symbol=config.SYMBOL)
    current_price = float(res['result']['list'][0]['lastPrice'])
    stats["current_price"] = current_price

    grid = build_grid(current_price)
    stats["last_grid_update"] = time.time()
    logger.info(
        f"Сетка построена от цены {current_price}. "
        f"Уровни: {[o['buy_price'] for o in grid]}"
    )

    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"🚀 <b>Sentinel запущен!</b>\n"
            f"💰 Депозит: <code>{config.INITIAL_DEPOSIT}$</code>\n"
            f"📶 Уровней: {config.GRID_LEVELS}\n"
            f"📊 Шаг: {config.GRID_STEP * 100}%\n"
            f"💲 Цена: <code>{round(current_price, 2)}</code>\n"
            f"🎯 Первый BUY: <code>{grid[0]['buy_price']}</code>"
        ),
        parse_mode='HTML'
    )

    while True:
        try:
            res = session.get_tickers(category="spot", symbol=config.SYMBOL)
            current_price = float(res['result']['list'][0]['lastPrice'])
            stats["current_price"] = current_price

            await check_volatility(bot, current_price)

            if stats.get("is_paused"):
                await asyncio.sleep(config.POLL_INTERVAL)
                continue

            # ── Обновление сетки по таймеру ──
            if time.time() - stats["last_grid_update"] > config.GRID_REFRESH_SECONDS:
                any_updated = False
                for order in grid:
                    if order["status"] == "waiting":
                        new_buy = round(
                            current_price * (1 - config.GRID_STEP * order["level"]),
                            2
                        )
                        if new_buy != order["buy_price"]:
                            order["buy_price"] = new_buy
                            order["sell_target"] = round(
                                new_buy * (1 + config.GRID_STEP + config.PROFIT_MARGIN),
                                2
                            )
                            any_updated = True

                stats["last_grid_update"] = time.time()
                if any_updated:
                    logger.info(
                        f"Сетка обновлена. Waiting-уровни: "
                        f"{[o['buy_price'] for o in grid if o['status'] == 'waiting']}"
                    )

            # ── Логика BUY ──
            for order in grid:
                if order["status"] != "waiting":
                    continue

                if current_price <= order["buy_price"]:
                    if stats["balance_usd"] < trade_amount:
                        logger.warning(
                            f"Баланс {stats['balance_usd']}$ < "
                            f"размер сделки {trade_amount}$. Пропуск ур.{order['level']}"
                        )
                        continue

                    order["status"] = "bought"
                    order["actual_buy_price"] = current_price
                    order["buy_volume_btc"] = (
                        (trade_amount * (1 - config.FEE_RATE_BUY)) / current_price
                    )
                    order["sell_target"] = round(
                        current_price * (1 + config.GRID_STEP + config.PROFIT_MARGIN),
                        2
                    )
                    order["price_high"] = current_price
                    order["trailing_stop"] = 0.0

                    stats["balance_usd"] -= trade_amount

                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"📉 <b>BUY</b> ур.{order['level']}\n"
                            f"💲 Цена: <code>{current_price}</code>\n"
                            f"🎯 Цель: <code>{order['sell_target']}</code>\n"
                            f"💰 Остаток: <code>{round(stats['balance_usd'], 2)}$</code>"
                        ),
                        parse_mode='HTML'
                    )

                    save_stats(stats)
                    logger.info(
                        f"BUY ур.{order['level']} по {current_price}, "
                        f"цель {order['sell_target']}"
                    )

            # ── Логика SELL ──
            for order in grid:
                if order["status"] != "bought":
                    continue

                if current_price > order["price_high"]:
                    order["price_high"] = current_price
                    order["trailing_stop"] = round(
                        current_price * (1 - config.TRAILING_OFFSET), 2
                    )

                should_sell = False

                if config.TRAILING_ENABLED and current_price >= order["sell_target"]:
                    if (order["trailing_stop"] > 0
                            and current_price <= order["trailing_stop"]):
                        should_sell = True
                elif not config.TRAILING_ENABLED:
                    if current_price >= order["sell_target"]:
                        should_sell = True

                if should_sell:
                    sell_price = current_price
                    net_proceeds = (
                        order["buy_volume_btc"] * sell_price
                    ) * (1 - config.FEE_RATE_SELL)
                    profit = net_proceeds - trade_amount

                    stats["total_profit_net"] += profit
                    stats["balance_usd"] += trade_amount + profit
                    stats["trades_count"] += 1
                    if profit > 0:
                        stats["wins_count"] += 1

                    stats.setdefault("closed_trades", []).append({
                        "date": datetime.now().strftime("%m-%d %H:%M"),
                        "level": order["level"],
                        "buy": order["actual_buy_price"],
                        "sell": sell_price,
                        "profit": round(profit, 4)
                    })

                    if len(stats["closed_trades"]) > 50:
                        stats["closed_trades"] = stats["closed_trades"][-50:]

                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"✅ <b>SELL</b> ур.{order['level']}\n"
                            f"💲 Цена: <code>{sell_price}</code>\n"
                            f"📍 Вход: <code>{order['actual_buy_price']}</code>\n"
                            f"➕ Профит: <code>+{round(profit, 4)}$</code>\n"
                            f"💰 Баланс: <code>{round(stats['balance_usd'], 2)}$</code>"
                        ),
                        parse_mode='HTML'
                    )

                    order["status"] = "waiting"
                    order["buy_price"] = round(
                        sell_price * (1 - config.GRID_STEP * order["level"]),
                        2
                    )
                    order["sell_target"] = round(
                        order["buy_price"] * (1 + config.GRID_STEP + config.PROFIT_MARGIN),
                        2
                    )
                    order["buy_volume_btc"] = 0.0
                    order["actual_buy_price"] = 0.0
                    order["price_high"] = 0.0
                    order["trailing_stop"] = 0.0

                    save_stats(stats)
                    logger.info(
                        f"SELL ур.{order['level']} по {sell_price}, "
                        f"профит {round(profit, 4)}$"
                    )

            await asyncio.sleep(config.POLL_INTERVAL)

        except Exception as e:
            logger.error(f"Ошибка в monitor_market: {e}", exc_info=True)
            await asyncio.sleep(config.ERROR_COOLDOWN)


# ══════════════════════════════════════
#              ЗАПУСК
# ══════════════════════════════════════

async def main():
    Thread(target=run_flask, daemon=True).start()

    token = os.getenv("TELEGRAM_TOKEN", config.TELEGRAM_TOKEN)
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("trades", trades_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("pause", pause_command))
    application.add_handler(CommandHandler("resume", resume_command))
    application.add_handler(CommandHandler("help", help_command))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    monitor_task = asyncio.create_task(monitor_market(application.bot))

    logger.info("Bybit Sentinel запущен.")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки...")
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        save_stats(stats)
        logger.info("Sentinel остановлен. Состояние сохранено.")


if __name__ == "__main__":
    asyncio.run(main())
