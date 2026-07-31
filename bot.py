# bot.py
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")


# ---------- Render kabi platformalar uchun kichik "health check" server ----------
# Render Web Service portni "tinglab turishni" talab qiladi, aks holda u
# xizmatni "ishlamayapti" deb hisoblab, konteynerni qayta ishga tushiraveradi.
# Shu sabab bu serverni BOSHQA HAMMA IMPORTLARDAN OLDIN, darhol ishga tushiramiz.
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot ishlab turibdi.")

    def do_HEAD(self):
        # UptimeRobot va boshqa monitoring xizmatlari ko'pincha HEAD so'rovi
        # yuboradi (GET emas) - shuni ham qo'llab-quvvatlashimiz kerak,
        # aks holda ular xato ravishda "bot ishlamayapti" deb hisoblaydi.
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # konsolni keraksiz loglar bilan to'ldirmaslik uchun


def _run_health_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), _HealthHandler)
        log.info(f"Health-check server {port}-portda ishga tushdi.")
        server.serve_forever()
    except Exception as e:
        log.error(f"Health-check server ishga tushmadi: {e}")


# Health-server DARHOL, aiogram va boshqa og'ir kutubxonalar yuklanishidan
# oldin ishga tushadi — shunda Render port ochilganini tezroq ko'radi.
threading.Thread(target=_run_health_server, daemon=True).start()


# ---------- Endi qolgan (og'irroq) importlar ----------
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
import database as db
import handlers_user
import handlers_admin


async def main():
    db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # admin handlerlar user handlerlardan OLDIN ro'yxatdan o'tishi kerak,
    # aks holda callback_data mos kelib qolishi mumkin
    dp.include_router(handlers_admin.router)
    dp.include_router(handlers_user.router)

    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Bot polling boshlandi.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
