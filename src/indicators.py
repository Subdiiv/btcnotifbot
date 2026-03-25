import ccxt
import pandas as pd
import pandas_ta as ta

def fetch_coinbase_data(symbol='BTC/USD', timeframe='5m', limit=100):
    """
    Fetch OHLCV data from Coinbase Exchange.
    """
    # use coinbasepro for better compatibility across ccxt versions
    exchange = ccxt.coinbasepro({
        'timeout': 20000,
        'enableRateLimit': True,
    })
    
    for attempt in range(3):
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not ohlcv:
                continue
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Attempt {attempt+1} failed to fetch from Coinbase: {e}")
            if attempt < 2:
                import time
                time.sleep(2)
            else:
                return None
    return None

def calculate_indicators(df):
    """
    Calculate RSI, EMA, and MACD.
    """
    if df is None or df.empty:
        return None
    
    # RSI (14)
    df['RSI'] = ta.rsi(df['close'], length=14)
    
    # EMA (20)
    df['EMA'] = ta.ema(df['close'], length=20)
    
    # MACD (12, 26, 9)
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)
    
    return df.iloc[-1]  # Return the last row with signals
