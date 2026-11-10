import asyncio
import logging
import aiosqlite
import aiohttp
import random
import os
import re
import html
import time
import base64
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.token import validate_token

# =========================================================================
# ⚙️ SOZLAMALAR VA XATOSIZ TOKEN TEKSHIRUVI
# =========================================================================
_ENCODED_DEFAULT = "OTIzNzM4ODY0ODpBQUhxQzFVSHFia01VRndFSVctdkU1OU9qOTkwWnAyQXI0dw=="
DEFAULT_TOKEN = base64.b64decode(_ENCODED_DEFAULT).decode("utf-8")

raw_env_token = (os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or "").strip().strip('"').strip("'")
try:
    validate_token(raw_env_token)
    TOKEN = raw_env_token
except Exception:
    TOKEN = DEFAULT_TOKEN.strip()

GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")

ADMIN_ID = 1302845749
DB_PATH = "loto_game.db"
KARTA_RAQAMI = "9860 3501 4780 2176"
KARTA_EGASI = "Mamatkulov Izzatillo"
JOKER_IMG_URL = "https://i.ibb.co/RkRvBsHP/file-00000000865082469ff369a93b107407.png"

SUBJECTS = {
    "matematika": "📐 Matematika",
    "fizika": "⚡ Fizika",
    "adabiyot": "📚 Adabiyot",
    "ona_tili": "📝 Ona tili",
    "biologiya": "🧬 Biologiya",
    "tarix": "🏛 Tarix",
    "huquq": "⚖️ Huquq",
    "aralash": "🌐 Aralash (Barcha fanlar)"
}

class GameStates(StatesGroup):
    waiting_for_receipt = State()
    waiting_for_card = State()
    adding_single_question = State()
    adding_bulk_questions = State()

ADABIYOT_EASY = [
    ("5-sinf Adabiyot: «O'tkan kunlar» romanining muallifi kim?", "Abdulla Qodiriy", "Cho'lpon", "Oybek", "G'afur G'ulom"),
    ("6-sinf Adabiyot: «Shum bola» qissasini kim yozgan?", "G'afur G'ulom", "Abdulla Qahhor", "Said Ahmad", "O'tkir Hoshimov"),
    ("5-sinf Adabiyot: «Sariq devni minib» asari muallifi kim?", "Xudoyberdi To'xtaboyev", "Pirimqul Qodirov", "Odil Yoqubov", "Mirmuhsin"),
    ("9-sinf Adabiyot: Alisher Navoiyning «Xamsa» asari nechta dostondan iborat?", "5 ta", "4 ta", "6 ta", "3 ta"),
    ("7-sinf Adabiyot: «Dunyoning ishlari» asari muallifi kim?", "O'tkir Hoshimov", "Said Ahmad", "Asqad Muxtor", "Erkin Vohidov"),
    ("8-sinf Adabiyot: «Yulduzli tunlar» romani kim haqida yozilgan?", "Zahiriddin Muhammad Bobur", "Amir Temur", "Mirzo Ulug'bek", "Alisher Navoiy"),
    ("7-sinf Adabiyot: «O'zbegim» qasidasi muallifi kim?", "Erkin Vohidov", "Abdulla Oripov", "Usmon Nosir", "Hamid Olimjon"),
    ("6-sinf Adabiyot: «O'g'ri» va «Bemor» hikoyalari muallifi kim?", "Abdulla Qahhor", "G'afur G'ulom", "Oybek", "Cho'lpon")
]

ADABIYOT_HARD = [
    ("«Kecha va kunduz» romanining birinchi qismi qanday nomlanadi?", "Bahor", "Yoz", "Kuz", "Qish"),
    ("Alisher Navoiyning «Lison ut-tayr» dostonida qushlar yetakchisi qaysi qush?", "Hudhud", "Semurg'", "Bulbul", "Burgut"),
    ("Odil Yoqubovning «Ulug'bek xazinasi» romanida Ulug'bekning sodiq shogirdi kim?", "Ali Qushchi", "Qozizoda Rumiy", "G'iyosiddin Jamshid", "Mavlono Muhiddin"),
    ("O'tkir Hoshimovning «Ikki eshik orasi» romanida Qora ammaning asl ismi nima?", "Robiya", "Ra'no", "Zebi", "Kumush"),
    ("Cho'lponning «Kecha va kunduz» romanida Razzoq so'fining qizi kim?", "Zebi", "Maryam", "Xadicha", "Kumush")
]

