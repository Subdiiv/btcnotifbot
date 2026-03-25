import os
import asyncio
import schedule
import time
from dotenv import load_dotenv
from telegram import Bot
from indicators import fetch_coinbase_data, calculate_indicators
from fear_greed import fetch_fear_greed_index

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def send_update():
    """
    Fetch data, calculate indicators, and send update to Telegram.
    """
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # 1. Fetch Coinbase Data & Calculate Indicators
    df = fetch_coinbase_data(symbol='BTC/USDT', timeframe='5m', limit=100)
    if df is not None:
        latest = calculate_indicators(df)
        if latest is not None:
            # BTC Candle Movement (Close vs Open)
            price = latest['close']
            open_p = latest['open']
            change = ((price - open_p) / open_p) * 100
            movement_icon = "📈" if change >= 0 else "📉"
            
            # Indicators
            rsi = latest['RSI']
            ema = latest['EMA']
            macd = latest.get('MACD_12_26_9', 0)
            macd_signal = latest.get('MACDs_12_26_9', 0)
            macd_hist = latest.get('MACDh_12_26_9', 0)
            
            # 2. Fetch Fear & Greed Index
            fng = fetch_fear_greed_index()
            fng_value = fng['value'] if fng else "N/A"
            fng_class = fng['value_classification'] if fng else "N/A"
            
            # Format Message
            message = (
                f"📊 *BTC 5-Minute Update*\n"
                f"Price: `${price:,.2f}` {movement_icon} ({change:+.2f}%)\n\n"
                f"💡 *Indicators (5m):*\n"
                f"• RSI: `{rsi:.2f}`\n"
                f"• EMA (20): `${ema:,.2f}`\n"
                f"• MACD: `{macd:.2f}` (Signal: `{macd_signal:.2f}`, Hist: `{macd_hist:.2f}`)\n\n"
                f"🧠 *Sentiment:*\n"
                f"• Fear/Greed: `{fng_value}` ({fng_class})\n\n"
                f"⏰ Next update in 5 minutes."
            )
            
            try:
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
                print(f"Update sent: {price:,.2f}")
            except Exception as e:
                print(f"Error sending Telegram message: {e}")
        else:
            print("Could not calculate indicators.")
    else:
        print("Could not fetch Coinbase data.")

def run_scheduler():
    """
    Run the asynchronous task in the schedule.
    """
    asyncio.run(send_update())

async def main():
    # Initial ping
    await send_update()
    
    # Schedule every 5 minutes
    schedule.every(5).minutes.do(run_scheduler)
    
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
