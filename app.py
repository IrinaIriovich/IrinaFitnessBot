import os
import asyncio
import threading
import logging
from flask import Flask
from main import build_application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.get("/")
def health():
    return "ok", 200


async def run_bot():
    tg_app = build_application()
    async with tg_app:
        await tg_app.updater.start_polling()
        await tg_app.start()
        logger.info("Bot started in polling mode")
        await asyncio.Event().wait()


def start_bot_thread():
    asyncio.run(run_bot())


threading.Thread(target=start_bot_thread, daemon=True).start()
