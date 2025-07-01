from fastapi import FastAPI, Request
import requests
import yfinance as yf
import feedparser
import os

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
BBAI_TICKER = "BBAI"
NEWS_RSS = "https://news.google.com/rss/search?q=BigBear.ai+stock"

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if text == "/analisi":
        response = analisi_bbai()
    elif text == "/news":
        response = get_news()
    else:
        response = "📌 Comandi disponibili:\n/analisi – Analisi tecnica $BBAI\n/news – Ultime news su $BBAI"

    send_message(chat_id, response)
    return {"ok": True}

def send_message(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(TELEGRAM_URL, json=payload)

def analisi_bbai():
    ticker = yf.Ticker(BBAI_TICKER)
    hist = ticker.history(period="7d")
    if hist.empty:
        return "Errore: dati non disponibili."

    close = hist["Close"]
    volume = hist["Volume"]
    rsi = compute_rsi(close)
    last_price = close[-1]
    avg_volume = volume.mean()
    last_volume = volume[-1]

    signal = "📊 *Analisi tecnica $BBAI*\n"
    signal += f"Ultimo prezzo: **{last_price:.2f} USD**\n"
    signal += f"RSI(14): **{rsi:.2f}** → {'Overbought' if rsi > 70 else 'Oversold' if rsi < 30 else 'Neutro'}\n"
    signal += f"Volume: {last_volume:,} (Media: {avg_volume:,.0f})\n"
    return signal

def compute_rsi(series, period=14):
    delta = series.diff().dropna()
    up = delta.where(delta > 0, 0)
    down = -delta.where(delta < 0, 0)
    avg_gain = up.rolling(period).mean()
    avg_loss = down.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 0

def get_news():
    feed = feedparser.parse(NEWS_RSS)
    if not feed.entries:
        return "Nessuna news trovata."

    response = "📰 *Ultime news su $BBAI:*\n"
    for entry in feed.entries[:3]:
        response += f"- [{entry.title}]({entry.link})\n"
    return response