TARIX_EASY = [
    ("7-sinf Tarix: Amir Temur qaysi yilda tavallud topgan?", "1336-yil", "1441-yil", "1483-yil", "1394-yil"),
    ("11-sinf Tarix: O'zbekiston Respublikasi qachon mustaqillikka erishgan?", "1991-yil", "1990-yil", "1992-yil", "1989-yil"),
    ("8-sinf Tarix: Amir Temur davlatining poytaxti qaysi shahar bo'lgan?", "Samarqand", "Buxoro", "Toshkent", "Xiva"),
    ("6-sinf Tarix: Qadimgi Misr podsholari nima deb atalgan?", "Fir'avn", "Imperator", "Sulton", "Xon"),
    ("9-sinf Tarix: Birinchi jahon urushi qaysi yilda boshlangan?", "1914-yil", "1918-yil", "1939-yil", "1941-yil")
]

TARIX_HARD = [
    ("Amir Temur va Boyazid Yildirim o'rtasidagi Anqara jangi qachon bo'lib o'tgan?", "1402-yil 20-iyul", "1395-yil 15-aprel", "1365-yil 22-may", "1405-yil 18-fevral"),
    ("Jaloliddin Manguberdi mo'g'ullar ustidan g'alaba qozongan Parvon jangi qaysi yilda bo'lgan?", "1221-yil", "1219-yil", "1225-yil", "1231-yil"),
    ("O'zbekiston Respublikasi BMTga qachon a'zo bo'lgan?", "1992-yil 2-mart", "1991-yil 18-noyabr", "1992-yil 8-dekabr", "1993-yil 10-yanvar")
]

BIOLOGIYA_EASY = [
    ("6-sinf Botanika: O'simliklarda fotosintez jarayoni qaysi qismda boradi?", "Bargda (Xloroplastda)", "Ildizda", "Po'stloqda", "Urug'da"),
    ("8-sinf Biologiya: Inson tanasidagi eng katta organ qaysi?", "Teri", "Yurak", "O'pka", "Buyrak"),
    ("8-sinf Biologiya: Inson yuragi nechta kameradan iborat?", "4 ta", "2 ta", "3 ta", "5 ta")
]

BIOLOGIYA_HARD = [
    ("Hujayrada oqsil biosintezi qaysi organoidda amalga oshadi?", "Ribosoma", "Lizosoma", "Golji majmuasi", "Mitoxondriya"),
    ("Hujayraning «energiya stansiyasi» (ATF sintezlovchi) qaysi organoid?", "Mitoxondriya", "Ribosoma", "Endoplazmatik to'r", "Sentrosoma")
]

ONA_TILI_EASY = [
    ("5-sinf Ona tili: «Kim? Nima? Qayer?» so'roqlariga javob bo'luvchi so'z turkumi qaysi?", "Ot", "Sifat", "Fe'l", "Son"),
    ("5-sinf Ona tili: Ma'nosi bir-biriga qarama-qarshi bo'lgan so'zlar nima deyiladi?", "Antonimlar", "Sinonimlar", "Omonimlar", "Paronimlar"),
    ("5-sinf Ona tili: O'zbek tiliga Davlat tili maqomi qachon berilgan?", "1989-yil 21-oktabr", "1991-yil 1-sentabr", "1992-yil 8-dekabr", "1995-yil 24-avgust")
]

ONA_TILI_HARD = [
    ("Qaysi qatordagi so'z imlo qoidalariga ko'ra to'g'ri yozilgan?", "Taassurot", "Tassurot", "Taasurot", "Tasurot"),
    ("Talaffuzi yaqin, ammo ma'nosi va yozilishi farq qiluvchi so'zlar (asr - asir) nima deyiladi?", "Paronimlar", "Omonimlar", "Sinonimlar", "Arxaizmlar")
]

HUQUQ_EASY = [
    ("8-sinf Huquq: O'zbekiston Respublikasining Konstitutsiyasi kuni qachon nishonlanadi?", "8-dekabr", "1-sentabr", "21-oktabr", "18-noyabr"),
    ("9-sinf Huquq: O'zbekistonda fuqarolar necha yoshdan saylash huquqiga ega bo'ladilar?", "18 yoshdan", "16 yoshdan", "21 yoshdan", "25 yoshdan"),
    ("8-sinf Huquq: O'zbekistonda davlat hokimiyatining yagona manbai kim?", "Xalq", "Vazirlar Mahkamasi", "Oliy sud", "Hokimliklar")
]

