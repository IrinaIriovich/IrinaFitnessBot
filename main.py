import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import datetime
import asyncio

TOKEN = "7820484983:AAEBNzPMjEBp1GF8YG5O3AdwBi_QiqWyWfQ"

user_log = {}
reply_keyboard = [["✅ Да", "⚠️ Частично", "❌ Нет"]]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я твой бот-тренер 💪")

async def morning_workout(context: ContextTypes.DEFAULT_TYPE):
    weekday = datetime.datetime.now().strftime('%A')
    workouts = {
        "Monday": "Понедельник: Растяжка + 20 минут ходьбы",
        "Tuesday": "Вторник: Силовая: присед 3x15, мостик 3x20, планка",
        "Wednesday": "Среда: Хип-хоп 20 мин + вакуум 3x30 сек",
        "Thursday": "Четверг: Пресс + растяжка",
        "Friday": "Пятница: Прогулка или отдых",
        "Saturday": "Суббота: Кардио + пресс",
        "Sunday": "Воскресенье: Вакуум + замеры тела"
    }
    plan = workouts.get(datetime.datetime.now().strftime('%A'), "Свободный день!")
    await context.bot.send_message(
    chat_id=context.job.chat_id,
    text=f"📌 Тренировка на сегодня:\n{plan}"
)
async def evening_checkin(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=context.job.chat_id,
        text="Удалось выполнить тренировку сегодня?", reply_markup=markup)

async def weekly_measurement(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=context.job.chat_id,
        text="📏 Воскресенье! Не забудь сделать замеры: талия, живот, бёдра, вес")

async def log_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.first_name
    response = update.message.text
    date = datetime.datetime.now().strftime('%Y-%m-%d')
    user_log[date] = response
    messages = {
        "✅ Да": ["Ты большая молодец! 🌟", "Уважение! Сила и дисциплина — твоё всё 💪", "Так держать, прогресс идёт! 🔥"],
        "⚠️ Частично": ["Главное — не останавливаться 👣", "Уже лучше, чем ничего. Завтра дожмём!", "Ты стараешься — и это видно 👏"],
        "❌ Нет": ["Иногда нужен отдых. Завтра — вперёд!", "Пауза — не провал. Ты всё равно в игре!", "Пропуск — это просто точка запятой. Продолжим!"]
    }
    import random
    msg = random.choice(messages.get(response, ["Записано ✅"]))
    await update.message.reply_text(f"{msg}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_response))

    async def scheduler():
        while True:
            now = datetime.datetime.now()
            seconds_until_9 = ((9 - now.hour) % 24) * 3600
            seconds_until_23 = ((23 - now.hour) % 24) * 3600
            seconds_until_sun_12 = (((6 - now.weekday()) % 7) * 86400 + (12 - now.hour) * 3600)

            await asyncio.sleep(5)
            app.job_queue.run_once(morning_workout, seconds_until_9, chat_id=191224401)
            app.job_queue.run_once(evening_checkin, seconds_until_23, chat_id=191224401)
            app.job_queue.run_once(weekly_measurement, seconds_until_sun_12, chat_id=191224401)

    app.run_polling()

if __name__ == "__main__":
    main()
