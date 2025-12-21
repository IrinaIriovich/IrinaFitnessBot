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
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render выставляет сам

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


@app.post(WEBHOOK_PATH)
def webhook():
    global tg_app, loop

    if tg_app is None or loop is None:
        logger.warning("Webhook received but bot/loop not ready yet")
        return "not ready", 503

    data = request.get_json(force=True, silent=True)
    if not data:
        logger.warning("Empty JSON received on webhook")
        return "bad request", 400

    try:
        update = Update.de_json(data, tg_app.bot)
    except Exception:
        logger.exception("Failed to parse Update from JSON")
        return "bad update", 400

    fut = asyncio.run_coroutine_threadsafe(_process_update_safe(update), loop)
    # можно не ждать результата, но полезно логировать, если упадёт
    def _done_callback(f):
        try:
            f.result()
        except Exception:
            logger.exception("process_update crashed")
    fut.add_done_callback(_done_callback)

    return "ok", 200


async def _process_update_safe(update: Update):
    """Оборачиваем обработку апдейта, чтобы видеть исключения."""
    assert tg_app is not None
    try:
        await tg_app.process_update(update)
    except Exception:
        logger.exception("Exception while processing update")


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
        # 1) init PTB
        await tg_app.initialize()

        # 2) сбросить старый вебхук и очередь (важно при “переездах”)
        await tg_app.bot.delete_webhook(drop_pending_updates=True)

        # 3) поставить новый вебхук
        ok = await tg_app.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}, ok={ok}")

        # 4) старт приложения
        await tg_app.start()

    asyncio.run_coroutine_threadsafe(_init(), loop)


# Gunicorn import-time init
init_bot()
