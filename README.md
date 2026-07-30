# Telegram Shop Bot — Yo'riqnoma

## 1) Bot qanday ishlaydi

- `/start` — asosiy menyu chiqadi: 🛍 Xizmatlar, 👨‍💻 Admin bilan aloqa, 📢 Biz kanali
- **Xizmatlar** bosilsa — kategoriyalar ro'yxati chiqadi (masalan "Telegram Premium")
- Kategoriya bosilsa — ichidagi xizmatlar chiqadi (1 oylik, 3 oylik va h.k.) narxi bilan
- Xizmat bosilsa — narx va izoh ko'rsatiladi + "✅ Buyurtma berish" tugmasi
- "Buyurtma berish" bosilsa — **sizga (adminga) xabar keladi**: kim, qaysi xizmatni tanlagani

Kategoriya va xizmatlarni, narxlarni **/admin** buyrug'i orqali o'zingiz qo'shasiz, o'chirasiz, narxini o'zgartirasiz — kodga tegmasdan.

## 2) Botni sozlash (o'zingizga moslash)

1. Telegramda **@BotFather** ga boring, `/newbot` yuboring, bot yarating — sizga TOKEN beradi.
2. **@userinfobot** ga `/start` yozing — u sizning Telegram ID raqamingizni beradi.
3. `config.py` faylini oching va quyidagilarni almashtiring:
   ```python
   BOT_TOKEN = "sizning_tokeningiz"
   ADMIN_ID = 123456789  # sizning ID raqamingiz
   ```

## 3) Kompyuterda / VPS'da sinab ko'rish

```bash
pip install -r requirements.txt
python3 bot.py
```

Telegramda botingizga `/start`, keyin `/admin` yozib ko'ring — admin panel ochiladi.

**Admin panelda birinchi marta:**
1. "➕ Kategoriya qo'shish" — masalan "Telegram Premium" deb yozing
2. "📂 Kategoriyalarni boshqarish" → yaratgan kategoriyangizni tanlang → "➕ Xizmat qo'shish"
3. Nomini yozing (masalan "Telegram Premium 1 oylik"), narxini yozing (masalan 50000), izoh yozing yoki "-" qo'ying
4. Shu tariqa 3 oylik, 6 oylik, 12 oylikni ham qo'shasiz — istagancha kategoriya va xizmat qo'sha olasiz

Sozlamalar bo'limidan admin username va kanal linkini ham o'zgartira olasiz.

## 4) 24/7 ishlashi uchun — tekin serverga joylash

Kompyuteringiz o'chsa yoki Termux yopilsa, bot to'xtaydi. Doim ishlab turishi uchun serverga joylash kerak. Eng mos tekin variantlar:

### A) Railway.app — eng oson (yangi boshlovchilar uchun)
1. https://railway.app ga GitHub orqali ro'yxatdan o'ting
2. Loyihani GitHub'ga yuklang (yoki Railway CLI orqali to'g'ridan-to'g'ri joylang)
3. Railway'da "New Project" → "Deploy from GitHub repo" tanlang
4. `BOT_TOKEN` va `ADMIN_ID`ni **Environment Variables** orqali kiritish tavsiya etiladi (config.py'ga yozib qo'ymasdan) — xavfsizroq
5. Har oy bepul limit beriladi (kichik botlar uchun odatda yetadi)

### B) Fly.io — ham tekin limit bor, biroz texnik bilim talab qiladi
- `fly.io` da hisob oching, `flyctl` o'rnatib, `fly launch` orqali joylaysiz. Doimiy ishlaydigan kichik instance tekin.

### C) Oracle Cloud Free Tier — **butunlay bepul, doimiy (VPS)**
- Eng barqaror va cheksiz bepul variant, lekin Linux serverni sozlashni bilish kerak (SSH, systemd orqali botni doim ishlab turishini ta'minlash).
- Agar buni birga sozlashimni xohlasangiz, ayting — qadam-baqadam ko'rsataman.

### D) PythonAnywhere
- Tekin tarifda bot doimiy ishlashi cheklangan (har kuni qayta ishga tushirish talab qilinishi mumkin), shuning uchun uzoq muddatli loyiha uchun unchalik mos emas.

**Tavsiyam:** boshlash uchun **Railway** eng qulay — GitHub'ga joylab, bir necha click bilan ishga tushasiz. Agar botingiz katta bo'lib, doimiy va cheksiz bepul kerak bo'lsa — **Oracle Cloud Free Tier**ga o'tasiz.

Qaysi birini tanlashni xohlaysiz — men sizga o'sha serverga aynan qadam-baqadam joylashda yordam beraman (GitHub'ga yuklashdan tortib, serverda ishga tushirishgacha).
