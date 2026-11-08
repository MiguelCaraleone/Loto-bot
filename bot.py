import asyncio
import io
import os
import random
import secrets
import qrcode
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import aiosqlite

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ==================== SOZLAMALAR ====================
# Railway Environment Variables'dan o'qiydi yoki o'zingiz yozgan qiymatni oladi:
BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKENINGIZNI_YOZING")
BOT_USERNAME = os.getenv("BOT_USERNAME", "SizningBotingiz_bot")
BOSH_ADMIN_ID = int(os.getenv("BOSH_ADMIN_ID", "123456789"))

DB_NAME = "chegirmalar.db"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== KATTA SAVOLLAR BAZASI ====================
# Har gal ushbu bazadan 3 tasi tasodifiy tanlanadi va variantlari aralashtiriladi
SAVOLLAR_BANKI = {
    "tarix": [
        {"savol": "Amir Temur qachon tavallud topgan?", "variantlar": ["1336-yil", "1340-yil", "1370-yil"], "javob": "1336-yil"},
        {"savol": "Jaloliddin Manguberdi qaysi davlat sarkardasi bo‘lgan?", "variantlar": ["Xorazmshohlar", "Somoniylar", "Temuriylar"], "javob": "Xorazmshohlar"},
        {"savol": "Mirzo Ulug‘bek rasadxonasi qaysi shaharda barpo etilgan?", "variantlar": ["Samarqand", "Buxoro", "Xiva"], "javob": "Samarqand"},
        {"savol": "Alisher Navoiy qaysi asrda yashab ijod qilgan?", "variantlar": ["XV asr", "XIV asr", "XVI asr"], "javob": "XV asr"},
        {"savol": "Zahiriddin Muhammad Bobur qaysi sulolaga asos solgan?", "variantlar": ["Boburiylar", "Shayboniylar", "G‘aznaviylar"], "javob": "Boburiylar"},
        {"savol": "Buyuk Ipak yo‘li qaysi qit’alarni bog‘lagan?", "variantlar": ["Osiyo va Yevropa", "Afrika va Osiyo", "Amerika va Yevropa"], "javob": "Osiyo va Yevropa"},
        {"savol": "Abu Ali ibn Sino qaysi soha rivojiga ulkan hissa qo‘shgan?", "variantlar": ["Tibbiyot", "Geografiya", "Astronomiya"], "javob": "Tibbiyot"}
    ],
    "matematika": [
        {"savol": "2 + 2 * 2 amalini hisoblang:", "variantlar": ["6", "8", "4"], "javob": "6"},
        {"savol": "Tomoni 6 sm ga teng kvadratning yuzini toping:", "variantlar": ["36 sm²", "24 sm²", "12 sm²"], "javob": "36 sm²"},
        {"savol": "100 sonining 5 foizi nechaga teng?", "variantlar": ["5", "10", "50"], "javob": "5"},
        {"savol": "Bir kunda necha soat bor?", "variantlar": ["24 soat", "12 soat", "48 soat"], "javob": "24 soat"},
        {"savol": "Eng kichik tub son qaysi?", "variantlar": ["2", "1", "3"], "javob": "2"},
        {"savol": "To‘g‘ri to‘rtburchakning nechta burchagi bor?", "variantlar": ["4 ta", "3 ta", "6 ta"], "javob": "4 ta"},
        {"savol": "50 sonining yarmi nechchi bo‘ladi?", "variantlar": ["25", "20", "15"], "javob": "25"}
    ]
}

# ==================== FSM HOLATLARI ====================
class TestHolati(StatesGroup):
    fan_tanlash = State()
    test_yechish = State()

