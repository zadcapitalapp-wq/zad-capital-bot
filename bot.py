
import asyncio
import os
from groq import Groq
from supabase import create_client
import httpx
from datetime import datetime

# إعدادات من Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

STOP_LOSS_PCT = 0.05
TAKE_PROFIT_PCT = 0.10

async def get_price(symbol):
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            data = r.json()
            return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except:
        return None

def analyze_news(symbol, news_text):
    response = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": "أنت محلل مالي إسلامي. حدد: BUY أو WAIT مع CONFIDENCE (0-100) و REASON."},
            {"role": "user", "content": f"السهم: {symbol}\nالخبر: {news_text}"}
        ],
        temperature=0.3,
        max_tokens=150
    )
    return response.choices[0].message.content

async def monitor_trades():
    result = supabase.table("trades").select("*").eq("status", "open").execute()
    for trade in result.data:
        symbol = trade["symbol"]
        entry_price = float(trade["entry_price"])
        current_price = await get_price(symbol)
        if not current_price:
            continue
        change_pct = (current_price - entry_price) / entry_price
        pnl = (current_price - entry_price) * trade["quantity"]
        
        if change_pct <= -STOP_LOSS_PCT:
            supabase.table("trades").update({
                "status": "closed", "exit_price": current_price,
                "pnl": round(pnl, 2), "closed_at": datetime.utcnow().isoformat(),
                "reason": f"Stop Loss {change_pct*100:.1f}%"
            }).eq("id", trade["id"]).execute()
            print(f"🛑 {symbol} SOLD - Loss ${pnl:.2f}")
        elif change_pct >= TAKE_PROFIT_PCT:
            supabase.table("trades").update({
                "status": "closed", "exit_price": current_price,
                "pnl": round(pnl, 2), "closed_at": datetime.utcnow().isoformat(),
                "reason": f"Take Profit {change_pct*100:.1f}%"
            }).eq("id", trade["id"]).execute()
            print(f"🎯 {symbol} SOLD - Profit ${pnl:.2f}")

async def run_bot():
    print("🤖 Zad Capital Bot Started!")
    while True:
        await monitor_trades()
        print(f"✅ Check completed - {datetime.now()}")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(run_bot())