HUQUQ_HARD = [
    ("Yangi tahrirdagi O'zbekiston Respublikasi Konstitutsiyasi nechta bo'lim, bob va moddadan iborat?", "6 bo'lim, 27 bob, 155 modda", "6 bo'lim, 26 bob, 128 modda", "5 bo'lim, 25 bob, 150 modda", "7 bo'lim, 28 bob, 160 modda"),
    ("Yangi tahrirdagi O'zbekiston Konstitutsiyasi umumxalq referendumida qachon qabul qilindi?", "2023-yil 30-aprel", "2022-yil 8-dekabr", "2023-yil 1-may", "2024-yil 1-yanvar")
]

def generate_subject_question(subject: str, difficulty: str = "easy"):
    if subject == "aralash" or subject not in SUBJECTS:
        subject = random.choice(["matematika", "fizika", "adabiyot", "ona_tili", "biologiya", "tarix", "huquq"])

    if subject == "matematika":
        if difficulty == "easy":
            turi = random.choice(["add_sub", "perimetr", "yuza"])
            if turi == "add_sub":
                a, b, c = random.randint(25, 120), random.randint(15, 80), random.randint(10, 40)
                ans = a + b - c
                q_text = f"📐 Matematika (4-sinf darsligi): Hisoblang: {a} + {b} - {c} = ?"
            elif turi == "perimetr":
                a, b = random.randint(8, 30), random.randint(4, 20)
                ans = 2 * (a + b)
                q_text = f"📐 Matematika (5-sinf darsligi): To'g'ri to'rtburchakning bo'yi {a} sm, eni {b} sm. Perimetrini (sm) toping."
            else:
                a, b = random.randint(5, 22), random.randint(4, 18)
                ans = a * b
                q_text = f"📐 Matematika (5-sinf darsligi): Bo'yi {a} m va eni {b} m bo'lgan xonaning yuzini (m²) toping."
        else:
            son = random.choice([200, 300, 400, 500, 600, 800])
            foiz = random.choice([15, 20, 25, 35, 40])
            ans = (son * foiz) // 100
            q_text = f"📐 Matematika (Bellashuv): {son} sonining {foiz}% ini toping."

        wrongs = set()
        while len(wrongs) < 3:
            w = ans + random.choice([-10, -5, -3, 2, 3, 5, 10])
            if w != ans and w > 0:
                wrongs.add(str(w))
        w_list = list(wrongs)
        return {"question": q_text, "opt1": str(ans), "opt2": w_list[0], "opt3": w_list[1], "opt4": w_list[2], "correct_opt": 1, "subject": "matematika", "difficulty": difficulty}

    elif subject == "fizika":
        if difficulty == "easy":
            v = random.choice([40, 50, 60, 70, 80])
            t = random.randint(2, 5)
            s = v * t
            ans = f"{v} km/soat"
            wrongs = [f"{v + 10} km/soat", f"{v - 15} km/soat", f"{v + 20} km/soat"]
            q_text = f"⚡ Fizika (6-sinf darsligi): Avtomobil {s} km masofani {t} soatda bosib o'tdi. Tezligini toping."
        else:
            i_val = random.randint(3, 10)
            r_val = random.randint(5, 20)
            u_val = i_val * r_val
            ans = f"{r_val} Om"
            wrongs = [f"{r_val + 4} Om", f"{max(2, r_val - 3)} Om", f"{r_val * 2} Om"]
            q_text = f"⚡ Fizika (Bellashuv): Kuchlanishi {u_val} V bo'lgan o'tkazgichdan {i_val} A tok o'tmoqda. Qarshilikni (R) toping."
        return {"question": q_text, "opt1": ans, "opt2": wrongs[0], "opt3": wrongs[1], "opt4": wrongs[2], "correct_opt": 1, "subject": "fizika", "difficulty": difficulty}

    pool_map = {
        "adabiyot": (ADABIYOT_EASY, ADABIYOT_HARD, "📚 Adabiyot"),
        "tarix": (TARIX_EASY, TARIX_HARD, "🏛 Tarix"),
        "biologiya": (BIOLOGIYA_EASY, BIOLOGIYA_HARD, "🧬 Biologiya"),
        "ona_tili": (ONA_TILI_EASY, ONA_TILI_HARD, "📝 Ona tili"),
        "huquq": (HUQUQ_EASY, HUQUQ_HARD, "⚖️ Huquq"),
    }
    easy_list, hard_list, prefix = pool_map[subject]
    chosen_list = easy_list if difficulty == "easy" else hard_list
    q_raw, o1, o2, o3, o4 = random.choice(chosen_list)
    label = "Maktab darsligi" if difficulty == "easy" else "Bellashuv"
    return {
        "question": f"{prefix} ({label}): {q_raw}",
        "opt1": o1, "opt2": o2, "opt3": o3, "opt4": o4,
        "correct_opt": 1, "subject": subject, "difficulty": difficulty
    }

