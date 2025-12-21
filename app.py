import os
import asyncio
import logging
from flask import Flask, request

from telegram import Update
from telegram.ext import Application

# импортируем твой код (в main.py должны быть: build_application() )
# Я ниже покажу, как поправить main.py, чтобы это работало.
from main import build_application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render сам задаёт
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{PUBLIC_URL}{WEBHOOK_PATH}"

app = Flask(__name__)

tg_app: Application | None = None


@app.get("/")
def health():
    return "ok", 200


@app.post(WEBHOOK_PATH)
def webhook():
    global tg_app
    if tg_app is None:
        return "not ready", 503

    update_json = request.get_json(force=True)
    update = Update.de_json(update_json, tg_app.bot)

    # пробрасываем апдейт в PTB
    asyncio.run(tg_app.process_update(update))
    return "ok", 200


def init():
    global tg_app
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    tg_app = build_application()

    # Важно: инициализируем и ставим webhook
    asyncio.run(tg_app.initialize())
    asyncio.run(tg_app.bot.set_webhook(url=WEBHOOK_URL))
    asyncio.run(tg_app.start())
    logger.info(f"Webhook set to: {WEBHOOK_URL}")


init()
