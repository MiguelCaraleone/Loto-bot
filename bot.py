# -*- coding: utf-8 -*-
import asyncio
import io
import logging
import os
import random
import secrets
import time
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import aiosqlite
from aiohttp import web

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, BufferedInputFile, URLInputFile
from aiogram.filters import CommandStart, Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Qo'shimcha kutubxonalar bo'lmasa ham bot qulamasligi uchun xavfsiz yuklash:
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# =========================================================================
# ⚙️ SOZLAMALAR VA TOKENLAR RO'YXATI
# =========================================================================
CANDIDATE_TOKENS = [
    "9237388648:AAGv4Di7HjpZqNhMZ1FXPVVa4dRnILAP-h4",
    (os.getenv("BOT_TOKEN") or os.getenv("TOKEN") or "").strip().strip('"').strip("'"),
    "9237388648:AAHqC1UHqbkMUFwEIW-vE59Oj990Zp2Ar4w"
]

raw_admin = (os.getenv("BOSH_ADMIN_ID") or os.getenv("ADMIN_ID") or "1302845749").strip()
BOSH_ADMIN_ID = int(raw_admin) if raw_admin.isdigit() else 1302845749

DB_PATH = "loto_game.db"
KARTA_RAQAMI = "9860 3501 4780 2176"
KARTA_EGASI = "Mamatkulov Izzatillo"
JOKER_IMG_URL = "https://i.ibb.co/RkRvBsHP/file-00000000865082469ff369a93b107407.png"
UZB_TZ = timezone(timedelta(hours=5))

# --- FANLAR RO'YXATI ---
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

# --- FSM HOLATLARI ---
class GameStates(StatesGroup):
    waiting_for_receipt = State()
    admin_send_check = State()
    adding_single_question = State()
    adding_bulk_questions = State()

# =========================================================================
# 📚 OSON (YOSHLAR) VA MURAKKAB (KATTALAR) SAVOLLAR BAZASI
# =========================================================================
ADABIYOT_EASY = [
    ("«O'tkan kunlar» romanining muallifi kim?", "Abdulla Qodiriy", "Cho'lpon", "Oybek", "G'afur G'ulom"),
    ("«Shum bola» qissasini kim yozgan?", "G'afur G'ulom", "Abdulla Qahhor", "Said Ahmad", "O'tkir Hoshimov"),
    ("«Sariq devni minib» asari muallifi kim?", "Xudoyberdi To'xtaboyev", "Pirimqul Qodirov", "Odil Yoqubov", "Mirmuhsin"),
    ("Alisher Navoiyning «Xamsa» asari nechta dostondan iborat?", "5 ta", "4 ta", "6 ta", "3 ta"),
    ("«Dunyoning ishlari» asari muallifi kim?", "O'tkir Hoshimov", "Said Ahmad", "Asqad Muxtor", "Erkin Vohidov"),
    ("«Yulduzli tunlar» romani kim haqida yozilgan?", "Zahiriddin Muhammad Bobur", "Amir Temur", "Mirzo Ulug'bek", "Alisher Navoiy"),
    ("«O'zbegim» qasidasi muallifi kim?", "Erkin Vohidov", "Abdulla Oripov", "Usmon Nosir", "Hamid Olimjon"),
    ("«O'g'ri» va «Bemor» hikoyalari muallifi kim?", "Abdulla Qahhor", "G'afur G'ulom", "Oybek", "Cho'lpon")
]

ADABIYOT_HARD = [
    ("«Kecha va kunduz» romanining birinchi qismi qanday nomlanadi?", "Bahor", "Yoz", "Kuz", "Qish"),
    ("Alisher Navoiyning «Lison ut-tayr» dostonida qushlar yetakchisi qaysi qush?", "Hudhud", "Semurg'", "Bulbul", "Burgut"),
    ("Odil Yoqubovning «Ulug'bek xazinasi» romanida Ulug'bekning shogirdi kim?", "Ali Qushchi", "Qozizoda Rumiy", "G'iyosiddin Jamshid", "Mavlono Muhiddin"),
    ("O'tkir Hoshimovning «Ikki eshik orasi» romanida Qora ammaning asl ismi nima?", "Robiya", "Ra'no", "Zebi", "Kumush"),
    ("Cho'lponning «Kecha va kunduz» romanida Razzoq so'fining qizi kim?", "Zebi", "Maryam", "Xadicha", "Kumush"),
    ("Abdulla Qodiriyning «Mehrobdan chayon» romanida bosh qahramonlar kimlar?", "Anvar va Ra'no", "Otabek va Kumush", "Yo'lchi va Gulnor", "Saidiy va Munisxon"),
    ("Pirimqul Qodirovning «Avlodlar dovoni» romanida Boburning qaysi avlodi tarixi aks etgan?", "Humoyun va Akbar", "Komron Mirzo", "Askariy Mirzo", "Hindol Mirzo"),
    ("Oybekning «Qutlug' qon» romanidagi bosh qahramon kim?", "Yo'lchi", "Mirzakarimboy", "Otabek", "Tantiboyvachcha")
]

TARIX_EASY = [
    ("Amir Temur qaysi yilda tavallud topgan?", "1336-yil", "1441-yil", "1483-yil", "1394-yil"),
    ("O'zbekiston Respublikasi qachon mustaqillikka erishgan?", "1991-yil", "1990-yil", "1992-yil", "1989-yil"),
    ("Amir Temur davlatining poytaxti qaysi shahar bo'lgan?", "Samarqand", "Buxoro", "Toshkent", "Xiva"),
    ("Qadimgi Misr podsholari nima deb atalgan?", "Fir'avn", "Imperator", "Sulton", "Xon"),
    ("Birinchi jahon urushi qaysi yilda boshlangan?", "1914-yil", "1918-yil", "1939-yil", "1941-yil"),
    ("O'zbekistonning milliy valyutasi — so'm qachon muomalaga kiritilgan?", "1994-yil", "1991-yil", "1992-yil", "1996-yil"),
    ("Mirzo Ulug'bek rasadxonasi qaysi shaharda qurilgan?", "Samarqand", "Buxoro", "Shahrisabz", "Hirot")
]

TARIX_HARD = [
    ("Amir Temur va Boyazid Yildirim o'rtasidagi Anqara jangi qachon bo'lib o'tgan?", "1402-yil 20-iyul", "1395-yil 15-aprel", "1365-yil 22-may", "1405-yil 18-fevral"),
    ("Ilyosxo'ja va Amir Temur o'rtasidagi «Loy jangi» qachon bo'lgan?", "1365-yil 22-may", "1370-yil 10-aprel", "1360-yil 15-mart", "1388-yil 12-iyun"),
    ("Jaloliddin Manguberdi mo'g'ullar ustidan g'alaba qozongan Parvon jangi qaysi yilda bo'lgan?", "1221-yil", "1219-yil", "1225-yil", "1231-yil"),
    ("O'zbekiston Respublikasi BMTga qachon a'zo bo'lgan?", "1992-yil 2-mart", "1991-yil 18-noyabr", "1992-yil 8-dekabr", "1993-yil 10-yanvar"),
    ("Aleksandr Makedonskiyga qarshi Spitamen qo'zg'oloni qachon boshlangan?", "Mil. avv. 329-yil", "Mil. avv. 330-yil", "Mil. avv. 327-yil", "Mil. avv. 323-yil"),
    ("Toshkent shahrida Markaziy Osiyodagi ilk metropoliten qachon ishga tushirilgan?", "1977-yil", "1966-yil", "1980-yil", "1972-yil"),
    ("Zahiriddin Muhammad Bobur Hindistonda Boburiylar saltanatiga qachon asos solgan?", "1526-yil", "1512-yil", "1530-yil", "1504-yil")
]

BIOLOGIYA_EASY = [
    ("O'simliklarda fotosintez jarayoni qaysi qismda boradi?", "Bargda (Xloroplastda)", "Ildizda", "Po'stloqda", "Urug'da"),
    ("Inson tanasidagi eng katta organ qaysi?", "Teri", "Yurak", "O'pka", "Buyrak"),
    ("Inson yuragi nechta kameradan iborat?", "4 ta", "2 ta", "3 ta", "5 ta"),
    ("Qaysi hayvon sut emizuvchilar sinfiga kiradi?", "Ko'k kit", "Akula", "Timsoh", "Toshbaqa"),
    ("Quyosh nuridan inson organizmida qaysi vitamin hosil bo'ladi?", "D vitamini", "C vitamini", "A vitamini", "B12 vitamini"),
    ("Voyaga yetgan inson skeletida nechta suyak bo'ladi?", "206 ta", "150 ta", "300 ta", "256 ta"),
    ("Qushlarni o'rganuvchi biologiya bo'limi nima deyiladi?", "Ornitologiya", "Ixtiologiya", "Mikologiya", "Botanika")
]