async def fetch_ai_question(subject: str, difficulty: str) -> dict | None:
    if not GEMINI_API_KEY:
        return None
    subj_title = SUBJECTS.get(subject, "Aralash fanlar")
    if difficulty == "easy":
        rule = f"O'zbekiston umumta'lim maktablari (4-11 sinf) '{subj_title}' darsligi asosida 1 ta oson va aniq test savoli tuz."
    else:
        rule = f"Kattalar intellektual bellashuvi uchun '{subj_title}' yo'nalishida 1 ta qiziqarli test savoli tuz."

    prompt = f"{rule}\nFaqat JSON formatida qaytar:\n{{\"question\": \"Savol?\", \"opt1\": \"To'g'ri\", \"opt2\": \"Xato1\", \"opt3\": \"Xato2\", \"opt4\": \"Xato3\"}}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=6) as resp:
                if resp.status != 200:
                    return None
                res_json = await resp.json()
                text_out = res_json["candidates"][0]["content"]["parts"][0]["text"]
                match = re.search(r"\{.*\}", text_out, re.DOTALL)
                if not match:
                    return None
                import json
                data = json.loads(match.group(0))
                if all(k in data for k in ("question", "opt1", "opt2", "opt3", "opt4")):
                    label = "Maktab darsligi" if difficulty == "easy" else "Bellashuv"
                    return {
                        "question": f"{subj_title} ({label}): {data['question']}",
                        "opt1": str(data["opt1"]), "opt2": str(data["opt2"]),
                        "opt3": str(data["opt3"]), "opt4": str(data["opt4"]),
                        "correct_opt": 1, "subject": subject if subject in SUBJECTS else "aralash", "difficulty": difficulty
                    }
    except Exception:
        pass
    return None

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS questions
            (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT UNIQUE, opt1 TEXT, opt2 TEXT, opt3 TEXT, opt4 TEXT, correct_opt INTEGER, subject TEXT DEFAULT 'aralash', difficulty TEXT DEFAULT 'easy')""")
        await db.execute("""CREATE TABLE IF NOT EXISTS users
            (user_id INTEGER PRIMARY KEY, role TEXT, status TEXT, pending_mode TEXT DEFAULT 'pay_2', pending_subject TEXT DEFAULT 'aralash')""")
        await db.execute("""CREATE TABLE IF NOT EXISTS user_seen_questions
            (user_id INTEGER, question_id INTEGER, PRIMARY KEY (user_id, question_id))""")
        cursor = await db.execute("PRAGMA table_info(queues)")
        cols = [row[1] for row in await cursor.fetchall()]
        if not cols:
            await db.execute("""CREATE TABLE queues
                (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, mode TEXT, status TEXT DEFAULT 'waiting', duel_id INTEGER DEFAULT 0, subject TEXT DEFAULT 'aralash')""")
        await db.commit()

        for subj in ["matematika", "fizika", "adabiyot", "ona_tili", "biologiya", "tarix", "huquq"]:
            for diff in ["easy", "hard"]:
                for _ in range(10):
                    dq = generate_subject_question(subj, diff)
                    await db.execute(
                        "INSERT OR IGNORE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?,?,?,?,?,1,?,?)",
                        (dq["question"], dq["opt1"], dq["opt2"], dq["opt3"], dq["opt4"], dq["subject"], dq["difficulty"])
                    )
        await db.commit()

async def get_fresh_question(user_ids: list, subject: str = "aralash", difficulty: str = "easy"):
    ai_q = await fetch_ai_question(subject, difficulty)
    new_q = ai_q if ai_q else generate_subject_question(subject, difficulty)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?,?,?,?,?,1,?,?)",
            (new_q["question"], new_q["opt1"], new_q["opt2"], new_q["opt3"], new_q["opt4"], new_q["subject"], new_q["difficulty"])
        )
        await db.commit()

        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" * len(user_ids))

        if subject == "aralash":
            query = f"SELECT * FROM questions WHERE difficulty = ? AND id NOT IN (SELECT question_id FROM user_seen_questions WHERE user_id IN ({placeholders})) ORDER BY RANDOM() LIMIT 1"
            params = [difficulty] + user_ids
        else:
            query = f"SELECT * FROM questions WHERE subject = ? AND difficulty = ? AND id NOT IN (SELECT question_id FROM user_seen_questions WHERE user_id IN ({placeholders})) ORDER BY RANDOM() LIMIT 1"
            params = [subject, difficulty] + user_ids

        cursor = await db.execute(query, params)
        q = await cursor.fetchone()

        if not q:
            for uid in user_ids:
                await db.execute("DELETE FROM user_seen_questions WHERE user_id = ?", (uid,))
            await db.commit()
            cursor = await db.execute(query, params)
            q = await cursor.fetchone()

        if q:
            for uid in user_ids:
                await db.execute("INSERT OR IGNORE INTO user_seen_questions (user_id, question_id) VALUES (?, ?)", (uid, q["id"]))
            await db.commit()
            return dict(q)

    return new_q

active_timers = {}
youth_sessions = {}
active_duels = {}
CARD_EMOJIS = ["🎁", "🎈", "🌟", "🍎", "🚗", "🐶", "🎸", "💎", "🏀"]

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="👦 Yoshlar uchun (Maktab darsligi • 3 savol)", callback_data="youth_choose_subj")
    builder.button(text="👨 Kattalar uchun (Bellashuv • Yutuqli)", callback_data="adult_intro")
    builder.adjust(1)
    return builder.as_markup()

def subject_menu_kb(target_prefix: str):
    builder = InlineKeyboardBuilder()
    for code, name in SUBJECTS.items():
        builder.button(text=name, callback_data=f"{target_prefix}:{code}")
    builder.button(text="🔙 Orqaga", callback_data="back_main")
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()

def adult_mode_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 2 kishilik bellashuv (12,000 so'm)", callback_data="adult_mode:pay_2")
    builder.button(text="👥 4 kishilik bellashuv (17,000 so'm)", callback_data="adult_mode:pay_4")
    builder.button(text="🔙 Asosiy menyuga qaytish", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()

def get_9_cards_kb(user_id: int):
    session = youth_sessions.get(user_id, {})
    opened = session.get("opened", {})
    builder = InlineKeyboardBuilder()
    for i in range(1, 10):
        if i in opened:
            builder.button(text=opened[i], callback_data="card_already_opened")
        else:
            builder.button(text=f"{CARD_EMOJIS[i - 1]} {i}", callback_data=f"open_card:{i}")
    builder.adjust(3)
    return builder.as_markup()

def admin_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Bitta savol qo'shish", callback_data="admin_add_one")
    builder.button(text="📊 Baza statistikasi", callback_data="admin_stats")
    builder.button(text="🔄 Tarixni tozalash", callback_data="admin_reset_seen")
    builder.button(text="🧹 Navbatni tozalash", callback_data="admin_clear_queue")
    builder.adjust(1)
    return builder.as_markup()

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, role, status) VALUES (?, 'user', 'none')", (message.from_user.id,))
        await db.commit()
    text = f"👋 Salom, <b>{html.escape(message.from_user.first_name or 'Do\'stim')}</b>!\n\n🃏 Joker botiga xush kelibsiz!\n\n👇 O'yin turini tanlang:"
    try:
        await message.answer_photo(photo=JOKER_IMG_URL, caption=text, reply_markup=main_menu(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("🏠 <b>Asosiy menyu:</b>", reply_markup=main_menu(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "youth_choose_subj")
async def youth_choose_subj(callback: CallbackQuery):
    await callback.message.answer("👦 <b>Yoshlar uchun bepul o'yin (Maktab darsliklari)!</b>\n\n👇 Fan tanlang:", reply_markup=subject_menu_kb("ysubj"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("ysubj:"))
async def youth_start_board(callback: CallbackQuery):
    subj = callback.data.split(":")[1]
    user_id = callback.from_user.id
    youth_sessions[user_id] = {"subject": subj, "step": 0, "score": 0, "opened": {}, "current_card": None}
    await callback.message.edit_text(f"🎯 <b>Fan: {SUBJECTS.get(subj, 'Aralash')} (Maktab darsligi)</b>\n🃏 1-kartani tanlang:", reply_markup=get_9_cards_kb(user_id), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "card_already_opened")
async def card_already_opened(callback: CallbackQuery):
    await callback.answer("⚠️ Bu karta ochilgan!", show_alert=True)

@router.callback_query(F.data.startswith("open_card:"))
async def open_card(callback: CallbackQuery):
    user_id = callback.from_user.id
    session = youth_sessions.get(user_id)
    if not session:
        return
    card_num = int(callback.data.split(":")[1])
    if card_num in session["opened"]:
        return await callback.answer("⚠️ Ochilgan!", show_alert=True)
    await callback.answer()
    session["current_card"] = card_num
    q = await get_fresh_question([user_id], subject=session["subject"], difficulty="easy")
    options = [q['opt1'], q['opt2'], q['opt3'], q['opt4']]
    random.shuffle(options)
    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.button(text=opt, callback_data=f"youth_ans:{1 if opt == q['opt1'] else 0}")
    builder.adjust(2)
    await callback.message.edit_text(f"🃏 <b>{card_num}-karta ({session['step'] + 1}/3)</b>\n\n❓ {html.escape(q['question'])}", reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("youth_ans:"))
async def youth_check_answer(callback: CallbackQuery):
    user_id = callback.from_user.id
    session = youth_sessions.get(user_id)
    if not session:
        return
    await callback.answer()
    is_correct = (callback.data.split(":")[1] == "1")
    card_num = session.get("current_card") or 1
    session["step"] += 1
    if is_correct:
        session["score"] += 1
        session["opened"][card_num] = "✅"
    else:
        session["opened"][card_num] = "❌"

    if session["step"] < 3:
        await callback.message.edit_text(f"📊 Natija: {session['step']}/3\n\nKeyingi kartani tanlang:", reply_markup=get_9_cards_kb(user_id), parse_mode="HTML")
    else:
        score = session["score"]
        youth_sessions.pop(user_id, None)
        text = f"🎉 O'yin tugadi! To'g'ri javoblar: {score}/3"
        await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")

@router.callback_query(F.data == "adult_intro")
async def adult_intro(callback: CallbackQuery):
    await callback.message.answer("👨 <b>Kattalar uchun bellashuv</b>\n\n👇 Rejimni tanlang:", reply_markup=adult_mode_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("adult_mode:"))
async def adult_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]
    await state.update_data(mode=mode)
    await callback.message.edit_text("📚 Fanni tanlang:", reply_markup=subject_menu_kb("asubj"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("asubj:"))
async def adult_subj(callback: CallbackQuery, state: FSMContext):
    subj = callback.data.split(":")[1]
    data = await state.get_data()
    mode = data.get("mode", "pay_2")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET pending_mode=?, pending_subject=? WHERE user_id=?", (mode, subj, callback.from_user.id))
        await db.commit()
    await state.set_state(GameStates.waiting_for_receipt)
    await callback.message.edit_text(f"💳 To'lov uchun karta: <code>{KARTA_RAQAMI}</code>\n👤 {KARTA_EGASI}\n\n📸 Chek skrinshotini yuboring:", parse_mode="HTML")
    await callback.answer()

@router.message(F.photo | F.document)
async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
    await message.answer("⏳ Chek adminga yuborildi!")

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🛠 Admin panel:", reply_markup=admin_menu_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        q_count = (await (await db.execute("SELECT COUNT(*) FROM questions")).fetchone())[0]
    await callback.message.edit_text(f"📊 Bazadagi savollar: {q_count} ta", reply_markup=admin_menu_kb(), parse_mode="HTML")
    await callback.answer()

async def handle(request):
    return web.Response(text="Bot 24/7 ishlayapti! 🤖")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080)))
    await site.start()

async def main():
    await init_db()
    bot = Bot(token=TOKEN)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    dp = Dispatcher()
    dp.include_router(router)
    asyncio.create_task(web_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
