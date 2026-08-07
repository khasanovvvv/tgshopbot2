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

from config import BOT_TOKEN, ADMIN_BOT_TOKEN
import database as db
import handlers_user
import handlers_admin
import admin_bot


async def run_customer_bot(include_admin_router: bool):
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Agar alohida admin bot ishlamasa, /admin shu botning o'zida ham ishlaydi
    # (zaxira variant sifatida). Aks holda admin faqat maxsus botdan boshqaradi.
    if include_admin_router:
        dp.include_router(handlers_admin.router)
    dp.include_router(handlers_user.router)

    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Mijozlar boti (asosiy bot) polling boshlandi.")
    await dp.start_polling(bot)


async def run_admin_bot():
    bot = Bot(token=ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_bot.router)
    dp.include_router(handlers_admin.router)

    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Admin boti polling boshlandi.")
    await dp.start_polling(bot)


async def main():
    db.init_db()

    if ADMIN_BOT_TOKEN:
        # Ikkala bot ham ishlaydi: mijozlar boti (admin routerisiz) + alohida admin bot
        await asyncio.gather(run_customer_bot(include_admin_router=False), run_admin_bot())
    else:
        log.info("ADMIN_BOT_TOKEN berilmagan - faqat asosiy bot ishga tushadi (unda /admin ham ishlaydi).")
        await run_customer_bot(include_admin_router=True)


if __name__ == "__main__":
    asyncio.run(main())
