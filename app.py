import os
import asyncio
import logging
import threading
from typing import Optional

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

tg_app: Optional[Application] = None
loop: Optional[asyncio.AbstractEventLoop] = None
loop_ready = threading.Event()


@app.get("/")
def health():
    return "ok", 200


@app.post(WEBHOOK_PATH)
def webhook():
    global tg_app, loop

    if tg_app is None or loop is None:
        logger.warning("WEBHOOK: not ready yet")
        return "not ready", 503

    data = request.get_json(force=True, silent=True) or {}
    logger.info(f"WEBHOOK IN: keys={list(data.keys())}")

    try:
        update = Update.de_json(data, tg_app.bot)

        fut = asyncio.run_coroutine_threadsafe(tg_app.process_update(update), loop)

        # Ловим любые исключения из обработки апдейта (иначе “молчит” без следов)
        def _done_callback(f):
            exc = f.exception()
            if exc:
                logger.exception("process_update failed", exc_info=exc)

        fut.add_done_callback(_done_callback)

        return "ok", 200

    except Exception as e:
        logger.exception(f"WEBHOOK handler crashed: {e}")
        return "error", 500


def _run_loop_forever():
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop_ready.set()
    loop.run_forever()


def init_bot():
    global tg_app, loop

    # Один event loop в отдельном потоке
    threading.Thread(target=_run_loop_forever, daemon=True).start()
    loop_ready.wait(timeout=15)

    if loop is None:
        raise RuntimeError("Event loop failed to start")

    tg_app = build_application()

    async def _init():
        # Полный жизненный цикл PTB
        await tg_app.initialize()

        # На всякий случай чистим старый вебхук и зависшие апдейты
        await tg_app.bot.delete_webhook(drop_pending_updates=True)
        await tg_app.bot.set_webhook(url=WEBHOOK_URL)

        await tg_app.start()
        logger.info(f"Webhook set to {WEBHOOK_URL}")

    fut = asyncio.run_coroutine_threadsafe(_init(), loop)

    # Если тут ошибка — лучше упасть при старте, чем “тихо молчать”
    fut.result(timeout=30)


# Инициализация при импорте модуля gunicorn
init_bot()
