import os
import json
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from indicators import fetch_coinbase_data, calculate_indicators
from fear_greed import fetch_fear_greed_index

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Path to subscribers file
SUBSCRIBERS_FILE = "subscribers.json"

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, 'r') as f:
                return set(json.load(f))
        except Exception as e:
            print(f"❌ Error loading subscribers: {e}")
    return set()

def save_subscribers(subs):
    try:
        with open(SUBSCRIBERS_FILE, 'w') as f:
            json.dump(list(subs), f)
    except Exception as e:
        print(f"❌ Error saving subscribers: {e}")

# Global state
subscribers = load_subscribers()
if TELEGRAM_CHAT_ID and int(TELEGRAM_CHAT_ID) not in subscribers:
    subscribers.add(int(TELEGRAM_CHAT_ID))
    save_subscribers(subscribers)

async def get_analysis_message():
    """
    Fetch data, calculate indicators, and format the update message.
    """
    print("📡 Fetching BTC data and calculating indicators...")
    df = fetch_coinbase_data(symbol='BTC/USDC', timeframe='5m', limit=100)
    
    if df is not None:
        latest = calculate_indicators(df)
        if latest is not None:
            price = latest['close']
            open_p = latest['open']
            change = ((price - open_p) / open_p) * 100
            movement_icon = "📈" if change >= 0 else "📉"
            
            fng = fetch_fear_greed_index()
            fng_value = fng['value'] if fng else "N/A"
            fng_class = fng['value_classification'] if fng else "N/A"
            
            message = (
                f"📊 **BTC 5-Minute Update**\n"
                f"⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                f"Price: `${price:,.2f}` {movement_icon} ({change:+.2f}%)\n\n"
                f"💡 **Indicators (5m):**\n"
                f"• RSI: `{latest['RSI']:.2f}`\n"
                f"• EMA (20): `${latest['EMA']:.2f}`\n\n"
                f"🧠 **Sentiment:**\n"
                f"• Fear/Greed: `{fng_value}` ({fng_class})\n\n"
                f"⏰ Next update in 5 minutes."
            )
            return message
    return "❌ Error: Could not fetch market data."

async def broadcast_update(context: ContextTypes.DEFAULT_TYPE):
    """
    Periodic task to send updates to all subscribers.
    """
    if not subscribers:
        return

    message = await get_analysis_message()
    for chat_id in list(subscribers):
        try:
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
            print(f"✅ Update sent to {chat_id}")
        except Exception as e:
            print(f"❌ Failed to send to {chat_id}: {e}")
            if "blocked" in str(e).lower() or "not found" in str(e).lower():
                subscribers.discard(chat_id)
                save_subscribers(subscribers)

# --- Commands ---

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in subscribers:
        subscribers.add(chat_id)
        save_subscribers(subscribers)
        banner = "🚀 **Welcome to BTC Monitor Bot!**\n\nYou are now subscribed to 5-minute updates."
    else:
        banner = "✅ You are already subscribed to updates."
    
    await update.message.reply_text(banner, parse_mode='Markdown')
    # Send immediate update
    msg = await get_analysis_message()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        subscribers.remove(chat_id)
        save_subscribers(subscribers)
        await update.message.reply_text("❌ You have been unsubscribed from updates.")
    else:
        await update.message.reply_text("You are not currently subscribed.")

async def now_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await get_analysis_message()
    await update.message.reply_text(msg, parse_mode='Markdown')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **BTC Monitor Bot Help**\n\n"
        "This bot sends BTC analysis every 5 minutes.\n\n"
        "**Commands:**\n"
        "/start - Subscribe to updates\n"
        "/stop - Unsubscribe\n"
        "/now - Get instant analysis\n"
        "/status - Show subscription status\n"
        "/help - Show this message"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    is_subbed = chat_id in subscribers
    text = f"⚙️ **Status:** {'✅ Subscribed' if is_subbed else '❌ Not Subscribed'}\nTotal subs: {len(subscribers)}"
    await update.message.reply_text(text, parse_mode='Markdown')

# --- Main ---

async def periodic_job(app: Application):
    """
    Background loop for periodic updates.
    """
    print("🚀 Background scheduler started.")
    while True:
        try:
            # We use the bot application context to broadcast
            await broadcast_update(app)
        except Exception as e:
            print(f"🔥 Error in periodic task: {e}")
        await asyncio.sleep(300)

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ FATAL: TELEGRAM_BOT_TOKEN not set!")
        return

    print("🤖 Bot is starting...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add commands
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("stop", stop_cmd))
    application.add_handler(CommandHandler("now", now_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("status", status_cmd))

    # Add the periodic task to the application's startup
    async def post_init(app: Application):
        asyncio.create_task(periodic_job(app))
    
    application.post_init = post_init

    # Polling starts here and blocks
    application.run_polling()

if __name__ == "__main__":
    main()
