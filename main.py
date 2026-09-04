import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === НАСТРОЙКИ ===
BOT_TOKEN = "8976928394:AAHcq8RzfMte_PFREl2nHGA2Wij2JeeBRSc"
MY_CHAT_ID = 800295680  # ВСТАВЬ СВОЙ ЦИФРОВОЙ ID ИЗ USERINFOBOT

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Память для уже проверенных объявлений
seen_ads = set()

# Ключевые слова для обмена на Bazoš
EXCHANGE_KEYWORDS = [
    "výmena", "vymením", "vymena", "vymenim", 
    "na výmenu", "na vymenu", "možná výmena", "mozna vymena"
]

URLS = [
    "https://hudba.bazos.sk/gitary/",
    "https://hudba.bazos.sk/basgitaru/"
]

async def check_bazos_guitars():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        for base_url in URLS:
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
                        
                        if ad_id in seen_ads:
                            continue
                            
                        title = title_elem.text.strip()
                        desc = desc_elem.text.strip().lower() if desc_elem else ""
                        price_text = price_elem.text.replace(" ", "").replace("€", "").strip()
                        
                        try:
                            price = float(re.sub(r"[^\d]", "", price_text))
                        except ValueError:
                            continue

                        # Ищем гитары и басы от 600€ до 850€
                        if 600 <= price <= 850:
                            has_exchange = any(kw in desc or kw in title.lower() for kw in EXCHANGE_KEYWORDS)
                            
                            # Запоминаем объявление
                            seen_ads.add(ad_id)
                            
                            if has_exchange:
                                text = (
                                    f"🎸 **НАЙДЕН ВАРИАНТ ДЛЯ ОБМЕНА!**\n\n"
                                    f"📌 **Инструмент:** {title}\n"
                                    f"💰 **Цена:** {int(price)} €\n"
                                    f"🔗 [Открыть на Bazoš]({ad_url})"
                                )
                                await bot.send_message(chat_id=MY_CHAT_ID, text=text, parse_mode="Markdown")
            except Exception as e:
                print(f"Ошибка при парсинге Bazoš: {e}")

# Минимальный веб-сервер для Render Health Check
async def start_web_server():
    from aiohttp import web
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Guitar Bot Active"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

async def main():
    # Проверка Bazoš каждые 15 минут
    scheduler.add_job(check_bazos_guitars, 'interval', minutes=15)
    scheduler.start()
    
    # Запуск первой проверки сразу при старте
    asyncio.create_task(check_bazos_guitars())
    
    print("🎸 Гитарный бот запущен!")
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
