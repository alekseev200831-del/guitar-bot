import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === НАСТРОЙКИ (Ваши токен и Chat ID) ===
BOT_TOKEN = "8976928394:AAHcq8RzfMte_PFREl2nHGA2Wij2JeeBRSc"
MY_CHAT_ID = 800295680

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

seen_ads = set()

# Ключевые слова для поиска
EXCHANGE_KEYWORDS = [
    "výmena", "vymením", "vymena", "vymenim", 
    "na výmenu", "na vymenu", "možná výmena", "mozna vymena",
    "vymeniť", "vymenit", "vymene", "výmene", "doplatok", "doplatom"
]

STRAT_TELE_KEYWORDS = [
    "telecaster", "stratocaster", "tele", "strat"
]

URL_GUITARS = "https://hudba.bazos.sk/gitary/"
URL_BASSES = "https://hudba.bazos.sk/basgitaru/"

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "🎸 **Радар гитар Bazoš запущен!**\n\n"
        "Я отслеживаю:\n"
        "1. Любые гитары/басы от 600€ с возможностью обмена\n"
        "2. Телекастеры и Стратокастеры от 600€\n"
        "3. Бюджетные бас-гитары до 150€\n\n"
        "Напиши /test чтобы запустить поиск прямо сейчас.",
        parse_mode="Markdown"
    )

@dp.message(Command("test"))
async def test_handler(message: types.Message):
    await message.answer("🔍 Проверяю Bazoš.sk по всем критериям...")
    found = await check_bazos_guitars(force_send=True)
    if not found:
        await message.answer("ℹ️ Подходящих объявлений прямо сейчас не найдено. Фоновый мониторинг продолжит поиск каждые 15 минут!")

async def check_bazos_guitars(force_send=False):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    found_any = False

    async with aiohttp.ClientSession(headers=headers) as session:
        for base_url in [URL_GUITARS, URL_BASSES]:
            is_bass_section = (base_url == URL_BASSES)
            try:
                async with session.get(base_url) as response:
                    if response.status != 200:
                        continue
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    ads = soup.select(".inzeraty")
                    
                    for ad in ads:
                        title_elem = ad.select_one(".inzeratynadpis a")
                        price_elem = ad.select_one(".inzeratycena")
                        desc_elem = ad.select_one(".popis")
                        
                        if not title_elem or not price_elem:
                            continue
                            
                        ad_url = "https://hudba.bazos.sk" + title_elem["href"]
                        ad_id = ad_url.split('/')[4] if len(ad_url.split('/')) > 4 else ad_url
                        
                        if not force_send and ad_id in seen_ads:
                            continue
                            
                        title = title_elem.text.strip()
                        title_lower = title.lower()
                        desc = desc_elem.text.strip().lower() if desc_elem else ""
                        price_text = price_elem.text.replace(" ", "").replace("€", "").strip()
                        
                        try:
                            price = float(re.sub(r"[^\d]", "", price_text))
                        except ValueError:
                            continue

                        match_reason = None

                        # Критерий 1: Обмен от 600€
                        if price >= 600 and any(kw in desc or kw in title_lower for kw in EXCHANGE_KEYWORDS):
                            match_reason = "🔄 Вариант для обмена"

                        # Критерий 2: Страт или Телек от 600€
                        elif price >= 600 and any(kw in desc or kw in title_lower for kw in STRAT_TELE_KEYWORDS):
                            match_reason = "🎸 Telecaster / Stratocaster (от 600€)"

                        # Критерий 3: Недорогая бас-гитара до 150€
                        elif is_bass_section and price <= 150 and price > 0:
                            match_reason = "🔥 Бюджетный бас (до 150€)"

                        # Если сработало хотя бы одно правило
                        if match_reason:
                            seen_ads.add(ad_id)
                            found_any = True
                            text = (
                                f"🎯 **{match_reason}**\n\n"
                                f"📌 **Инструмент:** {title}\n"
                                f"💰 **Цена:** {int(price)} €\n"
                                f"🔗 [Открыть на Bazoš]({ad_url})"
                            )
                            await bot.send_message(chat_id=MY_CHAT_ID, text=text, parse_mode="Markdown")
            except Exception as e:
                print(f"Ошибка при парсинге Bazoš: {e}")
    return found_any

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
