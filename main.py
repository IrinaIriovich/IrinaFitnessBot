from keep_alive import keep_alive
from telegram.ext import ContextTypes
from datetime import datetime, timedelta, timezone, time as dt_time
import random
# 💬 Функция отправки вдохновения
async def send_random_inspiration(context: ContextTypes.DEFAULT_TYPE):
    phrase = random.choice(inspiration_phrases)
    await context.bot.send_message(chat_id=191224401, text=f"✨ {phrase}")
# 🧩 Убедимся, что job_queue инициализирован
async def setup_jobqueue(app):
    if not hasattr(app, "job_queue") or app.job_queue is None:
        print("[ERROR] job_queue is not available.")
        return

    print(f"[DEBUG] job_queue initialized: {app.job_queue is not None}")

    #schedule_inspiration_job(app)
    from pytz import timezone
    moscow_tz = timezone("Europe/Moscow")

    app.job_queue.run_daily(
        auto_what_was_message,
        time=dt_time(hour=9, minute=30, tzinfo=moscow_tz),
        name="auto_what_was"
    )
    print(f"[DEBUG] app.job_queue is available: {hasattr(app, 'job_queue') and app.job_queue is not None}")

# ⏰ Планировщик с рандомным временем (10:00–23:00) по Москве
from pytz import timezone

def schedule_next_inspiration(application):
    tz = timezone("Europe/Moscow")
    now = datetime.now(tz)
    hour = random.randint(10, 22)
    minute = random.randint(1, 59)
    next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_time < now:
        next_time += timedelta(days=1)

    delay = (next_time - now).total_seconds()
    print(f"[✔] Следующая мотивация будет отправлена в {next_time.strftime('%H:%M')} по Москве")
    application.job_queue.run_once(send_random_inspiration, when=delay)

async def send_random_inspiration(context: ContextTypes.DEFAULT_TYPE):
    phrase = random.choice(inspiration_phrases)
    for user_id in context.bot_data.get("users", []):
        await context.bot.send_message(chat_id=user_id, text=f"✨ {phrase}")
    # Планируем следующее сообщение
    schedule_next_inspiration(context.application)

