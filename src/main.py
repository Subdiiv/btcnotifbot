import os
import asyncio
import time
from dotenv import load_dotenv
from telegram import Bot
from indicators import fetch_coinbase_data, calculate_indicators
from fear_greed import fetch_fear_greed_index

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set!")
else:
    print(f"✅ Bot initialized. Chat ID: {TELEGRAM_CHAT_ID}")

async def send_update():
    """
    Fetch data, calculate indicators, and send update to Telegram.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Skipping update: Missing environment variables.")
        return

    print("🔄 Starting 5-minute update...")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # 1. Fetch Coinbase Data
    print("📡 Fetching Coinbase data...")
    df = fetch_coinbase_data(symbol='BTC/USDC', timeframe='5m', limit=100)
    
    if df is not None:
        print(f"📊 Data fetched. Calculating indicators for {len(df)} candles...")
        latest = calculate_indicators(df)
        
        if latest is not None:
            # BTC Candle Movement (Close vs Open)
            price = latest['close']
            open_p = latest['open']
            change = ((price - open_p) / open_p) * 100
            movement_icon = "📈" if change >= 0 else "📉"
            
            # 2. Fetch Fear & Greed Index
            print("🧠 Fetching Sentiment data...")
            fng = fetch_fear_greed_index()
            fng_value = fng['value'] if fng else "N/A"
            fng_class = fng['value_classification'] if fng else "N/A"
            
            # Format Message
            message = (
                f"📊 *BTC 5-Minute Update*\n"
                f"Price: `${price:,.2f}` {movement_icon} ({change:+.2f}%)\n\n"
                f"💡 *Indicators (5m):*\n"
                f"• RSI: `{latest['RSI']:.2f}`\n"
                f"• EMA (20): `${latest['EMA']:.2f}`\n\n"
                f"🧠 *Sentiment:*\n"
                f"• Fear/Greed: `{fng_value}` ({fng_class})\n\n"
                f"⏰ Next update in 5 minutes."
            )
            
            try:
                print("📤 Sending Telegram message...")
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
                print(f"✅ Update sent successfully. Price: {price:,.2f}")
            except Exception as e:
                print(f"❌ Error sending Telegram message: {e}")
        else:
            print("❌ Error: Could not calculate indicators.")
    else:
        print("❌ Error: Could not fetch Coinbase data.")

async def main():
    print("🚀 Bot starting...")
    while True:
        try:
            await send_update()
        except Exception as e:
            print(f"🔥 Unexpected error in loop: {e}")
        
        print("💤 Sleeping for 5 minutes...")
        await asyncio.sleep(300)  # 5 minutes

if __name__ == "__main__":
    asyncio.run(main())
