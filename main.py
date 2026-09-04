import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === НАСТРОЙКИ ===
BOT_TOKEN = "8976928394:AAHcq8RzfMte_PFREl2nHGA2Wij2JeeBRSc"
MY_CHAT_ID = 800295680

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

seen_ads = set()

EXCHANGE_KEYWORDS = [
    "výmena", "vymením", "vymena", "vymenim", 
    "na výmenu", "na vymenu", "možná výmena", "mozna vymena",
    "vymeniť", "vymenit", "vymene", "výmene", "doplatok", "doplatom"
]

STRAT_TELE_KEYWORDS = [
    "telecaster", "stratocaster", "tele", "strat"
]

BASS_KEYWORDS = [
    "basgitar", "basa", "bass"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "sk-SK,sk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://hudba.bazos.sk/"
}

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "🎸 **Радар гитар Bazoš запущен!**\n\n"
        "Отслеживаю:\n"
        "1. Любой обмен (от 600€ или Vymením/Dohodou)\n"
        "2. Telecaster / Stratocaster от 600€\n"
        "3. Любые бас-гитары до 150€\n\n"
        "Напиши /test для проверки.",
        parse_mode="Markdown"
    )

@dp.message(Command("test"))
async def test_handler(message: types.Message):
    await message.answer("🔍 Проверяю подключение к Bazoš.sk...")
    count, error_msg = await check_bazos_guitars(force_send=True)
    
    if error_msg:
        await message.answer(f"⚠️ Ошибка подключения к Bazoš: {error_msg}")
    elif count == 0:
        await message.answer("ℹ️ Доступ к Bazoš есть, но объявлений по фильтрам не найдено.")

async def fetch_full_description(session, url):
    try:
        async with session.get(url, headers=HEADERS, timeout=5) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                desc_elem = soup.select_one(".popis")
                return desc_elem.text.strip().lower() if desc_elem else ""
    except Exception:
        pass
    return ""

async def check_bazos_guitars(force_send=False):
    found_count = 0
    error_log = None

    urls = [
        "https://hudba.bazos.sk/gitary/",
        "https://hudba.bazos.sk/basgitaru/",
        "https://hudba.bazos.sk/gitary/20/",
        "https://hudba.bazos.sk/basgitaru/20/",
        "https://hudba.bazos.sk/gitary/40/",
        "https://hudba.bazos.sk/basgitaru/40/"
    ]

    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.get(url, headers=HEADERS, timeout=10) as response:
                    if response.status != 200:
                        error_log = f"Bazoš вернул статус HTTP {response.status}"
                        continue
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    ads = soup.select(".inzeraty")
                    
                    if not ads:
                        error_log = "Не удалось распарсить блоки объявлений (.inzeraty)"
                        continue

                    for ad in ads:
                        title_elem = ad.select_one(".inzeratynadpis a")
                        price_elem = ad.select_one(".inzeratycena")
                        short_desc_elem = ad.select_one(".popis")
                        
                        if not title_elem or not price_elem:
                            continue
                            
                        ad_url = "https://hudba.bazos.sk" + title_elem["href"]
                        ad_id = ad_url.split('/')[4] if len(ad_url.split('/')) > 4 else ad_url
                        
                        if not force_send and ad_id in seen_ads:
                            continue
                            
                        title = title_elem.text.strip()
                        title_lower = title.lower()
                        short_desc = short_desc_elem.text.strip().lower() if short_desc_elem else ""
                        price_raw = price_elem.text.strip().lower()

                        digits = re.findall(r'\d+', price_raw)
                        price = float("".join(digits)) if digits else None

                        is_bass = "basgitaru" in ad_url or any(kw in title_lower or kw in short_desc for kw in BASS_KEYWORDS)
                        has_strat_tele = any(kw in title_lower or kw in short_desc for kw in STRAT_TELE_KEYWORDS)
                        has_exchange = any(kw in short_desc or kw in title_lower or kw in price_raw for kw in EXCHANGE_KEYWORDS)
                        
                        if not has_exchange and (price is None or price >= 600):
                            full_desc = await fetch_full_description(session, ad_url)
                            has_exchange = any(kw in full_desc for kw in EXCHANGE_KEYWORDS)

                        match_reason = None

                        if has_exchange and (price is None or price >= 600):
                            match_reason = "🔄 Вариант для обмена"
                        elif has_strat_tele and price is not None and price >= 600:
                            match_reason = "🎸 Telecaster / Stratocaster (от 600€)"
                        elif is_bass and price is not None and 0 < price <= 150:
                            match_reason = "🔥 Бюджетный бас (до 150€)"

                        if match_reason:
                            seen_ads.add(ad_id)
                            found_count += 1
                            price_display = f"{int(price)} €" if price else "Vymením / Dohodou"
                            text = (
                                f"🎯 **{match_reason}**\n\n"
                                f"📌 **Инструмент:** {title}\n"
                                f"💰 **Цена:** {price_display}\n"
                                f"🔗 [Открыть на Bazoš]({ad_url})"
                            )
                            await bot.send_message(chat_id=MY_CHAT_ID, text=text, parse_mode="Markdown")
                            await asyncio.sleep(0.2)
            except Exception as e:
                error_log = str(e)

    return found_count, error_log

async def start_web_server():
    from aiohttp import web
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Guitar Bot Active"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

async def main():
    scheduler.add_job(check_bazos_guitars, 'interval', minutes=15)
    scheduler.start()
    
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
