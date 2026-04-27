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
bot_ready = threading.Event()


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

    async def _process():
        try:
            update = await Update.de_json(data, tg_app.bot)
            logger.info("Update parsed OK")
            await tg_app.process_update(update)
            logger.info("Update processed OK")
        except Exception:
            logger.exception("Error inside _process")

    asyncio.run_coroutine_threadsafe(_process(), loop)

    return "ok", 200


async def _run_bot():
    global tg_app
    tg_app = build_application()
    await tg_app.initialize()
    await tg_app.bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    await tg_app.start()
    logger.info(f"Webhook set to {WEBHOOK_URL}")
    bot_ready.set()
    # держим цикл живым
    await asyncio.Event().wait()


def _run_loop_forever():
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop_ready.set()
    loop.run_until_complete(_run_bot())


def init_bot():
    threading.Thread(target=_run_loop_forever, daemon=True).start()
    loop_ready.wait(timeout=10)
    bot_ready.wait(timeout=30)

    if tg_app is None:
        raise RuntimeError("Bot failed to initialize")

    logger.info("Bot fully initialized")


# Инициализация при старте gunicorn
init_bot()
