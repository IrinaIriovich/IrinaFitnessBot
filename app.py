import os
import asyncio
import logging
import threading
from flask import Flask, request

from telegram import Update
from telegram.ext import Application

from main import build_application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not PUBLIC_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL is not set")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{PUBLIC_URL}{WEBHOOK_PATH}"

app = Flask(__name__)

tg_app: Application | None = None
loop: asyncio.AbstractEventLoop | None = None


@app.get("/")
def health():
    return "ok", 200


@app.post(WEBHOOK_PATH)
def webhook():
    if tg_app is None or loop is None:
        return "not ready", 503

    data = request.get_json(force=True, silent=True) or {}
    update = Update.de_json(data, tg_app.bot)

    asyncio.run_coroutine_threadsafe(
        tg_app.process_update(update),
        loop
    )
    return "ok", 200


def start_loop():
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()


def init_bot():
    global tg_app

    thread = threading.Thread(target=start_loop, daemon=True)
    thread.start()

    while loop is None:
        pass

    tg_app = build_application()

    async def _init():
        await tg_app.initialize()
        await tg_app.bot.set_webhook(WEBHOOK_URL)
        await tg_app.start()
        logger.info(f"Webhook set to {WEBHOOK_URL}")

    asyncio.run_coroutine_threadsafe(_init(), loop)


# Инициализация при старте gunicorn
init_bot()
