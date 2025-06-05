
from flask import Flask, request, jsonify
import requests
import pandas as pd
import numpy as np
import ta

app = Flask(__name__)

API_KEY = "388733fb160e474abbd7990c4883acc0"
API_URL = "https://api.twelvedata.com/time_series"

def run_smc_analysis(symbol="GBP/USD"):
    params = {
        "symbol": symbol,
        "interval": "1min",
        "outputsize": 100,
        "apikey": API_KEY
    }

    response = requests.get(API_URL, params=params)
    data = response.json()
    if "values" not in data:
        return {"error": data.get("message", "Unknown error")}

    df = pd.DataFrame(data['values'])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.astype({'open': 'float', 'high': 'float', 'low': 'float', 'close': 'float'})
    df = df.sort_values('datetime').reset_index(drop=True)

    # RSI and MACD
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    # FVG Detection
    def detect_fvg(df):
        fvg_zones = []
        for i in range(2, len(df)):
            c1, c2, c3 = df.iloc[i-2], df.iloc[i-1], df.iloc[i]
            if c1['high'] < c2['low'] and c2['low'] > c3['high']:
                fvg_zones.append({"type": "bullish", "zone": [c1['high'], c2['low']], "time": str(df.iloc[i]['datetime'])})
            if c1['low'] > c2['high'] and c2['high'] < c3['low']:
                fvg_zones.append({"type": "bearish", "zone": [c1['low'], c2['high']], "time": str(df.iloc[i]['datetime'])})
        return fvg_zones

    fvg_list = detect_fvg(df)

    # BOS Detection
    def detect_bos(df):
        bos_list = []
        for i in range(2, len(df)):
            if df['high'][i] > df['high'][i-2] and df['close'][i] > df['high'][i-2]:
                bos_list.append({"time": str(df['datetime'][i]), "direction": "bullish"})
            if df['low'][i] < df['low'][i-2] and df['close'][i] < df['low'][i-2]:
                bos_list.append({"time": str(df['datetime'][i]), "direction": "bearish"})
        return bos_list

    bos_list = detect_bos(df)

    liquidity = {
        "highs": df['high'].rolling(10).max().dropna().unique()[-3:].tolist(),
        "lows": df['low'].rolling(10).min().dropna().unique()[-3:].tolist()
    }

    return {
        "symbol": symbol,
        "latest_data": df.tail(5)[['datetime', 'close', 'rsi', 'macd', 'macd_signal']].to_dict(orient="records"),
        "fvg_zones": fvg_list,
        "bos_signals": bos_list,
        "liquidity_levels": liquidity
    }

@app.route("/run", methods=["GET"])
def run():
    symbol = request.args.get("pair", "GBP/USD")
    result = run_smc_analysis(symbol)
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
