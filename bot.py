import os
import json
import random
import sqlite3
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
import google.generativeai as genai

# ==========================================
# 1. SOZLAMALAR (Railway Variables dan o'qiydi)
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO)

# Gemini AI sozlash
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel("gemini-2.5-flash")
else:
    ai_model = None

# ==========================================
# 2. SQLITE BAZA (Eski savollar qayta tushmasligi uchun)
# ==========================================
DB_NAME = "quiz_memory.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS asked_questions (
            user_id INTEGER,
            category TEXT,
            question_text TEXT,
            PRIMARY KEY (user_id, question_text)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            user_id INTEGER PRIMARY KEY,
            correct_count INTEGER DEFAULT 0,
            total_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_user_asked_questions(user_id: int, category: str) -> set:
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT question_text FROM asked_questions WHERE user_id = ? AND category = ?",
        (user_id, category)
    )
    rows = {row[0] for row in cur.fetchall()}
    conn.close()
    return rows

def mark_question_used(user_id: int, category: str, question_text: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO asked_questions (user_id, category, question_text) VALUES (?, ?, ?)",
        (user_id, category, question_text)
    )
    conn.commit()
    conn.close()

def update_score(user_id: int, is_correct: bool):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO scores (user_id, correct_count, total_count) VALUES (?, 0, 0)", (user_id,))
    if is_correct:
        cur.execute("UPDATE scores SET correct_count = correct_count + 1, total_count = total_count + 1 WHERE user_id = ?", (user_id,))
    else:
        cur.execute("UPDATE scores SET total_count = total_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_score(user_id: int) -> tuple:
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT correct_count, total_count FROM scores WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row if row else (0, 0)

# ==========================================
# 3. ZAXIRA SAVOLLAR BAZASI
# ==========================================
STATIC_QUESTIONS = {
    "bolalar": [
        {"fan": "Ona tili (5-sinf)", "savol": "Qaysi qatorda faqat ot so'z turkumiga oid so'zlar berilgan?", "variantlar": ["Kitob, maktab, daftar", "Chiroyli, katta, qizil", "O'qimoq, yozmoq, bormoq", "Tez, sekin, ko'p"], "javob": "Kitob, maktab, daftar"},
        {"fan": "Tabiiy fanlar (6-sinf)", "savol": "O'simliklarning quyosh nuri yordamida organik modda hosil qilish jarayoni nima deb ataladi?", "variantlar": ["Fotosintez", "Nafas olish", "Bug'lanish", "Changlanish"], "javob": "Fotosintez"},
        {"fan": "O'zbekiston tarixi (7-sinf)", "savol": "Mirzo Ulug'bek rasadxonasi qaysi shaharda bunyod etilgan?", "variantlar": ["Samarqand", "Buxoro", "Xiva", "Toshkent"], "javob": "Samarqand"},
        {"fan": "Geografiya (6-sinf)", "savol": "Yer yuzidagi eng katta va eng chuqur okean qaysi?", "variantlar": ["Tinch okeani", "Atlantika okeani", "Hind okeani", "Shimoliy Muz okeani"], "javob": "Tinch okeani"}
    ],
    "kattalar": [
        {"fan": "Konstitutsiya va Huquq", "savol": "O'zbekiston Respublikasi Konstitutsiyasiga ko'ra, davlat hokimiyatining birdan-bir manbai kim?", "variantlar": ["Xalq", "Parlament", "Vazirlar Mahkamasi", "Prezident"], "javob": "Xalq"},
        {"fan": "Jahon tarixi", "savol": "Qaysi davlat birinchi bo'lib qog'oz pullarni muomalaga kiritgan?", "variantlar": ["Xitoy", "Misr", "Rim imperiyasi", "Hindiston"], "javob": "Xitoy"},
        {"fan": "Iqtisodiyot", "savol": "Pulning qadrsizlanishi va tovar hamda xizmatlar narxining umumiy o'sishi nima deyiladi?", "variantlar": ["Inflyatsiya", "Deflyatsiya", "Devalvatsiya", "Diversifikatsiya"], "javob": "Inflyatsiya"}
    ]
}

def generate_dynamic_school_math() -> dict:
    sinf = random.choice([3, 4, 5, 6])
    turi = random.choice(["perimetr", "yuza", "tezlik", "tenglama"])
    
    if turi == "perimetr":
        a = random.randint(6, 25)
        b = random.randint(3, a - 1)
        togri = 2 * (a + b)
        savol = f"To'g'ri to'rtburchakning bo'yi {a} sm, eni esa {b} sm. Uning perimetrini toping."
        fan = f"Matematika ({sinf}-sinf)"
        birlik = " sm"
    elif turi == "yuza":
        a = random.randint(4, 18)
        b = random.randint(4, 15)
        togri = a * b
        savol = f"Bo'yi {a} metr, eni {b} metr bo'lgan xonaning yuzini (kv.m) hisoblang."
        fan = f"Matematika ({sinf}-sinf)"
        birlik = " kv.m"
    elif turi == "tezlik":
        v = random.choice([40, 50, 60, 70, 80])
        t = random.randint(2, 5)
        togri = v * t
        savol = f"Avtomobil {v} km/soat tezlik bilan {t} soatda qancha masofani bosib o'tadi?"
        fan = f"Matematika (4-sinf)"
        birlik = " km"
    else:
        x = random.randint(5, 20)
        k = random.randint(2, 5)
        c = random.randint(10, 30)
        res = k * x + c
        togri = x
        savol = f"Tenglamani yeching: {k}x + {c} = {res}"
        fan = f"Matematika (5-sinf)"
        birlik = ""

    javob = f"{togri}{birlik}"
    variantlar = {javob}
    while len(variantlar) < 4:
        xato = togri + random.choice([-10, -6, -4, -2, 2, 4, 6, 10])
        if xato > 0:
            variantlar.add(f"{xato}{birlik}")
            
    var_list = list(variantlar)
    random.shuffle(var_list)
    return {"fan": fan, "savol": savol, "variantlar": var_list, "javob": javob}

# ==========================================
# 4. AI ORQALI CHEKSIZ YANGI SAVOL TUZISH
# ==========================================
async def generate_ai_question(category: str, asked_list: list) -> dict | None:
    if not ai_model:
        return None

    recent_asked = asked_list[-35:]

    if category == "bolalar":
        sinf = random.randint(1, 11)
        fan = random.choice([
            "Matematika", "Ona tili", "Adabiyot", "O'zbekiston tarixi",
            "Tabiiy fanlar", "Biologiya", "Geografiya", "Fizika"
        ])
        rule = (
            f"Sen O'zbekiston umumta'lim maktablarining {sinf}-sinf '{fan}' darsligi bo'yicha test tuzuvchisan. "
            f"Savol FAQAT maktab darsligidagi aniq mavzular va qoidalardan tuzilsin."
        )
    else:
        mavzu = random.choice([
            "O'zbekiston qonunchiligi va huquq", "Jahon tarixi", "Mantiqiy fikrlash",
            "Iqtisodiyot", "Jahon geografiyasi", "Fan va texnologiya"
        ])
        rule = (
            f"Sen kattalar uchun '{mavzu}' yo'nalishida intellektual viktorina savolini tuzuvchisan. "
            f"Savol aniq faktga yoki mantiqqa asoslangan bo'lsin."
        )

    prompt = f"""
    {rule}
    Quyidagi savollarni va ularga o'xshashlarni ASLO takrorlama:
    {recent_asked}

    Faqat to'g'ri JSON formatda 1 ta yangi savol qaytar (boshqa hech qanday matn yozma):
    {{
        "fan": "Fan nomi (va sinfi) yoki mavzu",
        "savol": "Savol matni?",
        "variantlar": ["To'g'ri javob", "Xato javob 1", "Xato javob 2", "Xato javob 3"],
        "javob": "To'g'ri javob"
    }}
    """

    try:
        response = await asyncio.to_thread(ai_model.generate_content, prompt)
        raw = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        if "savol" in data and "variantlar" in data and "javob" in data and len(data["variantlar"]) == 4:
            if data["javob"] not in data["variantlar"]:
                data["variantlar"][0] = data["javob"]
            random.shuffle(data["variantlar"])
            return data
    except Exception as e:
        logging.warning(f"AI savol yaratishda xatolik: {e}")
    return None

async def get_fresh_question(user_id: int, category: str) -> dict:
    asked = get_user_asked_questions(user_id, category)

    for _ in range(2):
        ai_q = await generate_ai_question(category, list(asked))
        if ai_q and ai_q["savol"] not in asked:
            mark_question_used(user_id, category, ai_q["savol"])
            return ai_q

    available_static = [q for q in STATIC_QUESTIONS[category] if q["savol"] not in asked]
    if available_static:
        chosen = random.choice(available_static).copy()
        chosen["variantlar"] = chosen["variantlar"].copy()
        random.shuffle(chosen["variantlar"])
        mark_question_used(user_id, category, chosen["savol"])
        return chosen

    if category == "bolalar":
        for _ in range(10):
            dyn_q = generate_dynamic_school_math()
            if dyn_q["savol"] not in asked:
                mark_question_used(user_id, category, dyn_q["savol"])
                return dyn_q

    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM asked_questions WHERE user_id = ? AND category = ?", (user_id, category))
    conn.commit()
    conn.close()
    
    fallback = random.choice(STATIC_QUESTIONS[category]).copy()
    fallback["variantlar"] = fallback["variantlar"].copy()
    random.shuffle(fallback["variantlar"])
    mark_question_used(user_id, category, fallback["savol"])
    return fallback

# ==========================================
# 5. BOT KLAVIATURALARI VA HANDLERLARI
# ==========================================
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Railway Variables ga qo'shing.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
active_questions = {}

def main_menu_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎒 Bolalar bo'limi (Maktab darsliklari)")
    kb.button(text="🎓 Kattalar bo'limi")
    kb.button(text="📊 Mening natijam")
    kb.adjust(1, 1, 1)
    return kb.as_markup(resize_keyboard=True)

def build_question_kb(options: list, category: str):
    kb = InlineKeyboardBuilder()
    harflar = ["A", "B", "C", "D"]
    for idx, opt in enumerate(options):
        kb.button(text=f"{harflar[idx]}) {opt}", callback_data=f"ans:{idx}")
    kb.button(text="🔄 Keyingi savol", callback_data=f"next:{category}")
    kb.adjust(1, 1, 1, 1, 1)
    return kb.as_markup()

def next_question_kb(category: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="➡️ Keyingi savol", callback_data=f"next:{category}")
    return kb.as_markup()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Assalomu alaykum! Intellektual savol-javob botiga xush kelibsiz!**\n\n"
        "🎒 **Bolalar bo'limi** — faqat 1–11-sinf maktab darsliklari asosida.\n"
        "🎓 **Kattalar bo'limi** — huquq, tarix, mantiq va zamonaviy fanlar asosida.\n\n"
        "✨ *Savollar doimiy yangilanadi va sizga tushgan savol qayta takrorlanmaydi!*\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )

async def send_new_question(chat_id: int, user_id: int, category: str):
    wait_msg = await bot.send_message(chat_id, "⏳ *Yangi savol tayyorlanmoqda...*", parse_mode="Markdown")
    q_data = await get_fresh_question(user_id, category)
    active_questions[user_id] = {
        "category": category,
        "data": q_data
    }
    
    sarlavha = "🎒 **BOLALAR BO'LIMI (Maktab darsligi)**" if category == "bolalar" else "🎓 **KATTALAR BO'LIMI**"
    text = (
        f"{sarlavha}\n"
        f"📚 **Fan/Mavzu:** {q_data['fan']}\n\n"
        f"❓ **Savol:** {q_data['savol']}"
    )
    
    await wait_msg.edit_text(
        text,
        reply_markup=build_question_kb(q_data["variantlar"], category),
        parse_mode="Markdown"
    )

@dp.message(F.text == "🎒 Bolalar bo'limi (Maktab darsliklari)")
async def start_kids_quiz(message: types.Message):
    await send_new_question(message.chat.id, message.from_user.id, "bolalar")

@dp.message(F.text == "🎓 Kattalar bo'limi")
async def start_adults_quiz(message: types.Message):
    await send_new_question(message.chat.id, message.from_user.id, "kattalar")

@dp.message(F.text == "📊 Mening natijam")
async def show_my_score(message: types.Message):
    correct, total = get_score(message.from_user.id)
    foiz = round((correct / total) * 100, 1) if total > 0 else 0
    await message.answer(
        f"📊 **Sizning ko'rsatkichingiz:**\n\n"
        f"✅ To'g'ri javoblar: **{correct} ta**\n"
        f"📝 Jami javob berilgan savollar: **{total} ta**\n"
        f"📈 Natija: **{foiz}%**",
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("ans:"))
async def handle_answer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in active_questions:
        await callback.answer("Bu savol eskirgan. Yangi savol tugmasini bosing!", show_alert=True)
        return

    idx = int(callback.data.split(":")[1])
    session = active_questions.pop(user_id)
    q_data = session["data"]
    category = session["category"]
    
    selected_option = q_data["variantlar"][idx]
    correct_option = q_data["javob"]
    is_correct = (selected_option == correct_option)
    
    update_score(user_id, is_correct)

    if is_correct:
        result_text = f"✅ **Barakalla! Javobingiz to'g'ri:** {correct_option}"
    else:
        result_text = (
            f"❌ **Afsuski, noto'g'ri!**\n"
            f"Siz tanladingiz: {selected_option}\n"
            f"✅ **To'g'ri javob:** {correct_option}"
        )

    updated_message = (
        f"📚 **Fan/Mavzu:** {q_data['fan']}\n"
        f"❓ **Savol:** {q_data['savol']}\n\n"
        f"{result_text}"
    )

    await callback.message.edit_text(
        updated_message,
        reply_markup=next_question_kb(category),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("next:"))
async def handle_next(callback: types.CallbackQuery):
    category = callback.data.split(":")[1]
    await callback.answer()
    await send_new_question(callback.message.chat.id, callback.from_user.id, category)

# ==========================================
# 6. ISHGA TUSHIRISH
# ==========================================
async def main():
    init_db()
    logging.info("Bot ishga tushdi!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
