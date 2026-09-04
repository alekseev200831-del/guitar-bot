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
        "Отслеживаю:\n"
        "1. Обмен от 600€ (или Vymením/Dohodou)\n"
        "2. Telecaster / Stratocaster от 600€\n"
        "3. Басы до 150€\n\n"
        "Напиши /test для проверки Bazoš.",
        parse_mode="Markdown"
    )

@dp.message(Command("test"))
async def test_handler(message: types.Message):
    await message.answer("🔍 Запускаю полный анализ Bazoš.sk (со сканированием страниц объявлений)...")
    found = await check_bazos_guitars(force_send=True)
    if not found:
        await message.answer("ℹ️ Подходящих объявлений по заданным критериям прямо сейчас нет. Мониторинг ищет новые лоты каждые 15 минут!")

async def fetch_full_description(session, url):
    """Заходит внутрь объявления и получает полный текст"""
    try:
        async with session.get(url, timeout=5) as resp:
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                desc_elem = soup.select_one(".popis")
                return desc_elem.text.strip().lower() if desc_elem else ""
    except Exception:
        pass
    return ""

async def check_bazos_guitars(force_send=False):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    found_any = False

    # Сканируем первые 5 страниц (100 объявлений)
    urls_to_check = []
    for page in range(0, 100, 20):
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

                        digits = re.sub(r"[^\d]", "", price_raw)
                        price = float(digits) if digits else None

                        match_reason = None

                        # Быстрая проверка совпадений
                        has_exchange_short = any(kw in short_desc or kw in title_lower or kw in price_raw for kw in EXCHANGE_KEYWORDS)
                        has_strat_tele = any(kw in short_desc or kw in title_lower for kw in STRAT_TELE_KEYWORDS)

                        # Если есть подозрение на обмен, но в кратком описании слова нет — заходим внутрь объявления
                        full_desc = short_desc
                        if not has_exchange_short and (price is None or price >= 600):
                            full_desc = await fetch_full_description(session, ad_url)

                        has_exchange = has_exchange_short or any(kw in full_desc for kw in EXCHANGE_KEYWORDS)

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
                            await asyncio.sleep(0.3)
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
