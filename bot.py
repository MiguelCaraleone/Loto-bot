import os
import re
import html
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
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_model = genai.GenerativeModel("gemini-2.5-flash")
    except Exception as e:
        logging.warning(f"Gemini sozlashda xatolik: {e}")

# ==========================================
# 2. SQLITE BAZA (Eski savollar qayta tushmasligi uchun)
# ==========================================
DB_NAME = "quiz_memory.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
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

def get_user_asked_questions(user_id: int, category: str) -> set:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT question_text FROM asked_questions WHERE user_id = ? AND category = ?",
            (user_id, category)
        )
        return {row[0] for row in cur.fetchall()}

def mark_question_used(user_id: int, category: str, question_text: str):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO asked_questions (user_id, category, question_text) VALUES (?, ?, ?)",
            (user_id, category, question_text)
        )
        conn.commit()

def update_score(user_id: int, is_correct: bool):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO scores (user_id, correct_count, total_count) VALUES (?, 0, 0)", (user_id,))
        if is_correct:
            cur.execute("UPDATE scores SET correct_count = correct_count + 1, total_count = total_count + 1 WHERE user_id = ?", (user_id,))
        else:
            cur.execute("UPDATE scores SET total_count = total_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

def get_score(user_id: int) -> tuple:
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT correct_count, total_count FROM scores WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row if row else (0, 0)

# ==========================================
# 3. KENGAYTIRILGAN ZAXIRA VA DINAMIK BAZA
# ==========================================
STATIC_QUESTIONS = {
    "bolalar": [
        {"fan": "Ona tili (5-sinf)", "savol": "Qaysi qatorda faqat ot so'z turkumiga oid so'zlar berilgan?", "variantlar": ["Kitob, maktab, daftar", "Chiroyli, katta, qizil", "O'qimoq, yozmoq, bormoq", "Tez, sekin, ko'p"], "javob": "Kitob, maktab, daftar"},
        {"fan": "Tabiiy fanlar (6-sinf)", "savol": "O'simliklarning quyosh nuri yordamida organik modda hosil qilish jarayoni nima deb ataladi?", "variantlar": ["Fotosintez", "Nafas olish", "Bug'lanish", "Changlanish"], "javob": "Fotosintez"},
        {"fan": "O'zbekiston tarixi (7-sinf)", "savol": "Mirzo Ulug'bek rasadxonasi qaysi shaharda bunyod etilgan?", "variantlar": ["Samarqand", "Buxoro", "Xiva", "Toshkent"], "javob": "Samarqand"},
        {"fan": "Geografiya (6-sinf)", "savol": "Yer yuzidagi eng katta va eng chuqur okean qaysi?", "variantlar": ["Tinch okeani", "Atlantika okeani", "Hind okeani", "Shimoliy Muz okeani"], "javob": "Tinch okeani"},
        {"fan": "Adabiyot (5-sinf)", "savol": "'Shum bola' qissasining muallifi kim?", "variantlar": ["G'afur G'ulom", "Abdulla Qodiriy", "Oybek", "Cho'lpon"], "javob": "G'afur G'ulom"},
        {"fan": "Biologiya (8-sinf)", "savol": "Odam yuragi nechta kameradan (bo'lmachadan) iborat?", "variantlar": ["4 ta", "2 ta", "3 ta", "5 ta"], "javob": "4 ta"},
        {"fan": "Fizika (7-sinf)", "savol": "Xalqaro birliklar tizimida (SI) kuchning o'lchov birligi nima?", "variantlar": ["Nyuton", "Joul", "Vatt", "Paskal"], "javob": "Nyuton"},
        {"fan": "Kimyo (7-sinf)", "savol": "Suvning kimyoviy formulasi qanday?", "variantlar": ["H2O", "CO2", "NaCl", "O2"], "javob": "H2O"},
        {"fan": "O'zbekiston tarixi (8-sinf)", "savol": "Amir Temur davlatining poytaxti qaysi shahar bo'lgan?", "variantlar": ["Samarqand", "Shahrisabz", "Buxoro", "Hirot"], "javob": "Samarqand"},
        {"fan": "Matematika (5-sinf)", "savol": "Eng kichik tub son qaysi?", "variantlar": ["2", "1", "3", "0"], "javob": "2"},
        {"fan": "Geografiya (7-sinf)", "savol": "Dunyodagi eng uzun daryo qaysi?", "variantlar": ["Nil", "Amazonka", "Amudaryo", "Yanszi"], "javob": "Nil"},
        {"fan": "Adabiyot (9-sinf)", "savol": "Alisher Navoiyning 'Xamsa' asari nechta dostondan iborat?", "variantlar": ["5 ta", "4 ta", "6 ta", "7 ta"], "javob": "5 ta"},
        {"fan": "Ona tili (6-sinf)", "savol": "Fe'lning nechta zamon shakli bor?", "variantlar": ["3 ta", "2 ta", "4 ta", "5 ta"], "javob": "3 ta"},
        {"fan": "Biologiya (6-sinf)", "savol": "Hujayraning asosiy qismlari qaysilar?", "variantlar": ["Qobiq, sitoplazma, yadro", "Barg, poya, ildiz", "To'qima, organ, hujayra", "Suv, mineral tuz, havo"], "javob": "Qobiq, sitoplazma, yadro"},
        {"fan": "Fizika (6-sinf)", "savol": "Moddaning nechta asosiy agregat holati mavjud?", "variantlar": ["3 ta (qattiq, suyuq, gaz)", "2 ta (qattiq, suyuq)", "4 ta", "5 ta"], "javob": "3 ta (qattiq, suyuq, gaz)"}
    ],
    "kattalar": [
        {"fan": "Konstitutsiya va Huquq", "savol": "O'zbekiston Respublikasi Konstitutsiyasiga ko'ra, davlat hokimiyatining birdan-bir manbai kim?", "variantlar": ["Xalq", "Parlament", "Vazirlar Mahkamasi", "Prezident"], "javob": "Xalq"},
        {"fan": "Jahon tarixi", "savol": "Qaysi davlat birinchi bo'lib qog'oz pullarni muomalaga kiritgan?", "variantlar": ["Xitoy", "Misr", "Rim imperiyasi", "Hindiston"], "javob": "Xitoy"},
        {"fan": "Iqtisodiyot", "savol": "Pulning qadrsizlanishi va tovar hamda xizmatlar narxining umumiy o'sishi nima deyiladi?", "variantlar": ["Inflyatsiya", "Deflyatsiya", "Devalvatsiya", "Diversifikatsiya"], "javob": "Inflyatsiya"},
        {"fan": "Jinoyat huquqi", "savol": "Shaxsning aybdorligi qonunda belgilangan tartibda va sudning qonuniy kuchga kirgan hukmi bilan aniqlanmaguncha aybsiz hisoblanishi nima deyiladi?", "variantlar": ["Aybsizlik prezumpsiyasi", "Qonuniylik prinsipi", "Odil sudlov", "Insonparvarlik"], "javob": "Aybsizlik prezumpsiyasi"},
        {"fan": "Xalqaro huquq", "savol": "Inson huquqlari umumjahon deklaratsiyasi BMT Bosh Assambleyasi tomonidan qachon qabul qilingan?", "variantlar": ["1948-yil 10-dekabr", "1945-yil 24-oktyabr", "1950-yil 1-iyun", "1966-yil 16-dekabr"], "javob": "1948-yil 10-dekabr"},
        {"fan": "Geosiyosat", "savol": "Birlashgan Millatlar Tashkiloti (BMT) Xavfsizlik Kengashining nechta doimiy a'zosi bor?", "variantlar": ["5 ta", "7 ta", "10 ta", "15 ta"], "javob": "5 ta"},
        {"fan": "Jahon adabiyoti", "savol": "'Jinoyat va jazo' romanining muallifi kim?", "variantlar": ["Fyodor Dostoyevskiy", "Lev Tolstoy", "Anton Chexov", "Nikolay Gogol"], "javob": "Fyodor Dostoyevskiy"},
        {"fan": "Davlat moliyasi", "savol": "Davlat byudjeti xarajatlarining daromadlaridan oshib ketishi nima deb ataladi?", "variantlar": ["Byudjet taqchilligi (defitsiti)", "Byudjet profitsiti", "Balans", "Subvensiya"], "javob": "Byudjet taqchilligi (defitsiti)"},
        {"fan": "Ma'muriy huquq", "savol": "Ma'muriy sud ishlarini yuritishda da'vogarning talablaridan voz kechishi yoki taraflarning kelishuvi qanday hujjat bilan rasmiylashtiriladi?", "variantlar": ["Sud ajrimi", "Sud hukmi", "Ma'muriy bayonnoma", "Taqdimnoma"], "javob": "Sud ajrimi"},
        {"fan": "Fan va koinot", "savol": "Quyosh tizimidagi eng katta sayyora qaysi?", "variantlar": ["Yupiter", "Saturn", "Neptun", "Yer"], "javob": "Yupiter"},
        {"fan": "Mantiq", "savol": "Agar 5 ta mashina 5 daqiqada 5 ta detal ishlab chiqarsa, 100 ta mashina 100 ta detalni necha daqiqada ishlab chiqaradi?", "variantlar": ["5 daqiqada", "100 daqiqada", "20 daqiqada", "50 daqiqada"], "javob": "5 daqiqada"},
        {"fan": "Jahon geografiyasi", "savol": "Janubiy Amerika materigidagi eng katta davlat qaysi?", "variantlar": ["Braziliya", "Argentina", "Kolumbiya", "Peru"], "javob": "Braziliya"}
    ]
}

def generate_dynamic_school_question() -> dict:
    """Bolalar uchun maktab darsligi doirasida cheksiz dinamik savollar"""
    turi = random.choice(["perimetr", "yuza", "tezlik", "tenglama", "kasr"])
    
    if turi == "perimetr":
        a = random.randint(6, 30)
        b = random.randint(3, a - 1)
        togri = 2 * (a + b)
        savol = f"To'g'ri to'rtburchakning bo'yi {a} sm, eni esa {b} sm. Uning perimetrini toping."
        fan = "Matematika (4-sinf)"
        birlik = " sm"
    elif turi == "yuza":
        a = random.randint(4, 25)
        b = random.randint(4, 20)
        togri = a * b
        savol = f"Bo'yi {a} metr, eni {b} metr bo'lgan to'g'ri to'rtburchak shaklidagi maydonning yuzini (kv.m) hisoblang."
        fan = "Matematika (5-sinf)"
        birlik = " kv.m"
    elif turi == "tezlik":
        v = random.choice([45, 50, 60, 75, 80, 90])
        t = random.randint(2, 6)
        togri = v * t
        savol = f"Poyezd {v} km/soat tezlik bilan {t} soatda qancha masofani bosib o'tadi?"
        fan = "Matematika (4-sinf)"
        birlik = " km"
    elif turi == "kasr":
        son = random.choice([60, 80, 100, 120, 150, 200, 240])
        bolak = random.choice([2, 4, 5, 10])
        togri = son // bolak
        savol = f"{son} sonining 1/{bolak} qismi nechaga teng?"
        fan = "Matematika (5-sinf)"
        birlik = ""
    else:
        x = random.randint(4, 25)
        k = random.randint(2, 7)
        c = random.randint(8, 40)
        res = k * x + c
        togri = x
        savol = f"Tenglamani yeching: {k}x + {c} = {res}"
        fan = "Matematika (6-sinf)"
        birlik = ""

    javob = f"{togri}{birlik}"
    variantlar = {javob}
    while len(variantlar) < 4:
        xato = togri + random.choice([-12, -8, -5, -3, 3, 5, 8, 12, 15])
        if xato > 0:
            variantlar.add(f"{xato}{birlik}")
            
    var_list = list(variantlar)
    random.shuffle(var_list)
    return {"fan": fan, "savol": savol, "variantlar": var_list, "javob": javob}

def generate_dynamic_adult_question() -> dict:
    """Kattalar uchun mantiq va moliyaviy tahlil bo'yicha cheksiz dinamik savollar"""
    turi = random.choice(["foiz", "ketma_ketlik", "ish_unumdorligi"])
    
    if turi == "foiz":
        summa = random.choice([200, 400, 500, 800, 1200, 1500])
        foiz = random.choice([10, 15, 20, 25, 30])
        togri = int(summa * (1 + foiz / 100))
        savol = f"Agar mahsulotning boshlang'ich narxi {summa} ming so'm bo'lib, narx {foiz}% ga oshirilsa, uning yangi narxi qancha bo'ladi?"
        fan = "Iqtisodiyot va moliya"
        birlik = " ming so'm"
    elif turi == "ketma_ketlik":
        bosh = random.randint(2, 12)
        qadam = random.randint(3, 9)
        ketma = [bosh + i * qadam for i in range(5)]
        togri = ketma[4]
        savol = f"Mantiqiy ketma-ketlikni davom ettiring: {ketma[0]}, {ketma[1]}, {ketma[2]}, {ketma[3]}, ...?"
        fan = "Mantiqiy tahlil"
        birlik = ""
    else:
        kun = random.choice([6, 8, 10, 12])
        ishchi1 = random.choice([3, 4, 6])
        ishchi2 = ishchi1 * 2
        togri = kun // 2
        savol = f"{ishchi1} ta mutaxassis loyihani {kun} kunda yakunlaydi. Shu tempda {ishchi2} ta mutaxassis bu loyihani necha kunda tugatadi?"
        fan = "Mantiq va menejment"
        birlik = " kunda"

    javob = f"{togri}{birlik}"
    variantlar = {javob}
    while len(variantlar) < 4:
        xato = togri + random.choice([-10, -5, -2, -1, 1, 2, 5, 10])
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

    recent_asked = asked_list[-30:]

    if category == "bolalar":
        sinf = random.randint(1, 11)
        fan = random.choice([
            "Matematika", "Ona tili", "Adabiyot", "O'zbekiston tarixi",
            "Tabiiy fanlar", "Biologiya", "Geografiya", "Fizika", "Kimyo"
        ])
        rule = (
            f"Sen O'zbekiston umumta'lim maktablarining {sinf}-sinf '{fan}' darsligi bo'yicha test tuzuvchisan. "
            f"Savol FAQAT maktab darsligidagi aniq mavzular va qoidalardan tuzilsin."
        )
    else:
        mavzu = random.choice([
            "O'zbekiston qonunchiligi va huquq", "Jahon tarixi", "Mantiqiy fikrlash",
            "Iqtisodiyot va moliya", "Jahon geografiyasi", "Fan va texnologiya"
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
        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(0))
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

    # 1. AI orqali yangi savol olish
    for _ in range(2):
        ai_q = await generate_ai_question(category, list(asked))
        if ai_q and ai_q["savol"] not in asked:
            mark_question_used(user_id, category, ai_q["savol"])
            return ai_q

    # 2. Statik bazadan hali tushmagan savolni olish
    available_static = [q for q in STATIC_QUESTIONS[category] if q["savol"] not in asked]
    if available_static:
        chosen = random.choice(available_static).copy()
        chosen["variantlar"] = chosen["variantlar"].copy()
        random.shuffle(chosen["variantlar"])
        mark_question_used(user_id, category, chosen["savol"])
        return chosen

    # 3. Dinamik generator orqali yangi savol tuzish (ham bolalar, ham kattalar uchun)
    for _ in range(15):
        dyn_q = generate_dynamic_school_question() if category == "bolalar" else generate_dynamic_adult_question()
        if dyn_q["savol"] not in asked:
            mark_question_used(user_id, category, dyn_q["savol"])
            return dyn_q

    # 4. Barcha savollar ishlatib bo'linganda tarixni tozalash
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM asked_questions WHERE user_id = ? AND category = ?", (user_id, category))
        conn.commit()
    
    fallback = random.choice(STATIC_QUESTIONS[category]).copy()
    fallback["variantlar"] = fallback["variantlar"].copy()
    random.shuffle(fallback["variantlar"])
    mark_question_used(user_id, category, fallback["savol"])
    return fallback

# ==========================================
# 5. BOT KLAVIATURALARI VA HANDLERLARI
# ==========================================
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Railway Variables bo'limiga BOT_TOKEN qo'shing.")

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
        "👋 <b>Assalomu alaykum! Intellektual savol-javob botiga xush kelibsiz!</b>\n\n"
        "🎒 <b>Bolalar bo'limi</b> — faqat 1–11-sinf maktab darsliklari asosida.\n"
        "🎓 <b>Kattalar bo'limi</b> — huquq, tarix, mantiq va zamonaviy fanlar asosida.\n\n"
        "✨ <i>Savollar doimiy yangilanadi va sizga tushgan savol qayta takrorlanmaydi!</i>\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )

async def send_new_question(chat_id: int, user_id: int, category: str, edit_msg: types.Message = None):
    if edit_msg:
        wait_msg = await edit_msg.edit_text("⏳ <i>Yangi savol tayyorlanmoqda...</i>", parse_mode="HTML")
    else:
        wait_msg = await bot.send_message(chat_id, "⏳ <i>Yangi savol tayyorlanmoqda...</i>", parse_mode="HTML")

    q_data = await get_fresh_question(user_id, category)
    active_questions[user_id] = {
        "category": category,
        "data": q_data
    }
    
    sarlavha = "🎒 <b>BOLALAR BO'LIMI (Maktab darsligi)</b>" if category == "bolalar" else "🎓 <b>KATTALAR BO'LIMI</b>"
    fan_safe = html.escape(str(q_data["fan"]))
    savol_safe = html.escape(str(q_data["savol"]))

    text = (
        f"{sarlavha}\n"
        f"📚 <b>Fan/Mavzu:</b> {fan_safe}\n\n"
        f"❓ <b>Savol:</b> {savol_safe}"
    )
    
    await wait_msg.edit_text(
        text,
        reply_markup=build_question_kb(q_data["variantlar"], category),
        parse_mode="HTML"
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
        f"📊 <b>Sizning ko'rsatkichingiz:</b>\n\n"
        f"✅ To'g'ri javoblar: <b>{correct} ta</b>\n"
        f"📝 Jami javob berilgan savollar: <b>{total} ta</b>\n"
        f"📈 Natija: <b>{foiz}%</b>",
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("ans:"))
async def handle_answer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in active_questions:
        await callback.answer("Bu savolga javob berilgan. Keyingi savol tugmasini bosing!", show_alert=True)
        return

    idx = int(callback.data.split(":")[1])
    session = active_questions.pop(user_id)
    q_data = session["data"]
    category = session["category"]
    
    selected_option = q_data["variantlar"][idx]
    correct_option = q_data["javob"]
    is_correct = (selected_option == correct_option)
    
    update_score(user_id, is_correct)

    sel_safe = html.escape(str(selected_option))
    cor_safe = html.escape(str(correct_option))
    fan_safe = html.escape(str(q_data["fan"]))
    savol_safe = html.escape(str(q_data["savol"]))

    if is_correct:
        result_text = f"✅ <b>Barakalla! Javobingiz to'g'ri:</b> {cor_safe}"
    else:
        result_text = (
            f"❌ <b>Afsuski, noto'g'ri!</b>\n"
            f"Siz tanladingiz: {sel_safe}\n"
            f"✅ <b>To'g'ri javob:</b> {cor_safe}"
        )

    updated_message = (
        f"📚 <b>Fan/Mavzu:</b> {fan_safe}\n"
        f"❓ <b>Savol:</b> {savol_safe}\n\n"
        f"{result_text}"
    )

    await callback.message.edit_text(
        updated_message,
        reply_markup=next_question_kb(category),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("next:"))
async def handle_next(callback: types.CallbackQuery):
    category = callback.data.split(":")[1]
    await callback.answer()
    await send_new_question(callback.message.chat.id, callback.from_user.id, category, edit_msg=callback.message)

# ==========================================
# 6. ISHGA TUSHIRISH
# ==========================================
async def main():
    init_db()
    logging.info("Bot muvaffaqiyatli ishga tushdi!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
