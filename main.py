import os
import requests
import schedule
import time
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime, timedelta

# === Конфиг ===
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]  # токен бота
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL"]  # @имя_канала
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]  # ключ Gemini
TZ_OFFSET = int(os.environ.get("TZ_OFFSET", "5"))  # сдвиг времени (по умолчанию +5)

POST_TIMES = ["09:00", "21:00"]  # время постинга по местному времени

bot = Bot(token=TELEGRAM_TOKEN)

# === Получение топ-новостей ===
def get_top_posts(limit=2):
    url = "https://news.ycombinator.com/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    posts = []
    for item in soup.select(".athing")[:limit]:
        title = item.select_one(".titleline a").text
        link = item.select_one(".titleline a")["href"]
        posts.append((title, link))
    return posts

# === Генерация текста через Gemini ===
def generate_post(title, link):
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Сделай мемный, короткий и цепляющий пост для Telegram по новости: '{title}'. Ссылка: {link}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(endpoint, json=payload)
    try:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return f"{title}\n{link}"

# === Постинг в Telegram ===
def post_to_telegram(text):
    bot.send_message(chat_id=TELEGRAM_CHANNEL, text=text, parse_mode="HTML")

# === Задача для расписания ===
def job():
    print(f"🚀 Постим в {datetime.utcnow()} UTC")
    for title, link in get_top_posts():
        text = generate_post(title, link)
        post_to_telegram(text)

# === Планировщик ===
def schedule_jobs():
    for local_time in POST_TIMES:
        # конвертация локального времени в UTC
        hours, minutes = map(int, local_time.split(":"))
        utc_time = (datetime(2000, 1, 1, hours, minutes) - timedelta(hours=TZ_OFFSET)).time()
        schedule.every().day.at(utc_time.strftime("%H:%M")).do(job)
        print(f"⏰ Запланировано на {utc_time.strftime('%H:%M')} UTC ({local_time} по местному)")

if __name__ == "__main__":
    schedule_jobs()
    while True:
        schedule.run_pending()
        time.sleep(1)
