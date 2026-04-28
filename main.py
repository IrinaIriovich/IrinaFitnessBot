import os
import logging
import random
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# CONFIG
# =========================

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# Лучше хранить URL в env, но оставляю твой как fallback
GOOGLE_SCRIPT_URL = os.getenv(
    "AppScript",
    "https://script.google.com/macros/s/AKfycbxBWSJgOMLcLqHD6DsC9LKjRxtdjsSUvr_r-VFCx1Pxu9ZX7a93ZDwoBDTqtGi3bPeJ/exec",
)

ADMIN_CHAT_ID = 191224401  # твой id для вдохновения/команды users

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# =========================
# USERS FILE
# =========================

def load_users() -> set[int]:
    try:
        with open("users.txt", "r", encoding="utf-8") as f:
            return set(map(int, f.read().splitlines()))
    except FileNotFoundError:
        return set()
    except Exception as e:
        logger.error(f"Не удалось прочитать users.txt: {e}")
        return set()


def save_user(user_id: int) -> None:
    try:
        with open("users.txt", "a", encoding="utf-8") as f:
            f.write(f"{user_id}\n")
    except Exception as e:
        logger.error(f"Не удалось сохранить user_id в users.txt: {e}")


# =========================
# UI
# =========================

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("📅 Расписание"), KeyboardButton("🏃 Внеплановая")],
        [KeyboardButton("❓ Что было"), KeyboardButton("📊 Отчёт")],
        [KeyboardButton("🫶 Настройся на себя")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_response_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[
        InlineKeyboardButton("⭐ Да", callback_data="response_да"),
        InlineKeyboardButton("🤏 Частично", callback_data="response_частично"),
        InlineKeyboardButton("🫠 Нет", callback_data="response_нет"),
    ]]
    return InlineKeyboardMarkup(keyboard)


# =========================
# PHRASES & GUIDES
# =========================

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


# =========================
# WORKOUT PLAN
# =========================

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


def get_daily_workout():
    day_index = datetime.now(MOSCOW_TZ).weekday()
    _, options = WEEKLY_PLAN.get(day_index, ("", []))
    return random.choice(options) if options else []


def get_random_workout():
    valid_days = [WEEKLY_PLAN[i][1] for i in WEEKLY_PLAN if WEEKLY_PLAN[i][1]]
    return random.choice(valid_days) if valid_days else []


def format_workout_with_guides(workout) -> str:
    formatted = []
    for i, w in enumerate(workout):
        base = f"{i+1}. {w}"
        base_name = str(w).split(" 3×")[0].split("×")[0].strip()

        guide = GUIDES.get(base_name)
        if not guide:
            # мягкий поиск, если в названии есть доп. слова
            for key, val in GUIDES.items():
                if key in base_name or base_name in key:
                    guide = val
                    break

        if guide:
            base += f"\n {guide}"

        formatted.append(base)
    return "\n\n".join(formatted)


# =========================
# GOOGLE SHEET
# =========================

def send_to_gsheet(user_id: int, date_str: str, workout_type: str, response: str) -> None:
    logger.info(f"Отправка в Google Таблицу: {user_id}, {date_str}, {workout_type}, {response}")
    data = {"user_id": user_id, "date": date_str, "workout_type": workout_type, "response": response}
    try:
        r = requests.post(GOOGLE_SCRIPT_URL, data=data, timeout=10)
        if r.status_code == 200:
            logger.info("Успешно отправлено в Google Таблицу.")
        else:
            logger.warning(f"Не удалось отправить в Google Таблицу: код {r.status_code}, текст: {r.text[:200]}")
    except Exception as e:
        logger.error(f"Ошибка при отправке в Google Таблицу: {e}")


# =========================
# JOBS (SCHEDULE)
# =========================

async def morning_message(context: ContextTypes.DEFAULT_TYPE):
    users = context.bot_data.get("users", set())
    if not users:
        return

    date_str = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")

    for user_id in users:
        workout = get_daily_workout()
        if workout:
            formatted = format_workout_with_guides(workout)

            # фиксируем тип/дату для инлайн-кнопок именно у этого пользователя
            context.bot_data.setdefault("last_workout_meta", {})[(user_id, date_str)] = "плановая"

            await context.bot.send_message(
                chat_id=user_id,
                text=f"🏋️ Тренировка дня:\n{formatted}\nУдалось выполнить?",
                reply_markup=get_response_keyboard()
            )


async def send_random_inspiration(context: ContextTypes.DEFAULT_TYPE):
    phrase = random.choice(inspiration_phrases)
    # если хочешь всем пользователям — замени на цикл по users
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"✨ {phrase}")


def schedule_inspiration_job(app: Application):
    # каждый запуск выбираем случайное время на текущие сутки (10:00–23:00 по Москве)
    hour = random.randint(10, 22)
    minute = random.randint(0, 59)
    app.job_queue.run_daily(
        send_random_inspiration,
        time=dt_time(hour=hour, minute=minute, tzinfo=MOSCOW_TZ),
        name="daily_inspiration"
    )
    logger.info(f"Вдохновение запланировано на {hour:02d}:{minute:02d} (MSK)")


