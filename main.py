from fastapi import FastAPI, Request
import requests
import yfinance as yf
import pandas as pd
import os
import feedparser

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
BBAI_TICKER = "28K1.BE"  # Titolo BigBear.ai in euro (Trade Republic - Borsa tedesca XETRA)
TRADINGVIEW_SECRET = os.getenv("TV_SECRET")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if text == "/analisi":
        response = analisi_bbai()
        send_message(chat_id, response)
        send_message(chat_id, "Vuoi usare la strategia Swing o Long? Rispondi con 'Swing' o 'Long'.")

    elif text.lower() == "swing":
        response = strategia("swing")
        send_message(chat_id, response)

    elif text.lower() == "long":
        send_message(chat_id, "Inserisci il prezzo di ingresso per la strategia Long (es. 5.85):")

    elif is_number(text):
        entry = float(text)
        response = strategia("long", entry)
        send_message(chat_id, response)

    elif text == "/news":
        news = news_bbai()
        send_message(chat_id, news)

    else:
        send_message(chat_id, "Usa il comando /analisi per iniziare.")

    return {"ok": True}

@app.post("/tvwebhook")
async def tradingview_webhook(request: Request):
    headers = request.headers
    if headers.get("Authorization") != f"Bearer {TRADINGVIEW_SECRET}":
        return {"error": "Unauthorized"}

    data = await request.json()
    ticker = data.get("ticker", "N/A")
    signal = data.get("signal", "N/A")
    price = data.get("price", "N/A")

    message = f"⚠️ Segnale da TradingView per {ticker}\nSegnale: *{signal}*\nPrezzo: {price} EUR"
    send_message(chat_id=ADMIN_CHAT_ID, text=message)
    return {"ok": True}

def send_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    requests.post(TELEGRAM_URL, json=payload)

def get_price_in_eur(eur_price):
    return eur_price  # già in euro

def analisi_bbai():
    intervals = [
        ("1d", "1 Giorno"),
        ("4h", "4 Ore"),
        ("1h", "1 Ora"),
        ("30m", "30 Minuti"),
        ("15m", "15 Minuti")
    ]
    results = ["📊 *Analisi tecnica multi-timeframe su BBAI (valori in EUR)*\n"]
    ticker = yf.Ticker(BBAI_TICKER)

    for interval, label in intervals:
        hist = ticker.history(period="7d", interval=interval, auto_adjust=True)

        if hist.empty:
            results.append(f"⚠️ Nessun dato disponibile per il timeframe {label}")
            continue

        close = hist["Close"]
        price = close.iloc[-1]
        ema20 = close.ewm(span=20).mean().iloc[-1]
        ema50 = close.ewm(span=50).mean().iloc[-1]
        rsi = compute_rsi(close).iloc[-1]
        macd, signal, _ = compute_macd(close)
        atr = compute_atr(hist).iloc[-1]
        momentum = close.diff().iloc[-1]
        trend = "📈 Rialzista" if ema20 > ema50 else "📉 Ribassista"
        alert = "✅ Breakout confermato" if macd.iloc[-1] > signal.iloc[-1] and rsi > 55 else "⚠️ Nessun breakout confermato"

        results.append(
            f"🕐 {label}:\n"
            f"Prezzo: {price:.2f} EUR\n"
            f"EMA20: {ema20:.2f} | EMA50: {ema50:.2f}\n"
            f"RSI: {rsi:.2f} | MACD: {macd.iloc[-1]:.3f} (segnale: {signal.iloc[-1]:.3f})\n"
            f"Momentum: {momentum:.3f} | ATR: {atr:.3f}\n"
            f"Trend: {trend} | {alert}\n"
        )

    return "\n".join(results)

def news_bbai():
    feed_url = "https://news.google.com/rss/search?q=BigBear.ai"
    feed = feedparser.parse(feed_url)
    formatted_news = "📰 *Ultime News su BBAI:*\n\n"

    for i, entry in enumerate(feed.entries[:5], 1):
        title = entry.get("title") or "Titolo non disponibile"
        link = entry.get("link") or "#"
        formatted_news += f"{i}. [{title}]({link})\n\n"

    return formatted_news

def strategia(tipo, entry=None):
    ticker = yf.Ticker(BBAI_TICKER)
    hist = ticker.history(period="1mo", interval="1d")
    atr = compute_atr(hist).iloc[-1]

    if tipo == "swing":
        entry = hist["Close"].iloc[-1]
        tp = entry + 1.5 * atr
        sl = entry - atr
        strategia_msg = "🚀 Strategia Swing (Entry attuale)"

    elif tipo == "long" and entry:
        tp = entry + 2 * atr
        sl = entry - 1.5 * atr
        strategia_msg = f"🚀 Strategia Long (Entry: {entry:.2f} EUR)"

    else:
        return "Errore: inserisci un prezzo valido per strategia Long."

    msg = (f"{strategia_msg}\n"
           f"🎯 Take Profit: {tp:.2f} EUR\n"
           f"🛑 Stop Loss: {sl:.2f} EUR")
    return msg

def compute_rsi(series, period=14):
    delta = series.diff().dropna()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_macd(series):
    short = series.ewm(span=12).mean()
    long = series.ewm(span=26).mean()
    macd = short - long
    signal = macd.ewm(span=9).mean()
    hist = macd - signal
    return macd, signal, hist

def compute_atr(data, period=14):
    high_low = data['High'] - data['Low']
    high_close = (data['High'] - data['Close'].shift()).abs()
    low_close = (data['Low'] - data['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