BIOLOGIYA_HARD = [
    ("Hujayrada oqsil biosintezi qaysi organoidda amalga oshadi?", "Ribosoma", "Lizosoma", "Golji majmuasi", "Mitoxondriya"),
    ("Hujayraning «energiya stansiyasi» (ATF sintezlovchi) qaysi organoid?", "Mitoxondriya", "Ribosoma", "Endoplazmatik to'r", "Sentrosoma"),
    ("Odamning somatik (tana) hujayralarida nechta xromosoma bo'ladi?", "46 ta (23 juft)", "23 ta", "48 ta (24 juft)", "44 ta (22 juft)"),
    ("Qonning ivish jarayonida ishtirok etuvchi shaklli elementlar qaysi?", "Trombotsitlar", "Eritrotsitlar", "Leykotsitlar", "Limfotsitlar"),
    ("DNK tarkibiga kirmaydigan, faqat RNKda uchraydigan azotli asos qaysi?", "Uratsil (U)", "Timin (T)", "Adenin (A)", "Guanin (G)"),
    ("Odamda shabko'rlik kasalligi qaysi vitamin yetishmasligidan kelib chiqadi?", "A vitamini (Retinol)", "D vitamini (Kalsiferol)", "C vitamini", "K vitamini"),
    ("Zamburug'lar dunyosini o'rganuvchi biologiya bo'limi qanday ataladi?", "Mikologiya", "Briologiya", "Algologiya", "Entomologiya")
]

ONA_TILI_EASY = [
    ("«Kim? Nima? Qayer?» so'roqlariga javob bo'luvchi so'z turkumi qaysi?", "Ot", "Sifat", "Fe'l", "Son"),
    ("Ma'nosi bir-biriga qarama-qarshi bo'lgan so'zlar nima deyiladi?", "Antonimlar", "Sinonimlar", "Omonimlar", "Paronimlar"),
    ("O'zbek tiliga Davlat tili maqomi qachon berilgan?", "1989-yil 21-oktabr", "1991-yil 1-sentabr", "1992-yil 8-dekabr", "1995-yil 24-avgust"),
    ("«Chiroyli, katta, qizil» so'zlari qaysi so'z turkumiga kiradi?", "Sifat", "Ot", "Ravish", "Olmosh"),
    ("Gapning eng asosiy bosh bo'laklari qaysilar?", "Ega va kesim", "Hol va to'ldiruvchi", "Aniqlovchi va hol", "To'ldiruvchi va ega"),
    ("Shakli bir xil, ammo ma'nosi har xil so'zlar nima deyiladi?", "Omonimlar", "Sinonimlar", "Antonimlar", "Ibora")
]

ONA_TILI_HARD = [
    ("Qaysi qatordagi so'z imlo qoidalariga ko'ra to'g'ri yozilgan?", "Taassurot", "Tassurot", "Taasurot", "Tasurot"),
    ("Talaffuzi yaqin, ammo ma'nosi va yozilishi farq qiluvchi so'zlar (asr - asir) nima deyiladi?", "Paronimlar", "Omonimlar", "Sinonimlar", "Arxaizmlar"),
    ("Qaysi qatorda barcha so'zlar to'g'ri yozilgan?", "Munosabat, xushomad, tafakkur", "Munosobat, hushomad, tafakkur", "Munasabat, xushomat, tafakur", "Munosabat, hushomat, tafakkur"),
    ("«O'qigan bola» birikmasidagi «o'qigan» so'zi fe'lning qaysi vazifa shakliga kiradi?", "Sifatdosh", "Ravishdosh", "Harakat nomi", "Sof fe'l"),
    ("Ko'makchi fe'lli so'z qo'shilmasini toping:", "O'qib chiqdi", "Sotib oldi", "Qarab qoldi", "Barchasi to'g'ri"),
    ("Gapda «Qanday qilib? Qay tarzda?» so'roqlariga javob bo'luvchi bo'lak qaysi?", "Ravish holi", "Sifatlovchi aniqlovchi", "Vositali to'ldiruvchi", "Maqsad holi")
]

HUQUQ_EASY = [
    ("O'zbekiston Respublikasining Konstitutsiyasi kuni qachon nishonlanadi?", "8-dekabr", "1-sentabr", "21-oktabr", "18-noyabr"),
    ("O'zbekistonda fuqarolar necha yoshdan saylash huquqiga ega bo'ladilar?", "18 yoshdan", "16 yoshdan", "21 yoshdan", "25 yoshdan"),
    ("O'zbekistonda davlat hokimiyatining yagona manbai kim?", "Xalq", "Vazirlar Mahkamasi", "Oliy sud", "Hokimliklar"),
    ("Bola huquqlari to'g'risidagi konvensiyaga ko'ra necha yoshgacha bo'lgan shaxs bola hisoblanadi?", "18 yoshga to'lmagan", "16 yoshga to'lmagan", "14 yoshga to'lmagan", "12 yoshga to'lmagan"),
    ("O'zbekiston Davlat bayrog'i qachon qabul qilingan?", "1991-yil 18-noyabr", "1992-yil 2-iyul", "1992-yil 10-dekabr", "1991-yil 31-avgust"),
    ("O'zbekiston Respublikasida qonun chiqaruvchi oliy organ qaysi?", "Oliy Majlis", "Vazirlar Mahkamasi", "Oliy sud", "Adliya vazirligi")
]

HUQUQ_HARD = [
    ("Yangi tahrirdagi O'zbekiston Respublikasi Konstitutsiyasi nechta bo'lim, bob va moddadan iborat?", "6 bo'lim, 27 bob, 155 modda", "6 bo'lim, 26 bob, 128 modda", "5 bo'lim, 25 bob, 150 modda", "7 bo'lim, 28 bob, 160 modda"),
    ("Yangi tahrirdagi O'zbekiston Konstitutsiyasi umumxalq referendumida qachon qabul qilindi?", "2023-yil 30-aprel", "2022-yil 8-dekabr", "2023-yil 1-may", "2024-yil 1-yanvar"),
    ("O'zbekiston Respublikasi Prezidenti necha yil muddatga saylanadi?", "7 yil", "5 yil", "4 yil", "6 yil"),
    ("Mehnat kodeksiga ko'ra, xodim uchun normal ish vaqti haftasiga necha soatdan oshmasligi shart?", "40 soatdan", "48 soatdan", "36 soatdan", "45 soatdan"),
    ("Jinoyat kodeksiga ko'ra, umumiy jinoiy javobgarlik necha yoshdan boshlanadi?", "16 yoshdan", "18 yoshdan", "14 yoshdan", "15 yoshdan"),
    ("Oliy Majlis Qonunchilik palatasi nechta deputatdan iborat?", "150 nafar", "100 nafar", "120 nafar", "65 nafar"),
    ("Oila kodeksiga muvofiq, O'zbekistonda erkaklar va ayollar uchun nikoh yoshi necha yosh?", "18 yosh", "17 yosh", "20 yosh", "19 yosh")
]

def generate_subject_question(subject: str, difficulty: str = "easy"):
    if subject == "aralash" or subject not in SUBJECTS:
        subject = random.choice(["matematika", "fizika", "adabiyot", "ona_tili", "biologiya", "tarix", "huquq"])

    if subject == "matematika":
        if difficulty == "easy":
            turi = random.choice(["add_sub", "mult"])
            if turi == "add_sub":
                a, b, c = random.randint(25, 90), random.randint(10, 40), random.randint(5, 30)
                ans = a + b - c
                q_text = f"📐 Matematika: Hisoblang: {a} + {b} - {c} = ?"
            else:
                a, b, c = random.randint(4, 12), random.randint(3, 9), random.randint(5, 25)
                ans = a * b + c
                q_text = f"📐 Matematika: Hisoblang: {a} × {b} + {c} = ?"
        else:
            turi = random.choice(["tenglama", "foiz", "kvadrat"])
            if turi == "tenglama":
                x = random.randint(6, 19)
                a = random.randint(4, 12)
                b = random.randint(15, 60)
                res = a * x - b
                ans = x
                q_text = f"📐 Matematika: Tenglamani yeching: {a}x - {b} = {res}"
            elif turi == "foiz":
                son = random.choice([200, 300, 400, 500, 600, 800, 1200])
                foiz = random.choice([15, 25, 35, 45, 65])
                ans = (son * foiz) // 100
                q_text = f"📐 Matematika: {son} sonining {foiz}% ini toping."
            else:
                a = random.randint(12, 24)
                b = random.randint(4, 9)
                c = random.randint(5, 12)
                ans = (a * a) - (b * c)
                q_text = f"📐 Matematika: Hisoblang: {a}² - ({b} × {c}) = ?"

        wrongs = set()
        while len(wrongs) < 3:
            w = ans + random.choice([-12, -8, -5, -3, -2, -1, 1, 2, 3, 5, 8, 12])
            if w != ans and w > 0:
                wrongs.add(str(w))
        w_list = list(wrongs)
        return {"question": q_text, "opt1": str(ans), "opt2": w_list[0], "opt3": w_list[1], "opt4": w_list[2], "correct_opt": 1, "subject": "matematika", "difficulty": difficulty}

    elif subject == "fizika":
        if difficulty == "easy":
            v = random.choice([40, 50, 60, 70, 80, 90])
            t = random.randint(2, 5)
            s = v * t
            ans = f"{v} km/soat"
            wrongs = [f"{v + 10} km/soat", f"{max(20, v - 15)} km/soat", f"{v + 20} km/soat"]
            q_text = f"⚡ Fizika: Avtomobil {s} km masofani {t} soatda bosib o'tdi. Tezligini toping."
        else:
            i_val = random.randint(3, 12)
            r_val = random.randint(5, 25)
            u_val = i_val * r_val
            ans = f"{r_val} Om"
            wrongs = [f"{r_val + 4} Om", f"{max(2, r_val - 3)} Om", f"{r_val * 2} Om"]
            q_text = f"⚡ Fizika: Kuchlanishi {u_val} V bo'lgan o'tkazgichdan {i_val} A tok o'tmoqda. Qarshilikni (R) toping."
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
    return {"question": f"{prefix}: {q_raw}", "opt1": o1, "opt2": o2, "opt3": o3, "opt4": o4, "correct_opt": 1, "subject": subject, "difficulty": difficulty}