# ==================== ASINXRON BAZA AMALLARI (aiosqlite) ====================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS vaucherlar (
                kod TEXT PRIMARY KEY,
                user_id INTEGER,
                foiz INTEGER,
                status TEXT DEFAULT 'faol',
                berilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ishlatilgan_vaqt TIMESTAMP NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kassirlar (
                user_id INTEGER PRIMARY KEY,
                ism TEXT,
                qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS takliflar (
                token TEXT PRIMARY KEY,
                status TEXT DEFAULT 'faol'
            )
        """)
        await db.commit()

async def is_kassir(user_id: int) -> bool:
    if user_id == BOSH_ADMIN_ID:
        return True
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM kassirlar WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            return res is not None

async def kod_saqlash(kod: str, user_id: int, foiz: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO vaucherlar (kod, user_id, foiz, status) VALUES (?, ?, ?, 'faol')",
            (kod, user_id, foiz)
        )
        await db.commit()

async def kodni_tekshirish(kod: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT foiz, status, ishlatilgan_vaqt FROM vaucherlar WHERE kod = ?", (kod,)) as cursor:
            natija = await cursor.fetchone()

        if not natija:
            return "topilmadi", None

        foiz, status, vaqt = natija
        if status == "ishlatildi":
            return "oldin_ishlatilgan", vaqt

        await db.execute(
            "UPDATE vaucherlar SET status = 'ishlatildi', ishlatilgan_vaqt = CURRENT_TIMESTAMP WHERE kod = ?",
            (kod,)
        )
        await db.commit()
        return "tasdiqlandi", foiz

async def hisobot_olish():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM vaucherlar") as c:
            jami_berilgan = (await c.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM vaucherlar WHERE status = 'faol'") as c:
            hali_ishlatilmagan = (await c.fetchone())[0]

        async with db.execute("""
            SELECT COUNT(*), 
                   COALESCE(SUM(CASE WHEN foiz = 5 THEN 1 ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN foiz = 3 THEN 1 ELSE 0 END), 0)
            FROM vaucherlar 
            WHERE status = 'ishlatildi' 
              AND date(ishlatilgan_vaqt, 'localtime') = date('now', 'localtime')
        """) as c:
            bugun_jami, bugun_5, bugun_3 = await c.fetchone()

        async with db.execute("""
            SELECT COUNT(*), 
                   COALESCE(SUM(CASE WHEN foiz = 5 THEN 1 ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN foiz = 3 THEN 1 ELSE 0 END), 0)
            FROM vaucherlar 
            WHERE status = 'ishlatildi' 
              AND date(ishlatilgan_vaqt, 'localtime') >= date('now', 'localtime', '-7 days')
        """) as c:
            hafta_jami, hafta_5, hafta_3 = await c.fetchone()

    return {
        "jami_berilgan": jami_berilgan,
        "hali_ishlatilmagan": hali_ishlatilmagan,
        "bugun_jami": bugun_jami,
        "bugun_5": bugun_5,
        "bugun_3": bugun_3,
        "hafta_jami": hafta_jami,
        "hafta_5": hafta_5,
        "hafta_3": hafta_3,
    }

# ==================== YORDAMCHI VIZUALLAR (QR VA EXCEL) ====================
def qr_kod_yaratish(havola: str) -> BufferedInputFile:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(havola)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return BufferedInputFile(buffer.getvalue(), filename="vaucher.png")

async def generate_excel_report() -> io.BytesIO:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT kod, user_id, foiz, status, berilgan_vaqt, ishlatilgan_vaqt 
            FROM vaucherlar 
            ORDER BY berilgan_vaqt DESC
        """) as cursor:
            rows = await cursor.fetchall()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Vaucherlar hisoboti"

    headers = ["Vaucher Kodi", "Telegram User ID", "Chegirma (%)", "Holati", "Berilgan Vaqti", "Ishlatilgan Vaqti"]
    ws.append(headers)

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    center_align = Alignment(horizontal="center", vertical="center")

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    for row_data in rows:
        kod, user_id, foiz, status, berilgan, ishlatilgan = row_data
        status_text = "Ishlatilgan" if status == "ishlatildi" else "Faol"
        ws.append([kod, user_id, f"{foiz}%", status_text, berilgan, ishlatilgan if ishlatilgan else "—"])

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 4, 15)
        for cell in col:
            cell.alignment = center_align

    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream

# ==================== TUGMALAR ====================
def fanlar_klaviaturasi():
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Tarix", callback_data="fan:tarix")
    builder.button(text="📐 Matematika", callback_data="fan:matematika")
    builder.adjust(2)
    return builder.as_markup()

def savol_klaviaturasi(variantlar: list):
    builder = InlineKeyboardBuilder()
    for variant in variantlar:
        builder.button(text=variant, callback_data=f"javob:{variant}")
    builder.adjust(1)
    return builder.as_markup()

