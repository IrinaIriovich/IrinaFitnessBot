import os
import random
import logging
import time
import asyncio
import threading
from datetime import datetime, time as dtime
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

TOKEN = "7820484983:AAECgwo0IlJaChQpoUeKsIx-DQvTTuKOyo"
WEBHOOK_URL = "https://irinafitnessbot.onrender.com/webhook"

app = Flask(__name__)
application = None

# --- Тренировки ---
WEEKLY_PLAN = [
    ("Кардио", ["Бёрпи – 3 подхода по 10", "Прыжки с разведением рук – 3×30 сек"]),
    ("Тренировка с тренером", []),
    ("Силовая", ["Приседания с весом – 3×12", "Отжимания – 3×10"]),
    ("Растяжка", ["Наклоны к полу – 3×30 сек", "Бабочка – 3×30 сек"]),
    ("Функциональная", ["Планка – 3×1 мин", "Выпады – 3×12 на каждую ногу"]),
    ("Йога", ["Собака мордой вниз – 3×1 мин", "Поза ребёнка – 3×1 мин"]),
    ("Восстановление", ["Медитация – 5 мин", "Глубокое дыхание – 3 мин"])
]

MOTIVATIONS = [
    "Ты сильнее, чем думаешь 💪",
    "Каждое движение приближает к цели 🧡",
    "Сегодня — отличный день, чтобы двигаться вперёд 🚀",
    "Не сдавайся. Ты уже начала 🔥",
    "Ты достойна заботы о себе 🌿"
]

# --- Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я твой фитнес-бот. Начнём?", reply_markup=get_main_keyboard()
    )

def get_main_keyboard():
    buttons = [
        ["📅 Расписание", "🏃 Внеплановая"],
        ["📊 Отчёт", "❓ Что было"],
        ["🌿 Настройся на себя"]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📅 Расписание":
        await update.message.reply_text(get_schedule(), reply_markup=get_main_keyboard())

    elif text == "🏃 Внеплановая":
        await send_today_workout(update)

    elif text == "❓ Что было":
        weekday = datetime.now().weekday()
        name, plan = WEEKLY_PLAN[weekday]
        await update.message.reply_text(f"Сегодня: {name}\n\n" + "\n".join(plan or ["Занятие с тренером"]))

    elif text == "📊 Отчёт":
        await update.message.reply_text("Скоро здесь появится отчёт 📈")

    elif text == "🌿 Настройся на себя":
        await update.message.reply_text(random.choice(MOTIVATIONS), reply_markup=get_main_keyboard())

async def send_today_workout(update: Update):
    weekday = datetime.now().weekday()
    name, plan = WEEKLY_PLAN[weekday]
    msg = f"📋 План на сегодня: {name}\n\n" + "\n".join(plan or ["Занятие с тренером"])
    await update.message.reply_text(msg)

    # Опрос
    buttons = [
        [KeyboardButton("✅ Да"), KeyboardButton("🟡 Частично"), KeyboardButton("❌ Нет")]
    ]
    await update.message.reply_text("Удалось выполнить тренировку?", reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True))

# --- План и вдохновение ---
async def morning_plan():
    chat_id = 191224401
    weekday = datetime.now().weekday()
    name, plan = WEEKLY_PLAN[weekday]
    msg = f"Доброе утро! ☀️\n\n📋 Сегодня: {name}\n\n" + "\n".join(plan or ["Занятие с тренером"])
    await application.bot.send_message(chat_id=chat_id, text=msg)

    # Опрос
    buttons = [
        [KeyboardButton("✅ Да"), KeyboardButton("🟡 Частично"), KeyboardButton("❌ Нет")]
    ]
    await application.bot.send_message(chat_id=chat_id, text="Удалось выполнить тренировку?", reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True))

async def weekly_reminder():
    chat_id = 191224401
    await application.bot.send_message(chat_id=chat_id, text="📏 Не забудь сделать замеры тела!")

async def send_inspiration():
    chat_id = 191224401
    await application.bot.send_message(chat_id=chat_id, text=random.choice(MOTIVATIONS))

def schedule_tasks():
    now = datetime.now()
    loop = asyncio.get_event_loop()

    async def daily():
        while True:
            now = datetime.now()
            if now.time() >= dtime(9, 0) and now.time() < dtime(9, 1):
                await morning_plan()
                await asyncio.sleep(60)
            elif now.weekday() == 6 and now.time() >= dtime(12, 0) and now.time() < dtime(12, 1):
                await weekly_reminder()
                await asyncio.sleep(60)
            else:
                await asyncio.sleep(30)

    async def inspiration_loop():
        while True:
            now = datetime.now()
            next_delay = random.randint(3600, 46800)  # между 1 и 13 часами
            await asyncio.sleep(next_delay)
            await send_inspiration()

    loop.create_task(daily())
    loop.create_task(inspiration_loop())

# --- Webhook ---
@app.route("/webhook", methods=["POST"])
def webhook():
    global application
    if request.method == "POST":
        if not application or not getattr(application, "bot", None):
            return "bot not ready", 503
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, application.bot)
        application.update_queue.put(update)
        return "ok", 200
    return "not allowed", 405

def run_flask():
    app.run(host="0.0.0.0", port=10000)

# --- Main ---
async def main():
    global application
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    await application.initialize()
    await application.start()
    await application.bot.set_webhook(WEBHOOK_URL)

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    schedule_tasks()
    print("[INIT] Бот запущен")
    await application.updater.start_polling()
    await application.updater.idle()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