# =========================================================================
# 🗄 BAZA AMALLARI (SQLite + aiosqlite)
# =========================================================================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS vaucherlar (
            kod TEXT PRIMARY KEY,
            user_id INTEGER,
            foiz INTEGER,
            status TEXT DEFAULT 'faol',
            berilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ishlatilgan_vaqt TIMESTAMP NULL
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS kassirlar (
            user_id INTEGER PRIMARY KEY,
            ism TEXT,
            qoshilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS takliflar (
            token TEXT PRIMARY KEY,
            status TEXT DEFAULT 'faol'
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT,
            status TEXT,
            pending_mode TEXT DEFAULT 'pay_2',
            pending_subject TEXT DEFAULT 'aralash'
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS queues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mode TEXT,
            status TEXT DEFAULT 'waiting',
            duel_id INTEGER DEFAULT 0,
            subject TEXT DEFAULT 'aralash'
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT UNIQUE,
            opt1 TEXT,
            opt2 TEXT,
            opt3 TEXT,
            opt4 TEXT,
            correct_opt INTEGER,
            subject TEXT DEFAULT 'aralash',
            difficulty TEXT DEFAULT 'easy'
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS user_seen_questions (
            user_id INTEGER,
            question_id INTEGER,
            PRIMARY KEY (user_id, question_id)
        )""")
        await db.commit()

        for subj in ["matematika", "fizika", "adabiyot", "ona_tili", "biologiya", "tarix", "huquq"]:
            for diff in ["easy", "hard"]:
                for _ in range(8):
                    dq = generate_subject_question(subj, diff)
                    await db.execute(
                        "INSERT OR IGNORE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?,?,?,?,?,1,?,?)",
                        (dq["question"], dq["opt1"], dq["opt2"], dq["opt3"], dq["opt4"], dq["subject"], dq["difficulty"])
                    )
        await db.commit()

async def get_fresh_question(user_ids: list, subject: str = "aralash", difficulty: str = "easy"):
    new_q = generate_subject_question(subject, difficulty)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?,?,?,?,?,1,?,?)",
            (new_q["question"], new_q["opt1"], new_q["opt2"], new_q["opt3"], new_q["opt4"], new_q["subject"], new_q["difficulty"])
        )
        await db.commit()

        if subject in ("matematika", "fizika") or random.random() < 0.45:
            return new_q

        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" * len(user_ids))

        if subject == "aralash":
            query = f"""
                SELECT * FROM questions 
                WHERE difficulty = ? AND id NOT IN (
                    SELECT question_id FROM user_seen_questions WHERE user_id IN ({placeholders})
                )
                ORDER BY RANDOM() LIMIT 1
            """
            params = [difficulty] + user_ids
        else:
            query = f"""
                SELECT * FROM questions 
                WHERE subject = ? AND difficulty = ? AND id NOT IN (
                    SELECT question_id FROM user_seen_questions WHERE user_id IN ({placeholders})
                )
                ORDER BY RANDOM() LIMIT 1
            """
            params = [subject, difficulty] + user_ids

        cursor = await db.execute(query, params)
        q = await cursor.fetchone()

        if q:
            for uid in user_ids:
                await db.execute(
                    "INSERT OR IGNORE INTO user_seen_questions (user_id, question_id) VALUES (?, ?)",
                    (uid, q["id"])
                )
            await db.commit()
            return dict(q)

    return new_q

async def is_kassir(user_id: int) -> bool:
    if user_id == BOSH_ADMIN_ID:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM kassirlar WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            return res is not None

async def kod_saqlash(kod: str, user_id: int, foiz: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO vaucherlar (kod, user_id, foiz, status) VALUES (?, ?, ?, 'faol')",
            (kod, user_id, foiz)
        )
        await db.commit()

async def kodni_tekshirish(kod: str):
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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

# =========================================================================
# 🎨 QR-KOD VA EXCEL (KUTUBXONA BO'LMASA HAM ISHLAYDIGAN VARIANT)
# =========================================================================
def qr_kod_yaratish(havola: str):
    if HAS_QRCODE:
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(havola)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return BufferedInputFile(buffer.getvalue(), filename="vaucher_qr.png")
    else:
        url = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&margin=10&data={quote(havola)}"
        return URLInputFile(url, filename="vaucher_qr.png")

async def generate_report_file():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT kod, user_id, foiz, status, berilgan_vaqt, ishlatilgan_vaqt 
            FROM vaucherlar 
            ORDER BY berilgan_vaqt DESC
        """) as cursor:
            rows = await cursor.fetchall()

    if HAS_OPENPYXL:
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
        return BufferedInputFile(file_stream.getvalue(), filename="vaucherlar_hisoboti.xlsx")
    else:
        csv_lines = ["\ufeffVaucher Kodi;Telegram User ID;Chegirma (%);Holati;Berilgan Vaqti;Ishlatilgan Vaqti"]
        for row_data in rows:
            kod, user_id, foiz, status, berilgan, ishlatilgan = row_data
            status_text = "Ishlatilgan" if status == "ishlatildi" else "Faol"
            csv_lines.append(f"{kod};{user_id};{foiz}%;{status_text};{berilgan};{ishlatilgan or '—'}")
        csv_bytes = "\n".join(csv_lines).encode("utf-8")
        return BufferedInputFile(csv_bytes, filename="vaucherlar_hisoboti.csv")

# =========================================================================
# 🔘 XOTIRA VA KLAVIATURALAR
# =========================================================================
active_timers = {}
youth_sessions = {}
active_duels = {}
CARD_EMOJIS = ["🎁", "🎈", "🌟", "🍎", "🚗", "🐶", "🎸", "💎", "🏀"]

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="👦 Yoshlar uchun (Bepul • 3 savol)", callback_data="youth_choose_subj")
    builder.button(text="👨 Kattalar uchun (Bellashuv • Yutuqli)", callback_data="adult_intro")
    builder.adjust(1)
    return builder.as_markup()

def admin_main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Do‘kon Chegirmalar Statistikasi", callback_data="admin_run_stat")
    builder.button(text="📁 Excel hisobot yuklab olish", callback_data="admin_run_excel")
    builder.button(text="🔗 Yangi kassir taklif havolasi", callback_data="admin_run_kassir_link")
    builder.button(text="👥 Ulangan kassirlar ro‘yxati", callback_data="admin_run_kassirlar")
    builder.button(text="➕ Savollar va O‘yin boshqaruvi", callback_data="admin_questions_panel")
    builder.button(text="🎮 Oddiy foydalanuvchi sifatida o‘ynash", callback_data="user_mode_start")
    builder.adjust(1)
    return builder.as_markup()

def admin_questions_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Bitta savol qo'shish", callback_data="admin_add_one")
    builder.button(text="📥 Ko'p savol qo'shish (Ro'yxat)", callback_data="admin_add_bulk")
    builder.button(text="⚡ Avto-generatordan 50 ta qo'shish", callback_data="admin_auto_gen")
    builder.button(text="🔄 Savollar tarixini tozalash", callback_data="admin_reset_seen")
    builder.button(text="🧹 Navbatni tozalash (Reset)", callback_data="admin_clear_queue")
    builder.button(text="📈 O'yin va Savollar statistikasi", callback_data="admin_stats")
    builder.button(text="🔙 Admin menyuga qaytish", callback_data="back_admin_main")
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
            emoji = CARD_EMOJIS[i - 1]
            builder.button(text=f"{emoji} {i}", callback_data=f"open_card:{i}")
    builder.adjust(3)
    return builder.as_markup()

