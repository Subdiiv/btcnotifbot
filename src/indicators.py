import ccxt
import pandas as pd
import pandas_ta as ta

def fetch_coinbase_data(symbol='BTC/USDC', timeframe='5m', limit=100):
    """
    Fetch OHLCV data from Coinbase.
    Note: Coinbase uses USDC or USDT pairs.
    """
    exchange = ccxt.coinbase()  # Or coinbasepro if preferred, but ccxt maps coinbase well.
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching data from Coinbase: {e}")
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