# ==================== HANDLERLAR ====================
@dp.message(CommandStart())
async def start_buyrugi(message: types.Message, command: CommandObject, state: FSMContext):
    await state.clear()
    args = command.args

    # 1. KASSIR QR-KODNI TEKSHIRGANDA:
    if args and args.startswith("CH_"):
        if not await is_kassir(message.from_user.id):
            await message.answer("⚠️ Bu QR-kod faqat do‘kon kassiri tomonidan skanerlanishi mumkin!")
            return

        holat, qiymat = await kodni_tekshirish(args)
        if holat == "tasdiqlandi":
            await message.answer(
                f"✅ <b>CHEGIRMA TASDIQLANDI!</b>\n\n"
                f"🎟 Kod: <code>{args}</code>\n"
                f"🎁 Chegirma: <b>{qiymat}%</b>\n"
                f"🔒 Holat: Kod bazada yopildi (bir martalik).",
                parse_mode="HTML"
            )
        elif holat == "oldin_ishlatilgan":
            await message.answer(
                f"❌ <b>BU KOD OLDIN ISHLATILGAN!</b>\n\n"
                f"🎟 Kod: <code>{args}</code>\n"
                f"🕒 Ishlatilgan vaqt: {qiymat}\n"
                f"⛔️ Chegirma berilmaydi!",
                parse_mode="HTML"
            )
        else:
            await message.answer("🚫 Bunday chegirma kodi topilmadi.")
        return

    # 2. KASSIR TAKLIF HAVOLASINI BOSGANDA:
    if args and args.startswith("kassir_"):
        token = args.replace("kassir_", "")
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT status FROM takliflar WHERE token = ?", (token,)) as cursor:
                res = await cursor.fetchone()

            if res and res[0] == "faol":
                await db.execute("UPDATE takliflar SET status = 'ishlatildi' WHERE token = ?", (token,))
                await db.execute(
                    "INSERT OR REPLACE INTO kassirlar (user_id, ism) VALUES (?, ?)",
                    (message.from_user.id, message.from_user.full_name)
                )
                await db.commit()

                await message.answer("🎉 <b>Tabriklaymiz! Siz kassir sifatida ulandingiz.</b>\nEndi xaridorlar QR-kodini tekshirishingiz mumkin.", parse_mode="HTML")
                await bot.send_message(
                    chat_id=BOSH_ADMIN_ID,
                    text=f"🔔 <b>Yangi kassir qo‘shildi:</b> {message.from_user.full_name} (ID: <code>{message.from_user.id}</code>)",
                    parse_mode="HTML"
                )
                return
            else:
                await message.answer("❌ Ushbu taklif havolasi eskirgan yoki ishlatilgan!")
                return

    # 3. ODDIY FOYDALANUVCHIGA TEST BOSHLANISHI:
    await message.answer(
        "👋 <b>Do‘konimiz viktorinasiga xush kelibsiz!</b>\n\n"
        "3 ta savoldan iborat qiziqarli testni yeching va chegirmaga ega bo‘ling:\n"
        "• 3 ta to‘g‘ri javob ➡️ <b>5% chegirma</b>\n"
        "• 2 ta to‘g‘ri javob ➡️ <b>3% chegirma</b>\n\n"
        "Boshlash uchun fanni tanlang:",
        reply_markup=fanlar_klaviaturasi(),
        parse_mode="HTML"
    )
    await state.set_state(TestHolati.fan_tanlash)