# =========================================================================
# 🤖 START, KASSIR SKANERI VA ADMIN MENYUSI
# =========================================================================
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    await state.clear()
    args = command.args
    user_id = message.from_user.id

    # 1. KASSIR QR-KODNI SKANER QILGANDA
    if args and args.startswith("CH_"):
        if not await is_kassir(user_id):
            await message.answer("⚠️ Bu QR-kod faqat do‘kon kassirlari tomonidan skanerlanishi mumkin!")
            return

        holat, qiymat = await kodni_tekshirish(args)
        if holat == "tasdiqlandi":
            await message.answer(
                f"✅ <b>CHEGIRMA TASDIQLANDI!</b>\n\n"
                f"🎟 Kod: <code>{args}</code>\n"
                f"🎁 Chegirma: <b>{qiymat}%</b>\n"
                f"🔒 Holat: Kod bazada yopildi (qayta ishlatib bo‘lmaydi).",
                parse_mode="HTML"
            )
        elif holat == "oldin_ishlatilgan":
            await message.answer(
                f"❌ <b>XATOLIK: BU KOD AVVAL ISHLATILGAN!</b>\n\n"
                f"🎟 Kod: <code>{args}</code>\n"
                f"🕒 Ishlatilgan vaqt: {qiymat}\n"
                f"⛔️ Mijozga chegirma bermang!",
                parse_mode="HTML"
            )
        else:
            await message.answer("🚫 Bunday chegirma kodi tizimda topilmadi.")
        return

    # 2. TAKLIF HAVOLASI ORQALI KASSIR ULANGANDA
    if args and args.startswith("kassir_"):
        token = args.replace("kassir_", "")
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT status FROM takliflar WHERE token = ?", (token,)) as cursor:
                res = await cursor.fetchone()

            if res and res[0] == "faol":
                await db.execute("UPDATE takliflar SET status = 'ishlatildi' WHERE token = ?", (token,))
                await db.execute(
                    "INSERT OR REPLACE INTO kassirlar (user_id, ism) VALUES (?, ?)",
                    (user_id, message.from_user.full_name)
                )
                await db.commit()

                await message.answer("🎉 <b>Tabriklaymiz! Siz muvaffaqiyatli kassir sifatida tizimga ulandingiz.</b>\nEndi mijozlarning QR-kodini kamerangiz orqali tekshirishingiz mumkin.", parse_mode="HTML")
                await bot.send_message(
                    chat_id=BOSH_ADMIN_ID,
                    text=f"🔔 <b>Yangi kassir ulandi:</b> {html.escape(message.from_user.full_name)} (ID: <code>{user_id}</code>)",
                    parse_mode="HTML"
                )
                return
            else:
                await message.answer("❌ Ushbu taklif havolasi eskirgan yoki avval ishlatilgan!")
                return

    # 3. AGAR BOSH ADMIN /start BOSSA:
    if user_id == BOSH_ADMIN_ID:
        await message.answer(
            f"👑 <b>Xush kelibsiz, Bosh Admin!</b> (ID: <code>{user_id}</code>)\n\n"
            f"Barcha chegirmalar, kassirlar va o‘yin tizimi nazoratingizda. Bo‘limni tanlang:",
            reply_markup=admin_main_kb(),
            parse_mode="HTML"
        )
        return

    # 4. AGAR KASSIR /start BOSSA:
    if await is_kassir(user_id):
        kassir_kb = InlineKeyboardBuilder()
        kassir_kb.button(text="📊 Do‘kon Statistikasi", callback_data="admin_run_stat")
        kassir_kb.button(text="📁 Hisobot yuklab olish", callback_data="admin_run_excel")
        kassir_kb.button(text="🎮 O‘yin menyusiga o‘tish", callback_data="user_mode_start")
        kassir_kb.adjust(1)
        await message.answer(
            f"💼 <b>Xush kelibsiz, Kassir {html.escape(message.from_user.first_name)}!</b>\n\n"
            f"Mijoz QR-kodini tekshirish uchun telefon kamerangiz orqali QR-kodni skaner qiling:",
            reply_markup=kassir_kb.as_markup(),
            parse_mode="HTML"
        )
        return

    # 5. ODDIY FOYDALANUVCHI UCHUN MENYU:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, role, status, pending_mode, pending_subject) VALUES (?, 'user', 'none', 'pay_2', 'aralash')",
            (user_id,)
        )
        await db.commit()

    safe_name = html.escape(message.from_user.first_name or "Do'stim")
    text = (
        f"👋 Salom, <b>{safe_name}</b>!\n\n"
        f"🃏 Men <b>Joker</b>! Intellektual o'yinimga xush kelibsiz!\n\n"
        f"👦 <b>Yoshlar bo'limi:</b> 9 ta kartadan 3 tasini ochib, savollarga javob bering va barcha mahsulotlarga <b>5% yoki 3% lik QR-kod chegirma</b> yuting!\n"
        f"👨 <b>Kattalar bellashuvi:</b> 2 yoki 4 kishi o'rtasida 3 ta savollik tezkor duelda qatnashib, <b>pul yutuqlarini</b> qo'lga kiriting!\n\n"
        f"👇 O'yin turini tanlang:"
    )
    try:
        await message.answer_photo(photo=JOKER_IMG_URL, caption=text, reply_markup=main_menu(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

@router.message(Command("id"))
async def cmd_my_id(message: Message):
    await message.answer(f"🆔 Sizning Telegram ID raqamingiz: <code>{message.from_user.id}</code>", parse_mode="HTML")

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("🏠 <b>Asosiy menyu:</b>", reply_markup=main_menu(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_admin_main")
async def back_admin_main(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    await state.clear()
    await callback.message.edit_text("👑 <b>Bosh Admin Paneli:</b>", reply_markup=admin_main_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "user_mode_start")
async def run_user_mode_cb(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🏠 <b>O‘yin turi menyusi:</b>", reply_markup=main_menu(), parse_mode="HTML")

# =========================================================================
# 👦 YOSHLAR O'YINI (9 KARTA + 3 SAVOL + 5% VA 3% QR-KOD VAUCHER)
# =========================================================================
@router.callback_query(F.data == "youth_choose_subj")
async def youth_choose_subj(callback: CallbackQuery):
    text = (
        "👦 <b>Yoshlar uchun bepul chegirmali o'yin!</b>\n\n"
        "📋 <b>Qoida:</b> 9 ta yashirin kartadan <b>3 tasini</b> tanlaysiz:\n"
        "• 3 tadan 3 ta topsangiz ➡️ Barcha mahsulotlarga <b>5% CHEGIRMA!</b>\n"
        "• 3 tadan 2 ta topsangiz ➡️ Barcha mahsulotlarga <b>3% CHEGIRMA!</b>\n\n"
        "💰 <b>Xarid misollari (5% chegirma bilan):</b>\n"
        "• 10 000 so‘mlik xarid uchun ➡️ <b>9 500 so‘m to‘laysiz</b>\n"
        "• 40 000 so‘mlik xarid uchun ➡️ <b>38 000 so‘m to‘laysiz</b>\n\n"
        "👇 <b>Savollar qaysi fandan bo'lsin? Tanlang:</b>"
    )
    await callback.message.answer(text, reply_markup=subject_menu_kb("ysubj"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("ysubj:"))
async def youth_start_board(callback: CallbackQuery):
    subj = callback.data.split(":")[1]
    user_id = callback.from_user.id
    youth_sessions[user_id] = {
        "subject": subj,
        "step": 0,
        "score": 0,
        "opened": {},
        "current_card": None
    }
    subj_name = SUBJECTS.get(subj, "🌐 Aralash")
    text = (
        f"🎯 <b>Fan: {subj_name}</b>\n"
        f"🃏 Quyidagi 9 ta kartadan <b>1-kartani</b> tanlang (0/3):"
    )
    await callback.message.edit_text(text, reply_markup=get_9_cards_kb(user_id), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "card_already_opened")
async def card_already_opened(callback: CallbackQuery):
    await callback.answer("⚠️ Bu kartani ochib bo'lgansiz! Boshqa kartani tanlang.", show_alert=True)

@router.callback_query(F.data.startswith("open_card:"))
async def open_card(callback: CallbackQuery):
    user_id = callback.from_user.id
    session = youth_sessions.get(user_id)
    if not session:
        youth_sessions[user_id] = {"subject": "aralash", "step": 0, "score": 0, "opened": {}, "current_card": None}
        session = youth_sessions[user_id]

    card_num = int(callback.data.split(":")[1])
    if card_num in session["opened"]:
        return await callback.answer("⚠️ Bu karta ochilgan!", show_alert=True)

    await callback.answer()
    session["current_card"] = card_num
    subj = session["subject"]
    current_q_num = session["step"] + 1

    q = await get_fresh_question([user_id], subject=subj, difficulty="easy")
    options = [q['opt1'], q['opt2'], q['opt3'], q['opt4']]
    random.shuffle(options)
    correct_text = q[f"opt{q['correct_opt']}"]

    builder = InlineKeyboardBuilder()
    for opt in options:
        is_correct = 1 if opt == correct_text else 0
        builder.button(text=opt, callback_data=f"youth_ans:{is_correct}")
    builder.adjust(2)

    text = (
        f"🃏 <b>{card_num}-karta ochildi! ({current_q_num}/3-savol)</b>\n\n"
        f"❓ {html.escape(q['question'])}\n\n"
        f"⏳ Javob berish uchun <b>20 soniya</b> vaqt:"
    )
    msg = await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

    if user_id in active_timers:
        active_timers[user_id].cancel()
    active_timers[user_id] = asyncio.create_task(youth_timeout(msg, user_id, callback.bot))

async def youth_timeout(message: Message, user_id: int, bot: Bot):
    try:
        await asyncio.sleep(20.0)
        session = youth_sessions.get(user_id)
        if not session:
            return
        card_num = session.get("current_card") or 1
        session["opened"][card_num] = "⏳"
        session["step"] += 1
        await proceed_youth_game(message, user_id, "⏳ <b>Vaqt tugadi!</b>", bot)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
    finally:
        active_timers.pop(user_id, None)

@router.callback_query(F.data.startswith("youth_ans:"))
async def youth_check_answer(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if user_id in active_timers:
        active_timers[user_id].cancel()
        active_timers.pop(user_id, None)

    session = youth_sessions.get(user_id)
    if not session:
        return await callback.message.edit_text("🏠 Asosiy menyu:", reply_markup=main_menu())

    await callback.answer()
    is_correct = (callback.data.split(":")[1] == "1")
    card_num = session.get("current_card") or 1
    session["step"] += 1

    if is_correct:
        session["score"] += 1
        session["opened"][card_num] = "✅"
        status_line = "✅ <b>Barakalla, to'g'ri javob!</b>"
    else:
        session["opened"][card_num] = "❌"
        status_line = "❌ <b>Afsuski, xato javob!</b>"

    await proceed_youth_game(callback.message, user_id, status_line, bot)

async def proceed_youth_game(message: Message, user_id: int, status_line: str, bot: Bot):
    session = youth_sessions.get(user_id)
    if not session:
        return
    step = session["step"]
    score = session["score"]
    subj_name = SUBJECTS.get(session["subject"], "🌐 Aralash")

    if step < 3:
        text = (
            f"{status_line}\n\n"
            f"📚 Fan: <b>{subj_name}</b>\n"
            f"📊 Natija: <b>{step}/3 savol</b> (To'g'ri: <b>{score} ta</b>)\n\n"
            f"👇 <b>Navbatdagi ({step + 1}-chi) kartani tanlang:</b>"
        )
        await message.edit_text(text, reply_markup=get_9_cards_kb(user_id), parse_mode="HTML")
    else:
        youth_sessions.pop(user_id, None)
        if score >= 2:
            foiz = 5 if score == 3 else 3
            unikal_kod = f"CH_{foiz}_{user_id}_{random.randint(1000, 9999)}"
            await kod_saqlash(unikal_kod, user_id, foiz)

            bot_me = await bot.get_me()
            skaner_havolasi = f"https://t.me/{bot_me.username}?start={unikal_kod}"
            qr_rasm = qr_kod_yaratish(skaner_havolasi)

            tolov_10 = 10000 - (10000 * foiz // 100)
            tolov_40 = 40000 - (40000 * foiz // 100)

            caption_text = (
                f"{status_line}\n\n"
                f"🎉 <b>TABRIKLAYMIZ! Siz 3 tadan {score} ta savolni to‘g‘ri topdingiz!</b>\n\n"
                f"🎁 Yutug‘ingiz: Barcha mahsulotlar uchun <b>{foiz}% CHEGIRMA VAUCHERI!</b>\n\n"
                f"💰 <b>Xarid misollari:</b>\n"
                f"• 10 000 so‘mlik xarid uchun ➡️ <b>{tolov_10:,} so‘m to‘laysiz</b>\n"
                f"• 40 000 so‘mlik xarid uchun ➡️ <b>{tolov_40:,} so‘m to‘laysiz</b>\n\n"
                f"🎟 <b>Vaucher kodi:</b> <code>{unikal_kod}</code>\n"
                f"📍 Urgut tumanidagi 3-umumta'lim maktabi ro'parasidagi <b>Super Mini Market</b>da ushbu <b>QR-kodni kassirga ko‘rsating!</b>\n"
                f"<i>(Vaucher faqat 1 marta amal qiladi)</i>"
            )
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await bot.send_photo(chat_id=user_id, photo=qr_rasm, caption=caption_text, reply_markup=main_menu(), parse_mode="HTML")
            except Exception:
                await bot.send_message(chat_id=user_id, text=caption_text, reply_markup=main_menu(), parse_mode="HTML")
        else:
            text = (
                f"{status_line}\n\n"
                f"📉 <b>Natijangiz: 3 tadan {score} ta to'g'ri.</b>\n\n"
                f"Chegirma olish uchun kamida 2 ta savolga to‘g‘ri javob berish kerak.\n"
                f"🎰 Senga Jokerning xabari bor:\n"
                f"<i>«Bu qovoqni ishlat bolakay! Yana bir bor urinib ko'r!»</i> 🎃"
            )
            await message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")

# =========================================================================
# 👨 KATTALAR BELLASHUVI (TUSHUNCHA + FAN TANLASH + 3 SAVOLLIK DUEL)
# =========================================================================
@router.callback_query(F.data == "adult_intro")
async def adult_intro_handler(callback: CallbackQuery):
    text = (
        "👨 <b>KATTALAR UCHUN BELLASHUV — QOIDALAR VA TUSHUNCHA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>O'yin qanday o'ynaladi?</b>\n"
        "1️⃣ O'yin turini (<b>2 yoki 4 kishilik</b>) va o'zingiz yaxshi biladigan <b>fanni</b> tanlaysiz.\n"
        "2️⃣ Karta raqamiga to'lov qilib, chek skrinshotini botga yuborasiz.\n"
        "3️⃣ Admin chekni tasdiqlagach, navbatga qo'shilasiz. Raqiblar yig'ilishi bilan <b>5 soniyalik ogohlantirish</b> beriladi va bellashuv boshlanadi!\n\n"
        "⚔️ <b>Bellashuv shartlari (3 ta savol):</b>\n"
        "• Har bir ishtirokchiga ketma-ket <b>3 ta murakkabroq savol</b> beriladi.\n"
        "• Kim 3 ta savoldan <b>eng ko'p to'g'ri javob</b> topsa va <b>eng qisqa vaqt</b> sarflasa — o'sha g'olib!\n\n"
        "💰 <b>Yutuq miqdori:</b>\n"
        "• 👥 2 kishilik (kirish 12,000 so'm) 👉 Yutuq: <b>18,000 so'm</b>\n"
        "• 👥 4 kishilik (kirish 17,000 so'm) 👉 Yutuq: <b>25,500 so'm</b>\n"
        "<i>(Yutuq g'olibning plastik kartasiga o'tkazilib, to'lov skrinshoti bot orqali yuboriladi!)</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>Bellashuv turini tanlang:</b>"
    )
    await callback.message.answer(text, reply_markup=adult_mode_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("adult_mode:"))
async def adult_choose_subj(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, role, status, pending_mode, pending_subject) VALUES (?, 'user', 'choosing_subj', ?, 'aralash') "
            "ON CONFLICT(user_id) DO UPDATE SET pending_mode = ?",
            (user_id, mode, mode)
        )
        await db.commit()

    await state.update_data(mode=mode)
    text = (
        f"🎮 Rejim: <b>{'2 kishilik (Yutuq: 18,000 so\'m)' if mode == 'pay_2' else '4 kishilik (Yutuq: 25,500 so\'m)'}</b>\n\n"
        f"📚 <b>Endi o'zingiz eng yaxshi biladigan fanni tanlang:</b>"
    )
    await callback.message.edit_text(text, reply_markup=subject_menu_kb("asubj"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("asubj:"))
async def adult_pay_instructions(callback: CallbackQuery, state: FSMContext):
    subj = callback.data.split(":")[1]
    user_id = callback.from_user.id
    data = await state.get_data()
    mode = data.get("mode")

    async with aiosqlite.connect(DB_PATH) as db:
        if not mode:
            cursor = await db.execute("SELECT pending_mode FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            mode = row[0] if (row and row[0]) else "pay_2"

        await db.execute(
            "UPDATE users SET status = 'waiting_receipt', pending_mode = ?, pending_subject = ? WHERE user_id = ?",
            (mode, subj, user_id)
        )
        await db.commit()

    await state.update_data(mode=mode, subject=subj)
    await state.set_state(GameStates.waiting_for_receipt)

    amount = "12,000" if mode == "pay_2" else "17,000"
    prize = "18,000" if mode == "pay_2" else "25,500"
    subj_name = SUBJECTS.get(subj, "🌐 Aralash")

    text = (
        f"💳 <b>TO'LOV MA'LUMOTLARI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 Rejim: <b>{'2 kishilik' if mode == 'pay_2' else '4 kishilik'}</b> (Yutuq: <b>{prize} so'm</b>)\n"
        f"📚 Tanlangan faningiz: <b>{subj_name}</b>\n"
        f"💰 To'lov summasi: <b>{amount} so'm</b>\n\n"
        f"Quyidagi karta raqamiga to'lovni o'tkazing:\n"
        f"💳 Karta: <code>{KARTA_RAQAMI}</code>\n"
        f"👤 Karta egasi: <b>{KARTA_EGASI}</b>\n\n"
        f"📸 <b>To'lov qilgach, chek skrinshotini (rasm yoki fayl shaklida) shu yerga yuboring:</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

# --- CHEK QABUL QILISH VA G'OLIBGA SKRINSHOT YUBORISH ---
@router.message(F.photo | F.document)
async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
    cur_state = await state.get_state()

    # 1. Agar Admin g'olibga to'lov skrinshotini yuborayotgan bo'lsa:
    if cur_state == GameStates.admin_send_check.state and message.from_user.id == BOSH_ADMIN_ID:
        data = await state.get_data()
        target_uid = data.get("target_user_id")
        try:
            caption_text = "✅ <b>Yutug‘ingiz kartangizga o‘tkazib berildi!</b>\nTo‘lov cheki yuqorida. Ishtirokingiz uchun rahmat!"
            if message.photo:
                await bot.send_photo(chat_id=target_uid, photo=message.photo[-1].file_id, caption=caption_text, parse_mode="HTML")
            else:
                await bot.send_document(chat_id=target_uid, document=message.document.file_id, caption=caption_text, parse_mode="HTML")
            await message.answer("✅ To‘lov skrinshoti g‘olibga muvaffaqiyatli yuborildi!")
        except Exception as e:
            await message.answer(f"❌ Xatolik: {e}")
        await state.clear()
        return

    # 2. Ishtirokchi bellashuvga kirish chekini yuborgan bo'lsa:
    user_id = message.from_user.id
    data = await state.get_data()
    mode = data.get("mode")
    subj = data.get("subject")

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT pending_mode, pending_subject FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not mode:
            mode = row[0] if (row and row[0]) else "pay_2"
        if not subj:
            subj = row[1] if (row and row[1]) else "aralash"

        await db.execute("UPDATE users SET status = 'receipt_sent' WHERE user_id = ?", (user_id,))
        await db.commit()

    await state.clear()
    amount = "12,000" if mode == "pay_2" else "17,000"
    subj_name = SUBJECTS.get(subj, "🌐 Aralash")

    safe_fullname = html.escape(message.from_user.full_name or "Ishtirokchi")
    username_str = f" (@{message.from_user.username})" if message.from_user.username else ""

    admin_text = (
        f"🧾 <b>Yangi chek keldi!</b>\n"
        f"👤 Ism: <b>{safe_fullname}</b>{username_str}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Summa: <b>{amount} so'm</b>\n"
        f"🎮 Turi: <b>{'2 kishilik' if mode == 'pay_2' else '4 kishilik'}</b>\n"
        f"📚 Tanlagan fani: <b>{subj_name}</b>\n\n"
        f"Tasdiqlaysizmi?"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"approve:{mode}:{user_id}")
    builder.button(text="❌ Rad etish", callback_data=f"reject:{user_id}")

    try:
        if message.photo:
            await bot.send_photo(BOSH_ADMIN_ID, message.photo[-1].file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        elif message.document:
            await bot.send_document(BOSH_ADMIN_ID, message.document.file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await message.answer("⏳ <b>Chek adminga muvaffaqiyatli yuborildi!</b>\nTasdiqlanishini kuting...", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}")

@router.callback_query(F.data.startswith("approve:"))
async def approve_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return await callback.answer("Siz admin emassiz!", show_alert=True)

    _, mode, user_id_str = callback.data.split(":")
    user_id = int(user_id_str)

    await callback.answer("✅ To'lov tasdiqlandi!")
    try:
        old_caption = callback.message.caption or "🧾 Chek"
        await callback.message.edit_caption(caption=old_caption + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML", reply_markup=None)
    except Exception:
        pass

    required_count = 2 if mode == "pay_2" else 4
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT pending_subject FROM users WHERE user_id = ?", (user_id,))
        u_row = await cursor.fetchone()
        user_subj = u_row[0] if (u_row and u_row[0]) else "aralash"

        await db.execute("INSERT INTO queues (user_id, mode, status, duel_id, subject) VALUES (?, ?, 'waiting', 0, ?)", (user_id, mode, user_subj))
        await db.commit()

        cursor = await db.execute("SELECT id, user_id, subject FROM queues WHERE mode = ? AND status = 'waiting' ORDER BY id ASC LIMIT ?", (mode, required_count))
        waiting_rows = await cursor.fetchall()

    current_count = len(waiting_rows)
    if current_count < required_count:
        try:
            await bot.send_message(
                user_id,
                f"✅ <b>To'lovingiz tasdiqlandi!</b>\n"
                f"⏳ Navbatga qo'shildingiz: <b>{current_count}/{required_count}</b>.\n"
                f"Raqiblar qo'shilishi bilan 5 soniyalik ogohlantirish keladi va o'yin boshlanadi!",
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        queue_ids = [r[0] for r in waiting_rows]
        players = [r[1] for r in waiting_rows]
        subjects = [r[2] for r in waiting_rows]
        duel_id = random.randint(1000, 9999)

        async with aiosqlite.connect(DB_PATH) as db:
            placeholders = ",".join("?" * len(queue_ids))
            await db.execute(f"UPDATE queues SET status = 'playing', duel_id = ? WHERE id IN ({placeholders})", [duel_id] + queue_ids)
            await db.commit()

        prize = 18000 if mode == "pay_2" else 25500
        duel_type = "2 kishilik" if mode == "pay_2" else "4 kishilik"
        asyncio.create_task(launch_3_question_duel(bot, duel_id, players, subjects, duel_type, prize))

@router.callback_query(F.data.startswith("reject:"))
async def reject_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return await callback.answer("Siz admin emassiz!", show_alert=True)

    rejected_user_id = int(callback.data.split(":")[1])
    await callback.answer("❌ Rad etildi!")
    try:
        old_caption = callback.message.caption or "🧾 Chek"
        await callback.message.edit_caption(caption=old_caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML", reply_markup=None)
        await bot.send_message(rejected_user_id, "❌ <b>Afsuski, chekingiz rad etildi.</b> Iltimos, qaytadan urinib ko'ring.", parse_mode="HTML")
    except Exception:
        pass

# =========================================================================
# ⚔️ KATTALAR 3 SAVOLLIK DUEL TIZIMI
# =========================================================================
async def launch_3_question_duel(bot: Bot, duel_id: int, players: list, subjects: list, duel_type: str, prize: int):
    unique_players = list(dict.fromkeys(players))
    s1 = subjects[0] if len(subjects) > 0 else "aralash"
    s2 = subjects[1] if len(subjects) > 1 else "aralash"
    s3 = subjects[2] if len(subjects) > 2 else "aralash"

    q1 = await get_fresh_question(unique_players, subject=s1, difficulty="hard")
    q2 = await get_fresh_question(unique_players, subject=s2, difficulty="hard")
    q3 = await get_fresh_question(unique_players, subject=s3, difficulty="hard")

    active_duels[duel_id] = {
        "duel_type": duel_type,
        "prize": prize,
        "questions": [q1, q2, q3],
        "players": {},
        "finished": False
    }

    prep_text = (
        f"⚔️ <b>DIQQAT! BARCHA ISHTIROKCHILAR YIG'ILDI!</b> ⚔️\n"
        f"🎮 Rejim: <b>{duel_type}</b> | 🏆 Yutuq: <b>{prize:,} so'm</b>\n\n"
        f"📋 Sizga ketma-ket <b>3 ta savol</b> beriladi.\n"
        f"⏳ <b>Bellashuv 5 soniyadan so'ng boshlanadi! Tayyor turing...</b>"
    )
    for uid in unique_players:
        try:
            chat = await bot.get_chat(uid)
            p_name = chat.full_name or f"Ishtirokchi {uid}"
        except Exception:
            p_name = f"Ishtirokchi {uid}"

        active_duels[duel_id]["players"][uid] = {
            "name": p_name,
            "step": 0,
            "score": 0,
            "start_time": 0.0,
            "elapsed": 999.0,
            "done": False
        }
        try:
            await bot.send_message(uid, prep_text, parse_mode="HTML")
        except Exception:
            pass

    await asyncio.sleep(5.0)
    now = time.monotonic()
    for uid in unique_players:
        active_duels[duel_id]["players"][uid]["start_time"] = now
        await send_duel_question(bot, duel_id, uid, 0)

    asyncio.create_task(duel_global_timeout(bot, duel_id))

async def send_duel_question(bot: Bot, duel_id: int, user_id: int, step_idx: int, edit_msg: Message = None):
    duel = active_duels.get(duel_id)
    if not duel or duel["finished"]:
        return

    q = duel["questions"][step_idx]
    options = [q['opt1'], q['opt2'], q['opt3'], q['opt4']]
    random.shuffle(options)
    correct_text = q[f"opt{q['correct_opt']}"]

    builder = InlineKeyboardBuilder()
    for opt in options:
        is_correct = 1 if opt == correct_text else 0
        builder.button(text=opt, callback_data=f"duel_ans:{duel_id}:{step_idx}:{is_correct}")
    builder.adjust(2)

    text = (
        f"⚔️ <b>BELLASHUV: {step_idx + 1}/3-SAVOL</b>\n"
        f"🏆 Yutuq: <b>{duel['prize']:,} so'm</b>\n\n"
        f"❓ {html.escape(q['question'])}"
    )
    try:
        if edit_msg:
            await edit_msg.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        else:
            await bot.send_message(user_id, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data.startswith("duel_ans:"))
async def handle_duel_answer(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    duel_id = int(parts[1])
    step_idx = int(parts[2])
    is_correct = (parts[3] == "1")
    user_id = callback.from_user.id

    duel = active_duels.get(duel_id)
    if not duel or duel["finished"] or user_id not in duel["players"]:
        return await callback.answer("⚠️ Bu bellashuv yakunlangan!", show_alert=True)

    p_data = duel["players"][user_id]
    if p_data["done"] or p_data["step"] != step_idx:
        return await callback.answer("⚠️ Bu savolga javob berib bo'lgansiz!")

    await callback.answer("✅ Qabul qilindi!" if is_correct else "❌ Xato!")
    if is_correct:
        p_data["score"] += 1
    p_data["step"] += 1

    if p_data["step"] < 3:
        await send_duel_question(bot, duel_id, user_id, p_data["step"], edit_msg=callback.message)
    else:
        p_data["elapsed"] = round(time.monotonic() - p_data["start_time"], 2)
        p_data["done"] = True

        if all(p["done"] for p in duel["players"].values()):
            await finalize_duel(bot, duel_id)
        else:
            try:
                await callback.message.edit_text(
                    f"🏁 <b>Siz barcha 3 ta savolga javob berdingiz!</b>\n\n"
                    f"📊 Natijangiz: <b>3 tadan {p_data['score']} ta to'g'ri</b>\n"
                    f"⏱ Sarflangan vaqt: <b>{p_data['elapsed']} soniya</b>\n\n"
                    f"⏳ Raqibingiz javob berishini kuting...",
                    parse_mode="HTML"
                )
            except Exception:
                pass

async def duel_global_timeout(bot: Bot, duel_id: int):
    await asyncio.sleep(60.0)
    duel = active_duels.get(duel_id)
    if duel and not duel["finished"]:
        await finalize_duel(bot, duel_id)

async def finalize_duel(bot: Bot, duel_id: int):
    duel = active_duels.get(duel_id)
    if not duel or duel["finished"]:
        return
    duel["finished"] = True

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM queues WHERE duel_id = ?", (duel_id,))
        await db.commit()

    ranking = sorted(duel["players"].items(), key=lambda item: (-item[1]["score"], item[1]["elapsed"]))
    winner_id, winner_info = ranking[0]
    prize = duel["prize"]

    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    board_lines = []
    for idx, (uid, info) in enumerate(ranking):
        medal = medals[idx] if idx < len(medals) else "▫️"
        time_str = f"{info['elapsed']} sek" if info["done"] else "vaqt tugadi"
        board_lines.append(f"{medal} <b>{html.escape(info['name'])}</b> — {info['score']}/3 ta ({time_str})")
    leaderboard_text = "\n".join(board_lines)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET status = ? WHERE user_id = ?", (f"won_{prize}", winner_id))
        await db.commit()

    try:
        await bot.send_message(
            winner_id,
            f"🎉 <b>TABRIKLAYMIZ, BELLASHUVDA SIZ G'OLIB BO'LDINGIZ!</b> 🎉\n\n"
            f"📊 <b>Yakuniy natijalar jadvali:</b>\n{leaderboard_text}\n\n"
            f"💰 Yutug'ingiz: <b>{prize:,} so'm!</b>\n"
            f"💳 Admin pul o'tkazishi uchun <b>karta raqamingiz va ism-sharifingizni</b> bitta xabarda yozib yuboring:",
            parse_mode="HTML"
        )
    except Exception:
        pass

    for uid, _ in ranking[1:]:
        try:
            await bot.send_message(
                uid,
                f"🚨 <b>BELLASHUV YAKUNLANDI — YUTQAZDINGIZ!</b> 🚨\n\n"
                f"📊 <b>Yakuniy natijalar jadvali:</b>\n{leaderboard_text}\n\n"
                f"Keyingi safar albatta yutasiz! 🧠🔥",
                reply_markup=main_menu(),
                parse_mode="HTML"
            )
        except Exception:
            pass

    active_duels.pop(duel_id, None)

# =========================================================================
# 💳 G'OLIB KARTASI VA SAVOL QO'SHISH HANDLERI
# =========================================================================
@router.message(F.text & ~F.text.startswith("/"))
async def catch_text_messages(message: Message, state: FSMContext, bot: Bot):
    cur_state = await state.get_state()
    if cur_state == GameStates.adding_single_question.state and message.from_user.id == BOSH_ADMIN_ID:
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 5:
            return await message.answer("❌ Format xato! <code>Savol | To'g'ri | Xato1 | Xato2 | Xato3</code> ko'rinishida yuboring:", parse_mode="HTML")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?, ?, ?, ?, ?, 1, 'aralash', 'hard')", parts)
            await db.commit()
        await state.clear()
        return await message.answer("✅ Savol bazaga qo'shildi!", reply_markup=admin_questions_kb())

    elif cur_state == GameStates.adding_bulk_questions.state and message.from_user.id == BOSH_ADMIN_ID:
        added = 0
        async with aiosqlite.connect(DB_PATH) as db:
            for line in message.text.strip().split("\n"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) == 5:
                    await db.execute("INSERT OR REPLACE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?, ?, ?, ?, ?, 1, 'aralash', 'hard')", parts)
                    added += 1
            await db.commit()
        await state.clear()
        return await message.answer(f"✅ Jami {added} ta savol qo'shildi!", reply_markup=admin_questions_kb())

    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT status FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

    if row and row[0] and row[0].startswith("won_"):
        prize = int(row[0].split("_")[1])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET status = 'none' WHERE user_id = ?", (user_id,))
            await db.commit()

        btn = InlineKeyboardBuilder()
        btn.button(text="📤 Chek (screenshot) yuborish", callback_data=f"send_check:{user_id}")

        await bot.send_message(
            BOSH_ADMIN_ID,
            f"🏆 <b>G'olib karta raqamini yubordi!</b>\n\n"
            f"👤 Ism: <b>{html.escape(message.from_user.full_name or 'G‘olib')}</b>\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💰 Yutuq: <b>{prize:,} so‘m</b>\n"
            f"💳 Karta: <code>{html.escape(message.text)}</code>\n\n"
            f"<i>Pul o‘tkazgach, tugmani bosib skrinshot yuboring:</i>",
            reply_markup=btn.as_markup(),
            parse_mode="HTML"
        )
        await message.answer(
            "✅ <b>Karta raqamingiz adminga yuborildi!</b>\nPul o‘tkazilgach, to‘lov chek skrinshoti shu yerga keladi.",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("send_check:"))
async def admin_check_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    await callback.answer()
    target_uid = int(callback.data.split(":")[1])
    await state.update_data(target_user_id=target_uid)
    await state.set_state(GameStates.admin_send_check)
    await callback.message.reply("📸 Iltimos, to‘lov cheki skrinshotini (rasm shaklida) shu chatga yuboring:")

# =========================================================================
# 🛠 ADMIN VA KASSIR BUYRUQLARI HAMDA TUGMALARI
# =========================================================================
@router.callback_query(F.data == "admin_run_stat")
async def run_stat_cb(callback: CallbackQuery):
    if not await is_kassir(callback.from_user.id):
        return await callback.answer("Ruxsat yo'q!", show_alert=True)
    await callback.answer()
    stat = await hisobot_olish()
    matn = (
        "📊 <b>DO‘KON CHEGIRMALAR STATISTIKASI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📅 <b>BUGUNGI NATIJA:</b>\n"
        f"• Ishlatilgan vaucherlar: <b>{stat['bugun_jami']} ta</b>\n"
        f"  └ 5% lik: <b>{stat['bugun_5']} ta</b>\n"
        f"  └ 3% lik: <b>{stat['bugun_3']} ta</b>\n\n"
        "🗓 <b>OXIRGI 7 KUN (HAFTALIK):</b>\n"
        f"• Ishlatilgan vaucherlar: <b>{stat['hafta_jami']} ta</b>\n\n"
        "📦 <b>UMUMIY BAZA:</b>\n"
        f"• Tarqatilgan vaucherlar: <b>{stat['jami_berilgan']} ta</b>\n"
        f"• Hali xarid qilinmaganlar: <b>{stat['hali_ishlatilmagan']} ta</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await callback.message.answer(matn, parse_mode="HTML")

@router.callback_query(F.data == "admin_run_excel")
async def run_excel_cb(callback: CallbackQuery):
    if not await is_kassir(callback.from_user.id):
        return await callback.answer("Ruxsat yo'q!", show_alert=True)
    await callback.answer("⏳ Hisobot tayyorlanmoqda...")
    fayl = await generate_report_file()
    await callback.message.answer_document(document=fayl, caption="📊 <b>Barcha vaucherlar bazasi jadvali tayyor.</b>", parse_mode="HTML")

@router.callback_query(F.data == "admin_run_kassir_link")
async def run_kassir_link_cb(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    await callback.answer()
    token = secrets.token_hex(8)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO takliflar (token) VALUES (?)", (token,))
        await db.commit()
    bot_me = await bot.get_me()
    havola = f"https://t.me/{bot_me.username}?start=kassir_{token}"
    await callback.message.answer(
        f"🔗 <b>Kassir uchun bir martalik taklif havolasi:</b>\n\n"
        f"<code>{havola}</code>\n\n"
        f"Ushbu havolani xodimga yuboring. U bosib <b>Start</b> qilishi bilan avtomatik kassirga aylanadi.\n\n"
        f"💡 <i>Qo‘lda qo‘shish:</i> <code>/kassir_qosh ID Ism</code>",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_run_kassirlar")
async def run_kassirlar_cb(callback: CallbackQuery):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    await callback.answer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, ism, qoshilgan_vaqt FROM kassirlar") as cursor:
            kassirlar = await cursor.fetchall()
    if not kassirlar:
        return await callback.message.answer("Hozircha birorta ham kassir ulanmagan.\nQo‘shish uchun: <code>/kassir_qosh ID Ism</code>", parse_mode="HTML")
    matn = "📋 <b>Ulangan kassirlar ro‘yxati:</b>\n\n"
    for kid, ism, vaqt in kassirlar:
        matn += f"• <b>{html.escape(ism)}</b> (ID: <code>{kid}</code>) — <i>{vaqt}</i>\n"
    matn += "\n🗑 O‘chirish uchun: <code>/kassir_ochir ID</code>"
    await callback.message.answer(matn, parse_mode="HTML")

@router.callback_query(F.data == "admin_questions_panel")
async def admin_q_panel(callback: CallbackQuery):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    await callback.answer()
    await callback.message.edit_text("🛠 <b>Savollar va O‘yin bazasini boshqarish:</b>", reply_markup=admin_questions_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_clear_queue")
async def admin_clear_queue(callback: CallbackQuery):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM queues")
        await db.commit()
    await callback.answer("🧹 Navbat to'liq tozalandi!", show_alert=True)

@router.callback_query(F.data == "admin_auto_gen")
async def admin_auto_gen(callback: CallbackQuery):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    added = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for _ in range(50):
            subj = random.choice(list(SUBJECTS.keys()))
            diff = random.choice(["easy", "hard"])
            dq = generate_subject_question(subj, diff)
            cursor = await db.execute(
                "INSERT OR IGNORE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?,?,?,?,?,1,?,?)",
                (dq["question"], dq["opt1"], dq["opt2"], dq["opt3"], dq["opt4"], dq["subject"], dq["difficulty"])
            )
            if cursor.rowcount > 0:
                added += 1
        await db.commit()
    await callback.answer(f"⚡ {added} ta yangi savol bazaga qo'shildi!", show_alert=True)

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        q_count = (await (await db.execute("SELECT COUNT(*) FROM questions")).fetchone())[0]
        u_count = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        w2_count = (await (await db.execute("SELECT COUNT(*) FROM queues WHERE status = 'waiting' AND mode = 'pay_2'")).fetchone())[0]
        w4_count = (await (await db.execute("SELECT COUNT(*) FROM queues WHERE status = 'waiting' AND mode = 'pay_4'")).fetchone())[0]
    text = (
        f"📈 <b>O‘yin Statistikasi:</b>\n\n"
        f"❓ Bazadagi savollar: <b>{q_count} ta</b>\n"
        f"👥 Foydalanuvchilar: <b>{u_count} ta</b>\n"
        f"⏳ 2 kishilik navbatda: <b>{w2_count}/2 ta</b>\n"
        f"⏳ 4 kishilik navbatda: <b>{w4_count}/4 ta</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_questions_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_reset_seen")
async def admin_reset_seen(callback: CallbackQuery):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_seen_questions")
        await db.commit()
    await callback.answer("✅ Savollar tarixi tozalandi!", show_alert=True)

@router.callback_query(F.data == "admin_add_one")
async def admin_add_one(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    await state.set_state(GameStates.adding_single_question)
    await callback.message.answer("✍️ <code>Savol | To'g'ri | Xato1 | Xato2 | Xato3</code> formatida yuboring:", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_add_bulk")
async def admin_add_bulk(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    await state.set_state(GameStates.adding_bulk_questions)
    await callback.message.answer("📥 Har bir qatorda bittadan savolni <code>Savol | To'g'ri | Xato1 | Xato2 | Xato3</code> formatida yuboring:", parse_mode="HTML")
    await callback.answer()

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id != BOSH_ADMIN_ID:
        return
    await state.clear()
    await message.answer("👑 <b>Bosh Admin Paneli:</b>", reply_markup=admin_main_kb(), parse_mode="HTML")

@router.message(Command("statistika"))
async def statistika_handler(message: Message):
    if not await is_kassir(message.from_user.id):
        return await message.answer("❌ Bu buyruq faqat kassirlar va admin uchun!")
    stat = await hisobot_olish()
    matn = (
        "📊 <b>DO‘KON CHEGIRMALAR STATISTIKASI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📅 <b>BUGUNGI NATIJA:</b>\n"
        f"• Ishlatilgan vaucherlar: <b>{stat['bugun_jami']} ta</b>\n"
        f"  └ 5% lik: <b>{stat['bugun_5']} ta</b>\n"
        f"  └ 3% lik: <b>{stat['bugun_3']} ta</b>\n\n"
        "🗓 <b>OXIRGI 7 KUN (HAFTALIK):</b>\n"
        f"• Ishlatilgan vaucherlar: <b>{stat['hafta_jami']} ta</b>\n\n"
        "📦 <b>UMUMIY BAZA:</b>\n"
        f"• Tarqatilgan vaucherlar: <b>{stat['jami_berilgan']} ta</b>\n"
        f"• Hali xarid qilinmaganlar: <b>{stat['hali_ishlatilmagan']} ta</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(matn, parse_mode="HTML")

@router.message(Command("excel"))
async def excel_handler(message: Message):
    if not await is_kassir(message.from_user.id):
        return await message.answer("❌ Bu buyruq faqat kassirlar va admin uchun!")
    await message.answer("⏳ Hisobot tayyorlanmoqda...")
    fayl = await generate_report_file()
    await message.answer_document(document=fayl, caption="📊 <b>Barcha vaucherlar bazasi jadvali tayyor.</b>", parse_mode="HTML")

@router.message(Command("kassir_qosh"))
async def kassir_qosh_cmd(message: Message):
    if message.from_user.id != BOSH_ADMIN_ID:
        return
    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer("⚠️ Namuna: <code>/kassir_qosh 543216789 Jasur</code>", parse_mode="HTML")
    try:
        kid, ism = int(parts[1]), parts[2]
    except ValueError:
        return await message.answer("⚠️ ID raqam faqat sondan iborat bo‘lsin!")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO kassirlar (user_id, ism) VALUES (?, ?)", (kid, ism))
        await db.commit()
    await message.answer(f"✅ Kassir ulandi:\n👤 <b>{html.escape(ism)}</b> (ID: <code>{kid}</code>)", parse_mode="HTML")

@router.message(Command("kassir_ochir"))
async def kassir_ochir_cmd(message: Message):
    if message.from_user.id != BOSH_ADMIN_ID:
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        return await message.answer("⚠️ Namuna: <code>/kassir_ochir 543216789</code>", parse_mode="HTML")
    try:
        kid = int(parts[1])
    except ValueError:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM kassirlar WHERE user_id = ?", (kid,))
        await db.commit()
    await message.answer(f"🗑 Kassir (ID: <code>{kid}</code>) o‘chirildi!", parse_mode="HTML")

@router.message(Command("yangi_kassir"))
async def yangi_kassir_link(message: Message, bot: Bot):
    if message.from_user.id != BOSH_ADMIN_ID:
        return
    token = secrets.token_hex(8)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO takliflar (token) VALUES (?)", (token,))
        await db.commit()
    bot_me = await bot.get_me()
    havola = f"https://t.me/{bot_me.username}?start=kassir_{token}"
    await message.answer(
        f"🔗 <b>Kassir uchun bir martalik taklif havolasi:</b>\n\n"
        f"<code>{havola}</code>\n\n"
        f"Ushbu havolani kassirga yuboring. U bosib <b>Start</b> qilishi bilan kassirga aylanadi.",
        parse_mode="HTML"
    )

@router.message(Command("kassirlar"))
async def kassirlar_cmd(message: Message):
    if message.from_user.id != BOSH_ADMIN_ID:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, ism, qoshilgan_vaqt FROM kassirlar") as cursor:
            kassirlar = await cursor.fetchall()
    if not kassirlar:
        return await message.answer("Hozircha birorta ham kassir ulanmagan.")
    matn = "📋 <b>Ulangan kassirlar ro‘yxati:</b>\n\n"
    for kid, ism, vaqt in kassirlar:
        matn += f"• <b>{html.escape(ism)}</b> (ID: <code>{kid}</code>) — <i>{vaqt}</i>\n"
    await message.answer(matn, parse_mode="HTML")

# =========================================================================
# ⏰ KUTUBXONASIZ 21:00 AVTO-HISOBOT VA WEB SERVER
# =========================================================================
async def daily_21_report_loop(bot: Bot):
    last_sent_date = None
    while True:
        try:
            now_uzb = datetime.now(UZB_TZ)
            if now_uzb.hour == 21 and now_uzb.minute == 0 and last_sent_date != now_uzb.date():
                last_sent_date = now_uzb.date()
                stat = await hisobot_olish()
                xabar = (
                    "📢 <b>KUNLIK YAKUNIY HISOBOT (21:00)</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📅 Bugun do‘konda <b>{stat['bugun_jami']} ta</b> chegirma ishlatildi:\n"
                    f"• 5% lik vaucherlar: <b>{stat['bugun_5']} ta</b>\n"
                    f"• 3% lik vaucherlar: <b>{stat['bugun_3']} ta</b>\n\n"
                    f"Kutilayotgan faol vaucherlar: <b>{stat['hali_ishlatilmagan']} ta</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━"
                )
                await bot.send_message(chat_id=BOSH_ADMIN_ID, text=xabar, parse_mode="HTML")
        except Exception:
            pass
        await asyncio.sleep(30)

async def handle(request):
    return web.Response(text="Joker Loto Bot 24/7 ishlayapti! 🤖")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# =========================================================================
# 🚀 ASOSIY ISHGA TUSHIRISH (AVTO-TOKEN TEKSHIRUVI BILAN)
# =========================================================================
async def get_working_bot() -> Bot:
    for tk in CANDIDATE_TOKENS:
        if not tk or ":" not in tk:
            continue
        try:
            test_bot = Bot(token=tk)
            me = await test_bot.get_me()
            print(f"✅ Ishlaydigan token topildi! Bot: @{me.username}")
            return test_bot
        except Exception as e:
            print(f"⚠️ Token ishlamadi ({tk[:12]}...): {e}")
            try:
                await test_bot.session.close()
            except Exception:
                pass
    raise RuntimeError("❌ Hech bir token ishlamadi! @BotFather dan yangi token oling.")

async def main():
    await init_db()
    asyncio.create_task(web_server())

    bot = await get_working_bot()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    dp = Dispatcher()
    dp.include_router(router)

    asyncio.create_task(daily_21_report_loop(bot))

    print("🤖 Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
