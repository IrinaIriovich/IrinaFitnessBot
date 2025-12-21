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
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render сам задаёт
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{PUBLIC_URL}{WEBHOOK_PATH}"

app = Flask(__name__)

tg_app: Application | None = None

# отдельный event loop для PTB (чтобы не драться с Flask/gunicorn)
loop: asyncio.AbstractEventLoop | None = None
loop_thread: threading.Thread | None = None


@app.get("/")
def health():
    return "ok", 200


@app.post(WEBHOOK_PATH)
def webhook():
    global tg_app, loop
    if tg_app is None or loop is None:
        return "not ready", 503

    update_json = request.get_json(force=True, silent=True) or {}
    update = Update.de_json(update_json, tg_app.bot)

    # ВАЖНО: не asyncio.run(), а отправка в наш loop
    asyncio.run_coroutine_threadsafe(tg_app.process_update(update), loop)
    return "ok", 200


def _run_loop_forever():
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()


def init():
    global tg_app, loop_thread, loop

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    if not PUBLIC_URL:
        raise RuntimeError("RENDER_EXTERNAL_URL is not set")

    # стартуем loop в отдельном потоке 1 раз
    loop_thread = threading.Thread(target=_run_loop_forever, daemon=True)
    loop_thread.start()

    # ждём пока loop поднимется
    while loop is None:
        pass

    tg_app = build_application()

    async def _async_init():
        await tg_app.initialize()
        await tg_app.bot.set_webhook(url=WEBHOOK_URL)
        await tg_app.start()
        logger.info(f"Webhook set to: {WEBHOOK_URL}")

    asyncio.run_coroutine_threadsafe(_async_init(), loop)


# Важно: делаем init при старте процесса
init()
