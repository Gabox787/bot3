@restricted
async def btc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        session = HTTP(testnet=config.IS_TESTNET)
        res = session.get_tickers(category="spot", symbol=config.SYMBOL)
        price = float(res['result']['list'][0]['lastPrice'])
        high_24h = float(res['result']['list'][0]['highPrice24h'])
        low_24h = float(res['result']['list'][0]['lowPrice24h'])
        volume_24h = float(res['result']['list'][0]['turnover24h'])
        change_24h = ((price - low_24h) / low_24h) * 100

        # ── Статистика за 24ч из closed_trades ──
        now = datetime.now()
        closed = stats.get("closed_trades", [])

        # Все сделки за сутки
        trades_24h = []
        for tr in closed:
            try:
                tr_time = datetime.strptime(f"{now.year}-{tr['date']}", "%Y-%m-%d %H:%M")
                if (now - tr_time).total_seconds() <= 86400:
                    trades_24h.append(tr)
            except ValueError:
                continue

        total_24h = len(trades_24h)
        wins_24h = sum(1 for t in trades_24h if t["profit"] > 0)
        losses_24h = sum(1 for t in trades_24h if t["profit"] <= 0)
        profit_24h = sum(t["profit"] for t in trades_24h)
        winrate_24h = (wins_24h / total_24h * 100) if total_24h > 0 else 0

        # ── Общая статистика ──
        total_all = stats["trades_count"]
        wins_all = stats["wins_count"]
        losses_all = total_all - wins_all
        winrate_all = (wins_all / total_all * 100) if total_all > 0 else 0

        # ── Плавающий PnL ──
        trade_amount = calculate_trade_amount(config.INITIAL_DEPOSIT)
        floating_pnl = 0.0
        active_count = 0
        for order in grid:
            if order["status"] == "bought":
                current_value = order["buy_volume_btc"] * price
                floating_pnl += current_value - trade_amount
                active_count += 1

        msg = (
            f"₿ <b>Bitcoin</b>\n\n"
            f"💲 Цена: <code>{round(price, 2)}</code> USDT\n"
            f"📈 24h High: <code>{round(high_24h, 2)}</code>\n"
            f"📉 24h Low: <code>{round(low_24h, 2)}</code>\n"
            f"📊 24h Volume: <code>{round(volume_24h / 1_000_000, 1)}M$</code>\n"
            f"📍 База сетки: <code>{round(base_price, 2) if base_price else 'N/A'}</code>\n\n"

            f"━━━ 📊 <b>За 24 часа</b> ━━━\n"
            f"🔄 Сделок: <code>{total_24h}</code>\n"
            f"✅ Выигрышных: <code>{wins_24h}</code>\n"
            f"❌ Убыточных: <code>{losses_24h}</code>\n"
            f"🏆 Винрейт: <code>{round(winrate_24h, 1)}%</code>\n"
            f"💵 Профит 24h: <code>{round(profit_24h, 4)}$</code>\n\n"

            f"━━━ 📈 <b>Всё время</b> ━━━\n"
            f"🔄 Сделок: <code>{total_all}</code>\n"
            f"✅ Выигрышных: <code>{wins_all}</code>\n"
            f"❌ Убыточных: <code>{losses_all}</code>\n"
            f"🏆 Винрейт: <code>{round(winrate_all, 1)}%</code>\n"
            f"💵 Зафиксировано: <code>{round(stats['total_profit_net'], 4)}$</code>\n\n"

            f"━━━ 💼 <b>Сейчас</b> ━━━\n"
            f"🔓 Открыто позиций: <code>{active_count}</code>\n"
            f"📊 Плавающий PnL: <code>{round(floating_pnl, 4)}$</code>\n"
            f"💰 Баланс: <code>{round(stats['balance_usd'], 2)}$</code>"
        )

        await update.message.reply_text(msg, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Ошибка в /btc: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")