# ==================== TESTNI TASODIFIY TANLASH VA O'TKAZISH ====================
@dp.callback_query(F.data.startswith("fan:"))
async def fan_tanlandi(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    fan_nomi = callback.data.split(":")[1]

    if fan_nomi not in SAVOLLAR_BANKI:
        return

    # Savollar bankidan 3 ta tasodifiy savolni tanlab olamiz:
    tanlangan_savollar = random.sample(SAVOLLAR_BANKI[fan_nomi], 3)
    
    # Har bir savolning variantlarini ham aralashtirib chiqamiz:
    tayyor_savollar = []
    for s in tanlangan_savollar:
        variantlar = list(s["variantlar"])
        random.shuffle(variantlar)
        tayyor_savollar.append({
            "savol": s["savol"],
            "variantlar": variantlar,
            "javob": s["javob"]
        })

    # Foydalanuvchining shaxsiy FSM xotirasiga unikal savollarini saqlaymiz:
    await state.update_data(
        fan=fan_nomi, 
        savollar=tayyor_savollar, 
        savol_indeksi=0, 
        togri_javoblar=0
    )
    await state.set_state(TestHolati.test_yechish)

    birinchi_savol = tayyor_savollar[0]
    await callback.message.edit_text(
        text=f"📌 <b>{fan_nomi.capitalize()} fani</b> (1/3)\n\n{birinchi_savol['savol']}",
        reply_markup=savol_klaviaturasi(birinchi_savol["variantlar"]),
        parse_mode="HTML"
    )

@dp.callback_query(TestHolati.test_yechish, F.data.startswith("javob:"))
async def javob_tekshirish(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    foydalanuvchi_javobi = callback.data.replace("javob:", "")

    data = await state.get_data()
    fan = data.get("fan")
    savollar = data.get("savollar", [])
    indeks = data.get("savol_indeksi", 0)
    togri_soni = data.get("togri_javoblar", 0)

    # To'g'riligini tekshirish
    if foydalanuvchi_javobi == savollar[indeks]["javob"]:
        togri_soni += 1

    keyingi_indeks = indeks + 1

    if keyingi_indeks < len(savollar):
        await state.update_data(savol_indeksi=keyingi_indeks, togri_javoblar=togri_soni)
        keyingi_savol = savollar[keyingi_indeks]
        await callback.message.edit_text(
            text=f"📌 <b>{fan.capitalize()} fani</b> ({keyingi_indeks + 1}/3)\n\n{keyingi_savol['savol']}",
            reply_markup=savol_klaviaturasi(keyingi_savol["variantlar"]),
            parse_mode="HTML"
        )
    else:
        # TEST TUGADI
        await state.clear()
        user_id = callback.from_user.id

        if togri_soni >= 2:
            foiz = 5 if togri_soni == 3 else 3
            unikal_kod = f"CH_{foiz}_{user_id}_{random.randint(1000, 9999)}"
            await kod_saqlash(unikal_kod, user_id, foiz)

            skaner_havolasi = f"https://t.me/{BOT_USERNAME}?start={unikal_kod}"
            qr_rasm = qr_kod_yaratish(skaner_havolasi)

            await callback.message.delete()
            await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=qr_rasm,
                caption=(
                    f"🎉 <b>Tabriklaymiz! Siz {togri_soni} ta savolga to‘g‘ri javob berdingiz!</b>\n\n"
                    f"Sizga barcha mahsulotlar uchun <b>{foiz}% lik chegirma</b> berildi.\n\n"
                    f"💰 <b>Xarid namunalari:</b>\n"
                    f"• 10 000 so‘mlik xarid ➡️ <b>{10000 - (10000 * foiz // 100)} so‘m</b>\n"
                    f"• 40 000 so‘mlik xarid ➡️ <b>{40000 - (40000 * foiz // 100)} so‘m</b>\n\n"
                    f"📲 Do‘konda to‘lov paytida ushbu <b>QR-kodni</b> kassirga ko‘rsating!\n"
                    f"<i>(Vaucher faqat 1 marta ishlatiladi)</i>"
                ),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"Siz {togri_soni} ta to‘g‘ri javob berdingiz.\n"
                f"Chegirmaga ega bo‘lish uchun kamida 2 ta savolga to‘g‘ri javob berish kerak edi.\n\n"
                f"Qaytadan urinib ko‘ring: /start"
            )

# ==================== ADMIN VA KASSIR BUYRUQLARI ====================
@dp.message(Command("yangi_kassir"))
async def kassir_taklif_linki(message: types.Message):
    if message.from_user.id != BOSH_ADMIN_ID:
        return

    token = secrets.token_hex(8)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO takliflar (token) VALUES (?)", (token,))
        await db.commit()

    havola = f"https://t.me/{BOT_USERNAME}?start=kassir_{token}"
    await message.answer(
        f"🔗 <b>Kassir uchun bir martalik taklif havolasi:</b>\n\n"
        f"<code>{havola}</code>\n\n"
        f"Ushbu havolani kassiringizga yuboring. U bosib <b>Start</b> tugmasini bosishi bilan kassirga aylanadi.",
        parse_mode="HTML"
    )

@dp.message(Command("kassirlar"))
async def kassirlar_royxati(message: types.Message):
    if message.from_user.id != BOSH_ADMIN_ID:
        return

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, ism, qoshilgan_vaqt FROM kassirlar") as cursor:
            kassirlar = await cursor.fetchall()

    if not kassirlar:
        await message.answer("Hozircha birorta ham kassir ulanmagan.")
        return

    matn = "📋 <b>Ulangan kassirlar ro‘yxati:</b>\n\n"
    for kid, ism, vaqt in kassirlar:
        matn += f"• <b>{ism}</b> (ID: <code>{kid}</code>) — {vaqt}\n"
    await message.answer(matn, parse_mode="HTML")

@dp.message(Command("statistika"))
async def statistika_handler(message: types.Message):
    if not await is_kassir(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat kassirlar va admin uchun!")
        return

    stat = await hisobot_olish()
    matn = (
        "📊 <b>DO‘KON CHEGIRMALAR STATISTIKASI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📅 <b>BUGUNGI NATIJA:</b>\n"
        f"• Ishlatilgan chegirmalar: <b>{stat['bugun_jami']} ta</b>\n"
        f"  └ 5% lik: <b>{stat['bugun_5']} ta</b>\n"
        f"  └ 3% lik: <b>{stat['bugun_3']} ta</b>\n\n"
        "🗓 <b>OXIRGI 7 KUN (HAFTALIK):</b>\n"
        f"• Ishlatilgan chegirmalar: <b>{stat['hafta_jami']} ta</b>\n"
        f"  └ 5% lik: <b>{stat['hafta_5']} ta</b>\n"
        f"  └ 3% lik: <b>{stat['hafta_3']} ta</b>\n\n"
        "📦 <b>UMUMIY BAZA:</b>\n"
        f"• Berilgan jami vaucherlar: <b>{stat['jami_berilgan']} ta</b>\n"
        f"• Ishlatilishi kutilayotganlar: <b>{stat['hali_ishlatilmagan']} ta</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(matn, parse_mode="HTML")

@dp.message(Command("excel"))
async def excel_handler(message: types.Message):
    if not await is_kassir(message.from_user.id):
        await message.answer("❌ Bu buyruq faqat kassirlar va admin uchun!")
        return

    await message.answer("⏳ Excel hisobot tayyorlanmoqda...")
    stream = await generate_excel_report()
    fayl = BufferedInputFile(file=stream.getvalue(), filename="vaucherlar_hisoboti.xlsx")
    await message.answer_document(
        document=fayl,
        caption="📊 <b>Barcha vaucherlar bazasi Excel formatida tayyor.</b>"
    )

# ==================== HAR KUNI SOAT 21:00 DA AVTO-HISOBOT ====================
async def kunlik_avto_hisobot():
    stat = await hisobot_olish()
    xabar = (
        "📢 <b>KUNLIK YAKUNIY HISOBOT (21:00)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 Bugun do‘konda <b>{stat['bugun_jami']} ta</b> chegirma ishlatildi:\n"
        f"• 5% lik: <b>{stat['bugun_5']} ta</b>\n"
        f"• 3% lik: <b>{stat['bugun_3']} ta</b>\n\n"
        f"Hali xarid qilinmagan faol vaucherlar: <b>{stat['hali_ishlatilmagan']} ta</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        await bot.send_message(chat_id=BOSH_ADMIN_ID, text=xabar, parse_mode="HTML")
    except Exception as e:
        print(f"Hisobot yuborishda xatolik: {e}")

# ==================== ISHGA TUSHIRISH ====================
async def main():
    await init_db()

    # Soat 21:00 uchun rejalashtiruvchi
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(
        kunlik_avto_hisobot,
        trigger=CronTrigger(hour=21, minute=0, timezone="Asia/Tashkent")
    )
    scheduler.start()

    print("Bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
