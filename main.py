import os
import requests
import schedule
import time
import json
from bs4 import BeautifulSoup
from telegram import Bot
from datetime import datetime, timedelta

# === Конфиг ===
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TZ_OFFSET = int(os.environ.get("TZ_OFFSET", "5"))  # часовой пояс

POST_TIMES = ["09:00", "21:00"]  # локальное время
SEEN_FILE = "seen_posts.json"

bot = Bot(token=TELEGRAM_TOKEN)

# === Работа с файлом уже опубликованных постов ===
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen_ids):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_ids), f)

seen_ids = load_seen()

# === Получение топ-новостей ===
def get_top_posts(limit=5):
    url = "https://news.ycombinator.com/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    posts = []
    for item in soup.select(".athing")[:limit]:
        post_id = item["id"]
        title = item.select_one(".titleline a").text
        link = item.select_one(".titleline a")["href"]
        posts.append((post_id, title, link))
    return posts

# === Генерация текста через Gemini ===
def generate_post(title, link):
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Сделай цепляющий, короткий пост для Telegram по новости: '{title}'. Ссылка: {link}."
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(endpoint, json=payload)
        raw_text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Берём только первую строку
        clean_text = raw_text.split("\n")[0]
        return clean_text
    except Exception as e:
        print(f"[❌] Ошибка Gemini: {e}")
        return f"{title}\n{link}"

# === Отправка в Telegram ===
def post_to_telegram(text):
    try:
        bot.send_message(chat_id=TELEGRAM_CHANNEL, text=text, parse_mode="HTML")
        print(f"[✅] Отправлено в канал: {text[:60]}...")
    except Exception as e:
        print(f"[❌] Ошибка Telegram: {e}")

# === Основная задача ===
def job():
    global seen_ids
    print(f"[🕒] Запуск постинга в {datetime.utcnow()} UTC")
    for post_id, title, link in get_top_posts():
        if post_id in seen_ids:
            print(f"[⏭] Пропущено (уже было): {title}")
            continue
        text = generate_post(title, link)
        post_to_telegram(text)
        seen_ids.add(post_id)
        save_seen(seen_ids)
        break  # публикуем только одну новость за раз

# === Планировщик ===
def schedule_jobs():
    for local_time in POST_TIMES:
        hours, minutes = map(int, local_time.split(":"))
        utc_time = (datetime(2000, 1, 1, hours, minutes) - timedelta(hours=TZ_OFFSET)).time()
        schedule.every().day.at(utc_time.strftime("%H:%M")).do(job)
        print(f"[⏰] Запланировано: {local_time} (локальное) / {utc_time.strftime('%H:%M')} UTC")

if __name__ == "__main__":
    job()  # сразу постим при запуске
    schedule_jobs()
    while True:
        schedule.run_pending()
        time.sleep(1)