# main.py
import logging
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, CallbackQueryHandler
import requests
# Ссылка на рабочий Web Apps скрипт Google Apps Script
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxBWSJgOMLcLqHD6DsC9LKjRxtdjsSUvr_r-VFCx1Pxu9ZX7a93ZDwoBDTqtGi3bPeJ/exec"
# Включаем логирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
# Главное меню
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("📅 Расписание"), KeyboardButton("🏃 Внеплановая")],
        [KeyboardButton("❓ Что было"), KeyboardButton("📊 Отчёт")],
        [KeyboardButton("🫶 Настройся на себя")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
# Ответные фразы
replies_positive = [
    "Ты супер! 🔥", "Молодец! Так держать 💥", "Отличная работа! 👍",
    "Ура! Так держать! 💪", "Ты сделала это! 💯", "Вот это настрой! 👏"
]
replies_partial = [
    "Неплохо! В следующий раз — ещё лучше 💡", "Ты на пути к цели 💫",
    "Частично — тоже результат! 👣", "Главное — не останавливаться 🌱"
]
replies_negative = [
    "Не получилось — бывает. Завтра будет шанс снова ✨",
    "Главное — не сдаваться! 💪",
    "Двигаемся дальше, даже если не идеально 🧭"
]
GUIDES = {
    "Бёрпи": "🤸‍♀️ Присед → опора на руки → отжимание → прыжок. Держи корпус ровным, приземляйся мягко.",
    "Альпинист": "⛰ Упор лёжа, колени поочерёдно к груди. Пресс — в напряжении!",
    "Бег на месте": "🏃 Поднимай колени выше, руки — активно. Темп уверенный!",
    "Прыжки звезда": "⭐ Прыжок с разведением рук и ног. Мягко приземляйся.",
    "Скалолаз": "🧗 Быстро и ритмично, не забывай про пресс!",
    "Высокие колени": "💥 Колени выше пояса, дыхание — не сбивай.",
    "Приседания": "🦵 Колени не выходят за носки, спина прямая. Движение от таза.",
    "Отжимания": "💪 Корпус ровный, локти под 45°. Можно с колен.",
    "Узкие отжимания": "🎯 Локти близко к телу — трицепс включается!",
    "Выпады": "🚶‍♀️ Колено над пяткой, держи баланс.",
    "Ягодичный мост": "🍑 Подъём таза за счёт ягодиц, не прогибай поясницу.",
    "Махи ногами": "👢 Назад с усилием, корпус зафиксирован.",
    "Супермен": "🦸 Лёжа — поднимай руки и ноги. Поясница не перегибается.",
    "Гудморнинг": "🧍‍♀️ Наклон с прямой спиной. Тянется задняя поверхность бедра.",
    "Скручивания": "🌀 Подбородок вверх, поясница на полу. Без рывков.",
    "Русский твист": "🪑 Повороты корпуса, косые мышцы включаются!",
    "Ножницы": "✂️ Прямые ноги, не отрывай поясницу.",
    "Складка": "📐 Руки и ноги навстречу, выдох — вверх.",
    "Велосипед": "🚴‍♀️ Ритм средний, локоть — к противоположному колену.",
    "Планка": "📏 Локти под плечами, не прогибайся в спине.",
    "Планка боковая": "↔️ Бёдра на линии, локоть под плечом.",
    "Планка с касанием плеч": "🤸 Старайся не раскачиваться при касании.",
    "Медвежий шаг": "🐻 Колени над полом, спина параллельно полу. Шагай плавно.",
    "Выпады с касанием пола": "🖐 Добавь лёгкое касание рукой — работает координация.",
    "Бег на месте с паузой": "⏸ Бег с микропаузами. Пульс вверх!",
    "Наклоны вперёд": "🧘‍♀️ Тянись от таза, не скругляй спину.",
    "Бабочка": "🦋 Колени к полу, не торопись — дыхание ровное.",
    "Шпагат или к нему": "⚠️ Только в комфорт — никаких рывков!",
    "Кошка-корова": "🐈 Спина — выгибай и прогибай. Синхронно с дыханием.",
    "Повороты корпуса лёжа": "🌪 Плавно, колени вместе, таз расслаблен.",
    "Растяжка на спину": "🌙 Колени к груди, перекаты — мягко и приятно."
}
inspiration_phrases = [
    "Сегодня — хороший день, чтобы начать! 💪",
    "Пусть сегодня будет тот день, когда ты собой гордишься ✨",
    "Каждое повторение — инвестиция в себя 📈",
    "Сделай это для себя. А ещё для красивых фоток 😉",
    "Если не сейчас — то когда? А ты уже в пути. 🚀",
    "Завтра ты поблагодаришь себя за это решение 💚",
    "Ты не обязана быть супергероем. Но спортивный костюм тебе к лицу 🦸‍♀️", 
    "Главное — не идеально, а регулярно. Даже если в пижаме 📆", 
    "Усталость пройдёт, а радость за себя останется. Ну или крепатура 💪",
    "Красивый пресс не главное. Главное — не отжиматься от реальности 🤸", 
    "Твоё тело скажет спасибо. Ну... может, не сразу 🧘", 
    "Сегодняшний ты — апгрейд вчерашнего 🔁", 
    "Даже супергерои делают перерыв на растяжку 🦸‍♂️", 
    "Удалось ли сегодня немного побыть с собой? Даже 1 движение — уже контакт 🧘"
]

SUPPORT_PHRASES = [
    "Ты уже сделала первый шаг — а это главное 🌱",
    "Когда ты рядом с собой — всё становится возможным 💫",
    "В тишине рождается сила. Ты с ней на связи 🤍",
    "Ничего не нужно доказывать. Просто будь собой ☀️",
    "Это маленькое касание к себе — как глубокий вдох 🌬",
    "Сегодня ты выбрала заботу. И это всегда правильно 🧘",
    "Ты здесь. Этого достаточно 🌍",
    "Настрой приходит не извне — он уже внутри ✨",
    "Ты умеешь быть с собой. И это твоя суперсила 💚"
]

MICRO_PRACTICES = [
    "Закрой глаза на 10 секунд и просто подыши 🌬",
    "Почувствуй, как стопы касаются пола 👣",
    "Покрути плечами назад и вперёд, медленно 🔄",
    "Сделай глубокий вдох на 4, выдох на 6 — трижды 🌿",
    "Положи ладонь на грудь и просто побудь так 🤲",
    "Потрогай свои ладони. Почувствуй их тепло 🖐️",
    "Смотри в окно 15 секунд. Просто будь 🪟",
    "Почувствуй опору под телом — ты здесь 📍",
    "Сделай лёгкий наклон головы в сторону и задержись 🧘",
    "Ничего не делай 30 секунд. Это тоже забота 🫖"
]

morning_greetings = [
    "☀️ Доброе утро! Сегодня ты — свой главный приоритет. Вот что для тебя приготовлено:",
    "🌿 Доброе утро! Начни день с движения — мягко, с заботой о себе:",
    "🔥 Доброе утро! Давай сделаем этот день бодрым — начнём с короткого ритуала:",
    "🌱 Доброе утро! Всё, что нужно — просто начать. Вот с чего:",
    "💫 Доброе утро! Дышим, двигаемся, живём. Сегодня — день с телом:",
    "☕ Доброе утро! Твоё утро начинается с простого шага к себе:",
    "🌅 Доброе утро. Давай мягко встретим этот день. Вот что поможет:",
    "💛 Доброе утро! Твоё тело будет благодарно за эти 10 минут заботы:",
]

def format_workout_with_guides(workout):
    formatted = []
    for i, w in enumerate(workout):
        base = f"{i+1}. {w}"
        # Универсальный способ получить название упражнения
        base_name = str(w).split(" 3×")[0].split("×")[0].strip()
        for key in GUIDES:
            if base_name in key:
                base += f"\n {GUIDES[key]}"
                break
        formatted.append(base)
    return "\n\n".join(formatted)
def get_random_workout():
    import random
    valid_days = [WEEKLY_PLAN[i][1] for i in WEEKLY_PLAN if WEEKLY_PLAN[i][1]]
    return random.choice(valid_days) if valid_days else []
def get_response_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💪 Да", callback_data="response_да"),
            InlineKeyboardButton("🤏 Частично", callback_data="response_частично"),
            InlineKeyboardButton("🫠 Нет", callback_data="response_нет"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
# Расписание по дням недели
WEEKLY_PLAN = {
        0: ("Кардио", [
            ["Бёрпи 3×10", "Альпинист 3×20", "Бег на месте 3×2 мин"],
            ["Прыжки звезда 3×20", "Скалолаз 3×30 сек", "Высокие колени 3×40 сек"]
        ]),
        1: ("С тренером", []),
        2: ("Силовая", [
            ["Приседания 3×15", "Отжимания 3×10", "Махи ногами 3×20"],
            ["Выпады 3×12", "Узкие отжимания 3×8", "Ягодичный мост 3×20"],
            ["Супермен 3×20", "Присед с подъёмом руки 3×12", "Гудморнинг 3×15"]
        ]),
        3: ("Пресс", [
            ["Скручивания 3×20", "Планка 3×30 сек", "Альпинист 3×20"],
            ["Русский твист 3×30", "Планка боковая 3×20", "Ножницы 3×30"],
            ["Складка 3×15", "Планка с касанием плеч 3×20", "Велосипед 3×40 сек"]
        ]),
        4: ("Функциональная", [
            ["Прыжки звезда 3×20", "Медвежий шаг 3×1 мин", "Планка 3×45 сек"],
            ["Бёрпи 3×10", "Выпады с касанием пола 3×12", "Бег на месте с паузой 3×40 сек"]
        ]),
        5: ("Растяжка", [
            ["Наклоны вперёд", "Бабочка", "Шпагат или к нему"],
            ["Кошка-корова", "Повороты корпуса лёжа", "Растяжка на спину"]
        ]),
        6: ("Свободный день", [])
    }
# Тренировка на день недели
def get_daily_workout():
    day_index = datetime.now().weekday()
    _, options = WEEKLY_PLAN.get(day_index, ("", []))
    return random.choice(options) if options else []
# Запись в Google Таблицу
def send_to_gsheet(user_id, date_str, workout_type, response):
    logging.info(f"Отправка в Google Таблицу: {user_id}, {date_str}, {workout_type}, {response}")
    data = {
        "user_id": user_id,
        "date": date_str,
        "workout_type": workout_type,
        "response": response
    }
    try:
        response_post = requests.post(GOOGLE_SCRIPT_URL, data=data, timeout=10)
        if response_post.status_code == 200:
            logging.info("Успешно отправлено в Google Таблицу.")
        else:
            logging.warning(f"Не удалось отправить в Google Таблицу: код {response_post.status_code}")
    except Exception as e:
        logging.error(f"Ошибка при отправке в Google Таблицу: {e}")

# Команда старт
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if "users" not in context.bot_data:
        context.bot_data["users"] = set()
    context.bot_data["users"].add(user_id)
    await update.message.reply_text("Привет! Готова к тренировке? 💪", reply_markup=get_main_keyboard())
# Обработка сообщений
async def handle_message(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.effective_user.id
    date_str = datetime.now().strftime("%Y-%m-%d")
    if text == "❓ Что было":
        workout = get_daily_workout()
        if workout:
            formatted = format_workout_with_guides(workout)
            await update.message.reply_text(
                f"Сегодняшняя тренировка:\n{formatted}\nУдалось выполнить?",
                reply_markup=get_response_keyboard()
            )
            context.user_data["workout"] = workout
            context.user_data["date"] = date_str
            context.user_data["type"] = "плановая"
    elif text == "📅 Расписание":
        schedule = "📅 Расписание на неделю:"
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        emoji_list = ["🏃‍♂️", "🧑‍🏫", "🏋️‍♀️", "🧘‍♀️", "🤸‍♂️", "🧘‍♂️", "😌"]
        for i in range(7):
            name, _ = WEEKLY_PLAN[i]
            emoji = emoji_list[i]
            schedule += f"\n{days[i]} — {name} {emoji}"
        await update.message.reply_text(
            schedule,
            reply_markup=get_main_keyboard()
        )
    elif text == "🏃 Внеплановая":
        workout_groups = get_random_workout()
        workout = random.choice(workout_groups) if workout_groups else []
        formatted = format_workout_with_guides(workout)
        await update.message.reply_text(
            f"Вот твоя внеплановая тренировка:\n{formatted}\nУдалось выполнить?",
            reply_markup=get_response_keyboard()
        )
        context.user_data["workout"] = workout
        context.user_data["date"] = datetime.now().strftime("%Y-%m-%d")
        context.user_data["type"] = "внеплановая"
    elif text == "🔥 Мотивация":
        phrase = random.choice(inspiration_phrases)
        await update.message.reply_text(f"✨ {phrase}")
    elif text.lower() in ["да", "частично", "нет"]:
        resp_type = context.user_data.get("type", "неизвестно")
        send_to_gsheet(user_id, context.user_data.get("date", date_str), resp_type, text.lower())
        if text.lower() == "да":
            msg = random.choice(replies_positive)
        elif text.lower() == "частично":
            msg = random.choice(replies_partial)
        else:
            msg = random.choice(replies_negative)
        await update.message.reply_text(msg, reply_markup=get_main_keyboard())
    elif text == "📊 Отчёт":
        user_id = update.effective_user.id
        await update.message.reply_text("📊 Формирую твой отчёт...")
        try:
            resp = requests.get(GOOGLE_SCRIPT_URL, params={"action": "report", "user_id": user_id}, timeout=10)
            if resp.status_code == 200:
                await update.message.reply_text(resp.text, reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text("❗ Не удалось получить отчёт. Попробуй позже.", reply_markup=get_main_keyboard())
        except Exception as e:
            logging.error(f"Ошибка при получении отчёта: {e}")
            await update.message.reply_text(
    "⚠️ Возникла ошибка при формировании отчёта. Нажми на кнопку в меню.",
    reply_markup=get_main_keyboard()
            )
    elif text == "🫶 Настройся на себя":
        practice = random.choice(MICRO_PRACTICES)
        await update.message.reply_text(
            f"Попробуй прямо сейчас:\n\n{practice}",
    reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📍 Я здесь", callback_data="support_done")],
            [InlineKeyboardButton("👣 Ещё один шаг к себе", callback_data="more_practice")]
            ])
        )
# Инициализация
async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    date_str = datetime.now().strftime("%Y-%m-%d")

    if query.data.startswith("response_"):
        response = query.data.replace("response_", "")
        workout_type = context.user_data.get("type", "неизвестно")
        send_to_gsheet(user_id, context.user_data.get("date", date_str), workout_type, response)

        if response == "да":
            msg = random.choice(replies_positive)
        elif response == "частично":
            msg = random.choice(replies_partial)
        else:
            msg = random.choice(replies_negative)

        await query.edit_message_text(text=msg)
        await context.bot.send_message(
            chat_id=user_id,
            text="Выберите, что делать дальше:",
            reply_markup=get_main_keyboard()
        )

    elif query.data == "support_done":
        phrase = random.choice(SUPPORT_PHRASES)
        await query.edit_message_text(f"{phrase}")

    elif query.data == "more_practice":
        new_practice = random.choice(MICRO_PRACTICES)
        await query.edit_message_text(
            f"Попробуй ещё одну микропрактику:\n\n{new_practice}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📍Я здесь", callback_data="support_done")],
                [InlineKeyboardButton("👣 Ещё", callback_data="more_practice")]
            ])
        )
# Автоматическое сообщение "Что было" в 9:45
async def auto_what_was_message(context: CallbackContext):
    for user_id in context.bot_data.get("users", []):
        workout = get_daily_workout()
        if workout:
            formatted = format_workout_with_guides(workout)
            await context.bot.send_message(
                chat_id=user_id,greeting = random.choice(morning_greetings)
text = f"{greeting}\n\n{formatted}\nУдалось выполнить?",
                reply_markup=get_response_keyboard()
            )
            context.user_data["workout"] = workout
            context.user_data["date"] = datetime.now().strftime("%Y-%m-%d")
            context.user_data["type"] = "плановая"
from telegram.ext import ApplicationBuilder, JobQueue

def main():
    application = Application.builder()\
        .token("7820484983:AAFy1bXpU8Zx0tvJCtOhgaIeYRKI6YL9WCg")\
        .post_init(setup_jobqueue)\
        .build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
        
    application.run_polling()
import asyncio

if __name__ == "__main__":
    keep_alive()
    main()
