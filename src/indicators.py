import requests
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta

COINBASE_API = "https://api.exchange.coinbase.com/products/BTC-USD/candles"

def fetch_coinbase_data(symbol='BTC/USD', timeframe='5m', limit=100):
    """
    Fetch OHLCV data from Coinbase Exchange REST API directly.
    granularity: 300 = 5 minutes
    """
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=9)  # 9 hours = enough for 100 5-min candles

        params = {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'granularity': 300  # 5-minute candles
        }

        response = requests.get(COINBASE_API, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if not data or isinstance(data, dict):
            print(f"Unexpected Coinbase response: {data}")
            return None

        # Coinbase returns: [time, low, high, open, close, volume]
        df = pd.DataFrame(data, columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values('timestamp').reset_index(drop=True)
        print(f"✅ Fetched {len(df)} candles from Coinbase REST API.")
        return df

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP error from Coinbase: {e} - Response: {e.response.text if e.response else 'N/A'}")
        return None
    except Exception as e:
        print(f"❌ Error fetching data from Coinbase: {e}")
        return None

def calculate_indicators(df):
    """
    Calculate RSI, EMA, and MACD.
    """
    if df is None or df.empty:
        return None

    try:
        # RSI (14)
        df['RSI'] = ta.rsi(df['close'], length=14)

        # EMA (20)
        df['EMA'] = ta.ema(df['close'], length=20)

        # MACD (12, 26, 9)
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df = pd.concat([df, macd], axis=1)

        last = df.iloc[-1]
        if pd.isna(last['RSI']) or pd.isna(last['EMA']):
            print("❌ Indicators returned NaN - not enough data.")
            return None

        return last
    except Exception as e:
        print(f"❌ Error calculating indicators: {e}")
        return None
