import os
import json
import asyncio
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from indicators import fetch_coinbase_data, calculate_indicators
from fear_greed import fetch_fear_greed_index

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

SUBSCRIBERS_FILE = "subscribers.json"
USER_SETTINGS_FILE = "user_settings.json"

# ── Persistence helpers ────────────────────────────────────────────────────────

def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(path: str, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving {path}: {e}")

# Global state
subscribers: set = set(load_json(SUBSCRIBERS_FILE, []))
user_settings: dict = load_json(USER_SETTINGS_FILE, {})  # {str(chat_id): {"currency":"usd","portfolio":0.0}}

if TELEGRAM_CHAT_ID and int(TELEGRAM_CHAT_ID) not in subscribers:
    subscribers.add(int(TELEGRAM_CHAT_ID))
    save_json(SUBSCRIBERS_FILE, list(subscribers))

def get_user(chat_id: int) -> dict:
    return user_settings.setdefault(str(chat_id), {"currency": "usd", "portfolio": 0.0})

def save_settings():
    save_json(USER_SETTINGS_FILE, user_settings)

# ── Currency helpers ───────────────────────────────────────────────────────────

EUR_RATE_CACHE = {"rate": None, "ts": 0}

def get_eur_rate() -> float:
    import time
    now = time.time()
    if EUR_RATE_CACHE["rate"] and now - EUR_RATE_CACHE["ts"] < 600:
        return EUR_RATE_CACHE["rate"]
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=EUR", timeout=8)
        rate = r.json()["rates"]["EUR"]
        EUR_RATE_CACHE["rate"] = rate
        EUR_RATE_CACHE["ts"] = now
        return rate
    except Exception:
        return EUR_RATE_CACHE["rate"] or 0.92  # fallback

def fmt_price(price: float, currency: str) -> str:
    if currency == "eur":
        return f"€{price * get_eur_rate():,.2f}"
    return f"${price:,.2f}"

# ── Analysis message ───────────────────────────────────────────────────────────

async def get_analysis_message(chat_id: int = None) -> str:
    currency = get_user(chat_id)["currency"] if chat_id else "usd"
    portfolio = get_user(chat_id)["portfolio"] if chat_id else 0.0

    print("📡 Fetching BTC data...")
    df = fetch_coinbase_data()

    if df is None:
        return "❌ Error: Could not fetch market data."

    latest = calculate_indicators(df)
    if latest is None:
        return "❌ Error: Could not calculate indicators."

    price = latest['close']
    open_p = latest['open']
    change = ((price - open_p) / open_p) * 100
    arrow = "📈" if change >= 0 else "📉"

    fng = fetch_fear_greed_index()
    fng_value = fng['value'] if fng else "N/A"
    fng_class = fng['value_classification'] if fng else "N/A"

    price_str = fmt_price(price, currency)
    ema_str = fmt_price(latest['EMA'], currency)
    cur_sym = "EUR" if currency == "eur" else "USD"

    lines = [
        f"📊 *BTC 5-Minute Update* ({cur_sym})",
        f"⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
        "",
        f"💰 Price: `{price_str}` {arrow} ({change:+.2f}%)",
        "",
        f"💡 *Indicators (5m):*",
        f"• RSI (14): `{latest['RSI']:.2f}`",
        f"• EMA (20): `{ema_str}`",
        "",
        f"🧠 *Sentiment:*",
        f"• Fear/Greed: `{fng_value}/100` — {fng_class}",
    ]

    if portfolio and portfolio > 0:
        port_val = fmt_price(price * portfolio, currency)
        lines += ["", f"💼 *Portfolio:* `{portfolio:.4f} BTC` = `{port_val}`"]

    lines += ["", "⏰ _Next update in 5 minutes._"]
    return "\n".join(lines)

# ── Broadcast ──────────────────────────────────────────────────────────────────

async def broadcast_update(app: Application):
    if not subscribers:
        return
    for chat_id in list(subscribers):
        try:
            msg = await get_analysis_message(chat_id)
            await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
            print(f"✅ Sent to {chat_id}")
        except Exception as e:
            print(f"❌ Failed to send to {chat_id}: {e}")
            if "blocked" in str(e).lower() or "not found" in str(e).lower():
                subscribers.discard(chat_id)
                save_json(SUBSCRIBERS_FILE, list(subscribers))

# ── Commands ───────────────────────────────────────────────────────────────────

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    first_name = update.effective_user.first_name or "there"
    greeting = (
        f"👋 Hey *{first_name}*, welcome to *BTC Monitor Bot!*\n\n"
        "I monitor Bitcoin every *5 minutes* using live Coinbase data and send you a full technical report.\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "📊 *What I track:*\n"
        "• 💰 BTC price & candle direction\n"
        "• 📈 RSI (14) — overbought/oversold signal\n"
        "• 📉 EMA (20) — trend direction\n"
        "• 🧠 Fear & Greed — market sentiment\n"
        "• 💼 Your BTC portfolio value (optional)\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "⚙️ *Commands:*\n"
        "• `/subscribe` — Start receiving 5-min alerts\n"
        "• `/stop` — Pause alerts\n"
        "• `/now` — Instant update\n"
        "• `/currency eur` — Switch to Euros 🇪🇺\n"
        "• `/portfoliovalue 0.5` — Track BTC holdings\n"
        "• `/explain` — What the indicators mean\n"
        "• `/status` — Your current settings\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "👇 Use /subscribe to start receiving alerts!"
    )
    await update.message.reply_text(greeting, parse_mode='Markdown')

async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        await update.message.reply_text("✅ You are already subscribed! Use /now for an instant update.")
        return
    subscribers.add(chat_id)
    save_json(SUBSCRIBERS_FILE, list(subscribers))
    await update.message.reply_text(
        "🔔 *Subscribed!* You'll now receive BTC updates every 5 minutes.\n\nHere's your first report:",
        parse_mode='Markdown'
    )
    msg = await get_analysis_message(chat_id)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_json(SUBSCRIBERS_FILE, list(subscribers))
        await update.message.reply_text("❌ Unsubscribed. Use /subscribe to start again.")
    else:
        await update.message.reply_text("You are not subscribed. Use /subscribe to start receiving alerts.")

async def now_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await get_analysis_message(update.effective_chat.id)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def currency_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        cur = get_user(chat_id)["currency"].upper()
        await update.message.reply_text(
            f"💱 Your currency is currently: *{cur}*\n\nChange it with:\n`/currency usd` or `/currency eur`",
            parse_mode='Markdown'
        )
        return
    chosen = context.args[0].lower()
    if chosen not in ("usd", "eur"):
        await update.message.reply_text("❌ Unknown currency. Use `/currency usd` or `/currency eur`.", parse_mode='Markdown')
        return
    get_user(chat_id)["currency"] = chosen
    save_settings()
    symbol = "USD 🇺🇸" if chosen == "usd" else "EUR 🇪🇺"
    await update.message.reply_text(f"✅ Currency set to *{symbol}*", parse_mode='Markdown')

async def portfoliovalue_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        portfolio = get_user(chat_id)["portfolio"]
        if portfolio > 0:
            df = fetch_coinbase_data()
            if df is not None:
                lat = calculate_indicators(df)
                if lat is not None:
                    currency = get_user(chat_id)["currency"]
                    val = fmt_price(lat['close'] * portfolio, currency)
                    await update.message.reply_text(
                        f"💼 *Your Portfolio*\n`{portfolio:.4f} BTC` = `{val}`\n\nUpdate with: `/portfoliovalue 0.5`",
                        parse_mode='Markdown'
                    )
                    return
        await update.message.reply_text(
            "💼 You haven\\`t set a portfolio yet\\.\n\nUse: `/portfoliovalue 0\\.5` to track 0\\.5 BTC",
            parse_mode='MarkdownV2'
        )
        return
    try:
        amount = float(context.args[0])
        if amount < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid positive number. E.g. `/portfoliovalue 0.5`", parse_mode='Markdown')
        return
    get_user(chat_id)["portfolio"] = amount
    save_settings()
    df = fetch_coinbase_data()
    if df is not None:
        lat = calculate_indicators(df)
        if lat is not None:
            currency = get_user(chat_id)["currency"]
            val = fmt_price(lat['close'] * amount, currency)
            await update.message.reply_text(
                f"✅ Portfolio set to `{amount:.4f} BTC`\n💼 Current value: `{val}`",
                parse_mode='Markdown'
            )
            return
    await update.message.reply_text(f"✅ Portfolio set to `{amount:.4f} BTC`. Value shown in next update.", parse_mode='Markdown')

async def explain_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 *Indicator Guide*\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 *RSI — Relative Strength Index*\n"
        "Measures how overbought or oversold BTC is on a scale of 0–100.\n"
        "• `> 70` → Overbought ⚠️ (price may drop)\n"
        "• `< 30` → Oversold 💎 (price may bounce)\n"
        "• `40–60` → Neutral ⚖️\n\n"
        "📈 *EMA — Exponential Moving Average*\n"
        "A smoothed average of recent prices, weighted towards the latest candles.\n"
        "• Price `> EMA` → Uptrend 📈\n"
        "• Price `< EMA` → Downtrend 📉\n"
        "• Acts as dynamic support/resistance.\n\n"
        "📉 *MACD — Moving Average Convergence Divergence*\n"
        "Tracks momentum using two moving averages (12 & 26 period).\n"
        "• MACD `> Signal` → Bullish momentum 🟢\n"
        "• MACD `< Signal` → Bearish momentum 🔴\n"
        "• Histogram shows how strong the trend is.\n\n"
        "😱 *Fear & Greed Index*\n"
        "Market sentiment score from 0–100 based on volatility, volume, social media & more.\n"
        "• `0–25` → Extreme Fear 😱 (possible buy opportunity)\n"
        "• `25–45` → Fear 😨\n"
        "• `45–55` → Neutral 😐\n"
        "• `55–75` → Greed 🤑\n"
        "• `75–100` → Extreme Greed 🚀 (possible sell signal)\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "_These are educational signals, not financial advice._"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    s = get_user(chat_id)
    is_subbed = chat_id in subscribers
    portfolio = s["portfolio"]
    currency = s["currency"].upper()
    text = (
        f"⚙️ *Your Settings*\n\n"
        f"• Subscription: {'✅ Active' if is_subbed else '❌ Inactive'}\n"
        f"• Currency: `{currency}`\n"
        f"• Portfolio: `{portfolio:.4f} BTC`\n"
        f"• Total subscribers: `{len(subscribers)}`\n\n"
        f"Update with:\n"
        f"`/currency eur` · `/portfoliovalue 0.5`"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *BTC Monitor Bot — Commands*\n\n"
        "/start — Subscribe to 5-min alerts\n"
        "/stop — Unsubscribe\n"
        "/now — Get instant analysis\n"
        "/currency usd|eur — Set display currency\n"
        "/portfoliovalue 0.5 — Track your BTC holdings\n"
        "/explain — Learn what RSI, EMA, MACD mean\n"
        "/status — View your settings\n"
        "/help — Show this menu"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# ── Background scheduler ───────────────────────────────────────────────────────

async def periodic_job(app: Application):
    print("⏰ Scheduler started — first update in 5 minutes.")
    await asyncio.sleep(300)
    while True:
        try:
            await broadcast_update(app)
        except Exception as e:
            print(f"🔥 Error in scheduler: {e}")
        await asyncio.sleep(300)

# ── Main ───────────────────────────────────────────────────────────────────────

BOT_COMMANDS = [
    BotCommand("start", "About this bot & all commands"),
    BotCommand("subscribe", "Start receiving 5-minute BTC alerts"),
    BotCommand("stop", "Pause alerts"),
    BotCommand("now", "Get an instant market update"),
    BotCommand("currency", "Set currency: /currency usd or /currency eur"),
    BotCommand("portfoliovalue", "Track holdings: /portfoliovalue 0.5"),
    BotCommand("explain", "What do RSI, EMA, MACD & Fear/Greed mean?"),
    BotCommand("status", "View your settings"),
    BotCommand("help", "Show all commands"),
]

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ FATAL: TELEGRAM_BOT_TOKEN not set!")
        return

    print("🤖 BTC Monitor Bot is starting...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("subscribe", subscribe_cmd))
    application.add_handler(CommandHandler("stop", stop_cmd))
    application.add_handler(CommandHandler("now", now_cmd))
    application.add_handler(CommandHandler("currency", currency_cmd))
    application.add_handler(CommandHandler("portfoliovalue", portfoliovalue_cmd))
    application.add_handler(CommandHandler("explain", explain_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("help", help_cmd))

    async def post_init(app: Application):
        await app.bot.set_my_commands(BOT_COMMANDS)
        print("✅ Bot command menu set.")
        asyncio.create_task(periodic_job(app))

    application.post_init = post_init
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
