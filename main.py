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

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "🎸 **Радар гитар Bazoš запущен!**\n\n"
        "Я отслеживаю (глубина 10 страниц):\n"
        "1. Любые гитары/басы от 600€ (или Vymením/Dohodou) с обменом\n"
        "2. Телекастеры и Стратокастеры от 600€\n"
        "3. Бюджетные бас-гитары до 150€\n\n"
        "Напиши /test чтобы запустить глубокий поиск прямо сейчас.",
        parse_mode="Markdown"
    )

@dp.message(Command("test"))
async def test_handler(message: types.Message):
    await message.answer("🔍 Проверяю первые 10 страниц Bazoš.sk (до 200 объявлений)... Это займет ~10 секунд.")
    found = await check_bazos_guitars(force_send=True)
    if not found:
        await message.answer("ℹ️ Подходящих объявлений не найдено.")

async def check_bazos_guitars(force_send=False):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    found_any = False

    # Сканируем 10 страниц (0, 20, 40 ... 180) для гитар и басов
    urls_to_check = []
    for page in range(0, 200, 20):
        page_str = f"{page}/" if page > 0 else ""
        urls_to_check.append(("guitar", f"https://hudba.bazos.sk/gitary/{page_str}"))
        urls_to_check.append(("bass", f"https://hudba.bazos.sk/basgitaru/{page_str}"))

    async with aiohttp.ClientSession(headers=headers) as session:
        for section, url in urls_to_check:
            try:
                async with session.get(url) as response:
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
                        price_raw = price_elem.text.strip().lower()

                        digits = re.sub(r"[^\d]", "", price_raw)
                        price = float(digits) if digits else None

                        match_reason = None

                        has_exchange = any(kw in desc or kw in title_lower or kw in price_raw for kw in EXCHANGE_KEYWORDS)
                        has_strat_tele = any(kw in desc or kw in title_lower for kw in STRAT_TELE_KEYWORDS)

                        # 1. Обмен (цена >= 600€ или Vymením/Dohodou)
                        if has_exchange and (price is None or price >= 600):
                            match_reason = "🔄 Вариант для обмена"

                        # 2. Strat / Telecaster от 600€
                        elif has_strat_tele and price is not None and price >= 600:
                            match_reason = "🎸 Telecaster / Stratocaster (от 600€)"

                        # 3. Бюджетный бас до 150€
                        elif section == "bass" and price is not None and 0 < price <= 150:
                            match_reason = "🔥 Бюджетный бас (до 150€)"

                        if match_reason:
                            seen_ads.add(ad_id)
                            found_any = True
                            price_display = f"{int(price)} €" if price else "Vymením / Dohodou"
                            text = (
                                f"🎯 **{match_reason}**\n\n"
                                f"📌 **Инструмент:** {title}\n"
                                f"💰 **Цена:** {price_display}\n"
                                f"🔗 [Открыть на Bazoš]({ad_url})"
                            )
                            await bot.send_message(chat_id=MY_CHAT_ID, text=text, parse_mode="Markdown")
                
                # Небольшая пауза 0.5 сек между запросами страниц
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Ошибка при парсинге: {e}")
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
