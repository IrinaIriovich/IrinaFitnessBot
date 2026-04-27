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
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render задаёт сам

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not PUBLIC_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL is not set")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{PUBLIC_URL}{WEBHOOK_PATH}"

app = Flask(__name__)

tg_app: Application | None = None
loop: asyncio.AbstractEventLoop | None = None
loop_ready = threading.Event()


@app.get("/")
def health():
    return "ok", 200


@app.get("/debug-webhook")
def debug_webhook():
    return {
        "webhook_url": WEBHOOK_URL,
        "ready": tg_app is not None and loop is not None,
    }, 200


@app.post(WEBHOOK_PATH)
def webhook():
    global tg_app, loop
    if tg_app is None or loop is None:
        logger.warning("Webhook hit but bot not ready yet")
        return "not ready", 503

    data = request.get_json(force=True, silent=True) or {}
    if not data:
        logger.warning("Webhook hit with empty JSON")
        return "empty", 200

    logger.info(f"Incoming update keys: {list(data.keys())}")

    try:
        update = Update.de_json(data, tg_app.bot)
    except Exception:
        logger.exception("Failed to parse Update.de_json")
        return "bad update", 200

    fut = asyncio.run_coroutine_threadsafe(tg_app.process_update(update), loop)

    def _done_callback(f):
        try:
            f.result()
        except Exception:
            logger.exception("Exception while processing update")

    fut.add_done_callback(_done_callback)

    return "ok", 200


def _run_loop_forever():
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop_ready.set()
    loop.run_forever()


def init_bot():
    global tg_app, loop

    threading.Thread(target=_run_loop_forever, daemon=True).start()
    loop_ready.wait(timeout=10)

    if loop is None:
        raise RuntimeError("Event loop failed to start")

    tg_app = build_application()

    async def _init():
        await tg_app.initialize()
        await tg_app.bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        await tg_app.start()
        logger.info(f"Webhook set to {WEBHOOK_URL}")

    fut = asyncio.run_coroutine_threadsafe(_init(), loop)

    async def _process():
        update = await Update.de_json(data, tg_app.bot)
        await tg_app.process_update(update)

    fut = asyncio.run_coroutine_threadsafe(_process(), loop)


# Инициализация при старте gunicorn
init_bot()