async def setup_jobqueue(app: Application):
    if not getattr(app, "job_queue", None):
        logger.error("job_queue is not available.")
        return

    # 06:30 МСК
    app.job_queue.run_daily(
        morning_message,
        time=dt_time(hour=6, minute=30, tzinfo=MOSCOW_TZ),
        name="auto_morning"
    )
    schedule_inspiration_job(app)

    logger.info("JobQueue настроен.")


# =========================
# HANDLERS
# =========================

async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if "users" not in context.bot_data:
        context.bot_data["users"] = load_users()

    if user_id not in context.bot_data["users"]:
        context.bot_data["users"].add(user_id)
        save_user(user_id)

    await update.message.reply_text(
        "Привет! Спорт — это не только про форму. Это про внимание, дыхание и выбор быть с собой.\n🧘‍♀️ Начнём?",
        reply_markup=get_main_keyboard()
    )


async def handle_message(update: Update, context: CallbackContext):
    text = (update.message.text or "").strip()
    user_id = update.effective_user.id
    date_str = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")

    if text == "❓ Что было":
        workout = get_daily_workout()
        if workout:
            formatted = format_workout_with_guides(workout)
            await update.message.reply_text(
                f"Сегодняшняя тренировка:\n{formatted}\nУдалось выполнить?",
                reply_markup=get_response_keyboard()
            )
            context.user_data["date"] = date_str
            context.user_data["type"] = "плановая"

    elif text == "📅 Расписание":
        schedule = "📅 Расписание на неделю:"
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        emoji_list = ["🏃‍♂️", "🧑‍🏫", "🏋️‍♀️", "🧘‍♀️", "🤸‍♂️", "🧘‍♂️", "😌"]
        for i in range(7):
            name, _ = WEEKLY_PLAN[i]
            schedule += f"\n{days[i]} — {name} {emoji_list[i]}"
        await update.message.reply_text(schedule, reply_markup=get_main_keyboard())

    elif text == "🏃 Внеплановая":
        workout_groups = get_random_workout()
        workout = random.choice(workout_groups) if workout_groups else []
        formatted = format_workout_with_guides(workout)
        await update.message.reply_text(
            f"Вот твоя внеплановая тренировка:\n{formatted}\nУдалось выполнить?",
            reply_markup=get_response_keyboard()
        )
        context.user_data["date"] = date_str
        context.user_data["type"] = "внеплановая"

    elif text == "🔥 Мотивация":
        phrase = random.choice(inspiration_phrases)
        await update.message.reply_text(f"✨ {phrase}", reply_markup=get_main_keyboard())

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
        await update.message.reply_text("📊 Формирую твой отчёт...")
        try:
            resp = requests.get(GOOGLE_SCRIPT_URL, params={"action": "report", "user_id": user_id}, timeout=10)
            if resp.status_code == 200:
                await update.message.reply_text(resp.text, reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text("❗ Не удалось получить отчёт. Попробуй позже.", reply_markup=get_main_keyboard())
        except Exception as e:
            logger.error(f"Ошибка при получении отчёта: {e}")
            await update.message.reply_text("⚠️ Возникла ошибка при формировании отчёта.", reply_markup=get_main_keyboard())

    elif text == "🫶 Настройся на себя":
        practice = random.choice(MICRO_PRACTICES)
        await update.message.reply_text(
            f"Попробуй прямо сейчас:\n\n{practice}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📍 Я здесь", callback_data="support_done")],
                [InlineKeyboardButton("👣 Ещё один шаг к себе", callback_data="more_practice")]
            ])
        )


async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    date_str = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")

    if query.data.startswith("response_"):
        response = query.data.replace("response_", "")

        # 1) пробуем взять тип из user_data (для сообщений внутри диалога)
        workout_type = context.user_data.get("type")
        used_date = context.user_data.get("date", date_str)

        # 2) если это утреннее авто-сообщение — берём из bot_data по ключу (user_id, date)
        if not workout_type:
            workout_type = context.bot_data.get("last_workout_meta", {}).get((user_id, date_str), "неизвестно")
            used_date = date_str

        send_to_gsheet(user_id, used_date, workout_type, response)

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
        await query.edit_message_text(phrase)

    elif query.data == "more_practice":
        new_practice = random.choice(MICRO_PRACTICES)
        await query.edit_message_text(
            f"Попробуй ещё одну микропрактику:\n\n{new_practice}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📍 Я здесь", callback_data="support_done")],
                [InlineKeyboardButton("👣 Ещё", callback_data="more_practice")]
            ])
        )


async def show_users(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ У тебя нет доступа к этому списку.")
        return

    users = load_users()
    if not users:
        await update.message.reply_text("📭 Пока что список пользователей пуст.")
    else:
        await update.message.reply_text("👥 Пользователи:\n" + "\n".join(map(str, sorted(users))))


# =========================
# BUILD APP (для webhook через app.py)
# =========================

def build_application() -> Application:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in environment variables")

    application = (
        Application.builder()
        .token(token)
        .post_init(setup_jobqueue)
        .build()
    )

    application.bot_data["users"] = load_users()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("users", show_users))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    return application

