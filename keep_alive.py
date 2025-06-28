from flask import Flask
from threading import Thread
import os  # Не забудь этот импорт!

app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"  # Render проверяет этот эндпоинт

def run():
    port = int(os.environ.get("PORT", 10000))  # Render передаёт PORT через переменные окружения
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
