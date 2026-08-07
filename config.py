# config.py
import os

# Token va ID avval "Environment Variable" (masalan Railway Variables) dan olinadi.
# Agar topilmasa, quyidagi standart qiymatlar ishlatiladi (lokal sinov uchun).
# RAILWAYDA BU YERGA HAQIQIY TOKEN YOZMANG — Variables bo'limidan kiriting.

BOT_TOKEN = os.getenv("BOT_TOKEN", "123456789:AAExampleTokenHereReplaceMe")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

# Faqat admin uchun alohida bot (yangi @BotFather'dan olingan token)
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")

# 1xpanel (SMM/nakrutka xizmatlari) API - Render'ning Environment Variables
# bo'limidan kiritiladi, GitHub'ga hech qachon yozilmaydi.
SMM_API_KEY = os.getenv("SMM_API_KEY", "")
SMM_API_URL = os.getenv("SMM_API_URL", "https://1xpanel.com/api/v2")

# Ma'lumotlar bazasi fayli nomi (o'zgartirish shart emas)
DB_NAME = "shop.db"
