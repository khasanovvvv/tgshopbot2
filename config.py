# config.py
import os

# Token va ID avval "Environment Variable" (masalan Railway Variables) dan olinadi.
# Agar topilmasa, quyidagi standart qiymatlar ishlatiladi (lokal sinov uchun).
# RAILWAYDA BU YERGA HAQIQIY TOKEN YOZMANG — Variables bo'limidan kiriting.

BOT_TOKEN = os.getenv("BOT_TOKEN", "123456789:AAExampleTokenHereReplaceMe")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

# Ma'lumotlar bazasi fayli nomi (o'zgartirish shart emas)
DB_NAME = "shop.db"
