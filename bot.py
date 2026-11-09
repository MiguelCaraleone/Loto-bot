import asyncio
import io
import logging
import os
import random
import secrets
import time
import html
import qrcode
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import aiosqlite
from aiohttp import web

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import CommandStart, Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# =========================================================================
# ⚙️ SOZLAMALAR VA TOKEN
# =========================================================================
TOKEN = "9237388648:AAGv4Di7HjpZqNhMZ1FXPVVa4dRnILAP-h4"
BOSH_ADMIN_ID = int(os.getenv("BOSH_ADMIN_ID", "1302845749"))
DB_PATH = "loto_game.db"
KARTA_RAQAMI = "9860 3501 4780 2176"
KARTA_EGASI = "Mamatkulov Izzatillo"
JOKER_IMG_URL = "https://i.ibb.co/RkRvBsHP/file-00000000865082469ff369a93b107407.png"

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
    toifa_tanlash = State()
    fan_tanlash = State()
    test_yechish = State()
    waiting_for_receipt = State()
    admin_send_check = State()
    adding_single_question = State()
    adding_bulk_questions = State()

# =========================================================================
# 📚 SAVOLLAR BAZASI (OSON VA MURAKKAB)
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
    ("Jinoyat kodeksiga ko'ra, umumiy jinoiy javobgarlik necha yoshdan boshlanadi (og'ir jinoyatlardan tashqari)?", "16 yoshdan", "18 yoshdan", "14 yoshdan", "15 yoshdan"),
    ("Oliy Majlis Qonunchilik palatasi (quyi palata) nechta deputatdan iborat?", "150 nafar", "100 nafar", "120 nafar", "65 nafar"),
    ("Oila kodeksiga muvofiq, O'zbekistonda erkaklar va ayollar uchun nikoh yoshi necha yosh?", "18 yosh", "Erkaklarga 18, ayollarga 17 yosh", "20 yosh", "19 yosh")
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
                q_text = f"Hisoblang: {a} + {b} - {c} = ?"
            else:
                a, b, c = random.randint(4, 12), random.randint(3, 9), random.randint(5, 25)
                ans = a * b + c
                q_text = f"Hisoblang: {a} × {b} + {c} = ?"
        else:
            turi = random.choice(["tenglama", "foiz", "kvadrat"])
            if turi == "tenglama":
                x = random.randint(6, 19)
                a = random.randint(4, 12)
                b = random.randint(15, 60)
                res = a * x - b
                ans = x
                q_text = f"Tenglamani yeching: {a}x - {b} = {res}"
            elif turi == "foiz":
                son = random.choice([200, 300, 400, 500, 600, 800, 1200])
                foiz = random.choice([15, 25, 35, 45, 65])
                ans = (son * foiz) // 100
                q_text = f"{son} sonining {foiz}% ini toping."
            else:
                a = random.randint(12, 24)
                b = random.randint(4, 9)
                c = random.randint(5, 12)
                ans = (a * a) - (b * c)
                q_text = f"Hisoblang: {a}² - ({b} × {c}) = ?"

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
            q_text = f"Avtomobil {s} km masofani {t} soatda bosib o'tdi. Tezligini toping."
        else:
            i_val = random.randint(3, 12)
            r_val = random.randint(5, 25)
            u_val = i_val * r_val
            ans = f"{r_val} Om"
            wrongs = [f"{r_val + 4} Om", f"{max(2, r_val - 3)} Om", f"{r_val * 2} Om"]
            q_text = f"Kuchlanishi {u_val} V bo'lgan o'tkazgichdan {i_val} A tok o'tmoqda. Qarshilikni (R) toping."
        return {"question": q_text, "opt1": ans, "opt2": wrongs[0], "opt3": wrongs[1], "opt4": wrongs[2], "correct_opt": 1, "subject": "fizika", "difficulty": difficulty}

    pool_map = {
        "adabiyot": (ADABIYOT_EASY, ADABIYOT_HARD),
        "tarix": (TARIX_EASY, TARIX_HARD),
        "biologiya": (BIOLOGIYA_EASY, BIOLOGIYA_HARD),
        "ona_tili": (ONA_TILI_EASY, ONA_TILI_HARD),
        "huquq": (HUQUQ_EASY, HUQUQ_HARD),
    }
    easy_list, hard_list = pool_map[subject]
    chosen_list = easy_list if difficulty == "easy" else hard_list
    q_raw, o1, o2, o3, o4 = random.choice(chosen_list)
    return {"question": q_raw, "opt1": o1, "opt2": o2, "opt3": o3, "opt4": o4, "correct_opt": 1, "subject": subject, "difficulty": difficulty}

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

        # Dastlabki savollarni bazaga yozish
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
# 🎨 QR-KOD VA EXCEL HISOBOT
# =========================================================================
def qr_kod_yaratish(havola: str) -> BufferedInputFile:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(havola)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return BufferedInputFile(buffer.getvalue(), filename="vaucher_qr.png")

async def generate_excel_report() -> io.BytesIO:
    async with aiosqlite.connect(DB_PATH) as db:
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

# =========================================================================
# 🔘 KLAVIATURALAR
# =========================================================================
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="👦 Yoshlar uchun (Bepul • Chegirmali)", callback_data="youth_intro")
    builder.button(text="👨 Kattalar uchun (Bellashuv • Yutuqli)", callback_data="adult_intro")
    builder.adjust(1)
    return builder.as_markup()

def admin_main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Do‘kon Chegirmalar Statistikasi", callback_data="admin_run_stat")
    builder.button(text="📁 Excel hisobot yuklab olish (.xlsx)", callback_data="admin_run_excel")
    builder.button(text="🔗 Yangi kassir taklif havolasi", callback_data="admin_run_kassir_link")
    builder.button(text="👥 Ulangan kassirlar ro‘yxati", callback_data="admin_run_kassirlar")
    builder.button(text="➕ Savol qo‘shish va Baza boshqaruvi", callback_data="admin_questions_panel")
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
    builder.button(text="🔙 Asosiy menyu", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()

def savol_klaviaturasi(variantlar: list, callback_prefix: str):
    builder = InlineKeyboardBuilder()
    for variant in variantlar:
        builder.button(text=variant, callback_data=f"{callback_prefix}:{variant}")
    builder.adjust(1)
    return builder.as_markup()

# =========================================================================
# 🤖 START VA ADMIN PANEL HANDLERLARI
# =========================================================================
router = Router()
active_duels = {}

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    await state.clear()
    args = command.args
    user_id = message.from_user.id

    # 1. KASSIR QR-KODNI TELEFONI BILAN SKANER QILGANDA
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

    # 2. BIR MARTALIK TAKLIF HAVOLASI ORQALI KASSIR ULANGANDA
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

                await message.answer("🎉 <b>Tabriklaymiz! Siz muvaffaqiyatli kassir sifatida tizimga ulandingiz.</b>\nEndi xaridorlarning QR-kodini kamerangiz orqali tekshirishingiz mumkin.", parse_mode="HTML")
                await bot.send_message(
                    chat_id=BOSH_ADMIN_ID,
                    text=f"🔔 <b>Yangi kassir ulandi:</b> {message.from_user.full_name} (ID: <code>{user_id}</code>)",
                    parse_mode="HTML"
                )
                return
            else:
                await message.answer("❌ Ushbu taklif havolasi eskirgan yoki avval ishlatilgan!")
                return

    # 3. AGAR SIZ (BOSH ADMIN) /start BOSGAN BO'LSANGIZ:
    if user_id == BOSH_ADMIN_ID:
        await message.answer(
            f"👑 <b>Xush kelibsiz, Bosh Admin!</b> (ID: <code>{user_id}</code>)\n\n"
            f"Do‘kon chegirmalari, kassirlar va o‘yin tizimi to‘liq nazoratingizda. Kerakli bo‘limni tanlang:",
            reply_markup=admin_main_kb(),
            parse_mode="HTML"
        )
        return

    # 4. AGAR KASSIR /start BOSGAN BO'LSA:
    if await is_kassir(user_id):
        kassir_kb = InlineKeyboardBuilder()
        kassir_kb.button(text="📊 Do‘kon Statistikasi", callback_data="admin_run_stat")
        kassir_kb.button(text="📁 Excel hisobot (.xlsx)", callback_data="admin_run_excel")
        kassir_kb.button(text="🎮 O‘yin menyusiga o‘tish", callback_data="user_mode_start")
        kassir_kb.adjust(1)
        await message.answer(
            f"💼 <b>Xush kelibsiz, Kassir {html.escape(message.from_user.first_name)}!</b>\n\n"
            f"Mijoz QR-kodini tekshirish uchun telefon kamerangiz orqali QR-kodni skaner qiling yoki quyidagi menyudan foydalaning:",
            reply_markup=kassir_kb.as_markup(),
            parse_mode="HTML"
        )
        return

    # 5. ODDIY FOYDALANUVCHIGA ASOSIY MENYU
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, role, status, pending_mode, pending_subject) VALUES (?, 'user', 'none', 'pay_2', 'aralash')",
            (user_id,)
        )
        await db.commit()

    safe_name = html.escape(message.from_user.first_name or "Do'stim")
    text = (
        f"👋 Salom, <b>{safe_name}</b>!\n\n"
        f"🃏 Intellektual viktorina botimizga xush kelibsiz!\n\n"
        f"👦 <b>Bolalar/Yoshlar bo'limi:</b> 3 ta savolga to‘g‘ri javob berib, do‘konimizdan <b>5% yoki 3% lik QR-kodli chegirma</b> yutib oling!\n"
        f"👨 <b>Kattalar bellashuvi:</b> 2 yoki 4 kishilik tezkor duelda qatnashib, <b>naqd pul yutuqlarini</b> kartangizga yutib oling!\n\n"
        f"👇 Kim uchun o‘yin boshlaymiz?"
    )
    try:
        await message.answer_photo(photo=JOKER_IMG_URL, caption=text, reply_markup=main_menu(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

# Kimdir o'z Telegram ID raqamini bilmoqchi bo'lsa: /id
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
# 👦 BOLALAR UCHUN TEST VA BIR MARTALIK QR-KOD CHEGIRMA
# =========================================================================
@router.callback_query(F.data == "youth_intro")
async def youth_intro(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    text = (
        "👦 <b>Bolalar va Yoshlar uchun chegirmali viktorina!</b>\n\n"
        "Tanlagan faningizdan <b>3 ta qiziqarli savol</b> beriladi:\n"
        "• 3 ta to‘g‘ri javob ➡️ <b>5% chegirma</b>\n"
        "• 2 ta to‘g‘ri javob ➡️ <b>3% chegirma</b>\n\n"
        "💰 <b>Chegirma qanday hisoblanadi (Misol):</b>\n"
        "• 10 000 so‘mlik xarid uchun ➡️ <b>9 500 so‘m to‘laysiz</b>\n"
        "• 40 000 so‘mlik xarid uchun ➡️ <b>38 000 so‘m to‘laysiz</b>\n\n"
        "👇 <b>Savollar qaysi fandan bo‘lsin? Tanlang:</b>"
    )
    await callback.message.edit_text(text, reply_markup=subject_menu_kb("ysubj"), parse_mode="HTML")

@router.callback_query(F.data.startswith("ysubj:"))
async def youth_start_test(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    subj = callback.data.split(":")[1]
    user_id = callback.from_user.id

    savollar = []
    for _ in range(3):
        q = await get_fresh_question([user_id], subject=subj, difficulty="easy")
        variantlar = [q["opt1"], q["opt2"], q["opt3"], q["opt4"]]
        random.shuffle(variantlar)
        savollar.append({
            "savol": q["question"],
            "variantlar": variantlar,
            "javob": q["opt1"]
        })

    await state.set_state(GameStates.test_yechish)
    await state.set_data({
        "fan": subj,
        "savollar": savollar,
        "indeks": 0,
        "score": 0
    })

    birinchi = savollar[0]
    subj_name = SUBJECTS.get(subj, "🌐 Aralash")

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        text=f"📌 <b>{subj_name}</b> (1/3-savol)\n\n❓ {html.escape(birinchi['savol'])}",
        reply_markup=savol_klaviaturasi(birinchi["variantlar"], "yans"),
        parse_mode="HTML"
    )

@router.callback_query(GameStates.test_yechish, F.data.startswith("yans:"))
async def youth_answer(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    javob = callback.data.split(":", 1)[1]

    data = await state.get_data()
    savollar = data.get("savollar", [])
    if not savollar:
        await callback.message.answer("⚠️ Sessiya eskirgan. Qaytadan /start bosing.")
        await state.clear()
        return

    indeks = data.get("indeks", 0)
    score = data.get("score", 0)
    subj = data.get("fan", "aralash")
    subj_name = SUBJECTS.get(subj, "🌐 Aralash")

    if javob == savollar[indeks]["javob"]:
        score += 1

    keyingi = indeks + 1

    if keyingi < len(savollar):
        await state.update_data(indeks=keyingi, score=score)
        q = savollar[keyingi]
        await callback.message.edit_text(
            text=f"📌 <b>{subj_name}</b> ({keyingi + 1}/3-savol)\n\n❓ {html.escape(q['savol'])}",
            reply_markup=savol_klaviaturasi(q["variantlar"], "yans"),
            parse_mode="HTML"
        )
    else:
        user_id = callback.from_user.id
        await state.clear()
        try:
            await callback.message.delete()
        except Exception:
            pass

        if score >= 2:
            foiz = 5 if score == 3 else 3
            unikal_kod = f"CH_{foiz}_{user_id}_{random.randint(1000, 9999)}"
            await kod_saqlash(unikal_kod, user_id, foiz)

            # Bot usernamesini avtomatik aniqlash
            bot_me = await bot.get_me()
            skaner_havolasi = f"https://t.me/{bot_me.username}?start={unikal_kod}"
            qr_rasm = qr_kod_yaratish(skaner_havolasi)

            tolov_10 = 10000 - (10000 * foiz // 100)
            tolov_40 = 40000 - (40000 * foiz // 100)

            matn = (
                f"🎉 <b>TABRIKLAYMIZ! Siz 3 tadan {score} ta to‘g‘ri javob berdingiz!</b>\n\n"
                f"Sizga do‘konimizdagi barcha mahsulotlar uchun <b>{foiz}% lik chegirma</b> berildi!\n\n"
                f"💰 <b>Xarid namunalari:</b>\n"
                f"• 10 000 so‘mlik xarid ➡️ <b>{tolov_10:,} so‘m</b>\n"
                f"• 40 000 so‘mlik xarid ➡️ <b>{tolov_40:,} so‘m</b>\n\n"
                f"🎟 <b>Vaucher kodi:</b> <code>{unikal_kod}</code>\n\n"
                f"📲 Do‘konga borganingizda ushbu <b>QR-kodni kassirga ko‘rsating</b>!\n"
                f"<i>(Vaucher faqat 1 marta amal qiladi)</i>"
            )
            try:
                await bot.send_photo(chat_id=user_id, photo=qr_rasm, caption=matn, reply_markup=main_menu(), parse_mode="HTML")
            except Exception:
                await bot.send_message(chat_id=user_id, text=matn, reply_markup=main_menu(), parse_mode="HTML")
        else:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"📉 <b>Natijangiz: 3 tadan {score} ta to‘g‘ri javob.</b>\n\n"
                    f"Chegirmaga ega bo‘lish uchun kamida 2 ta savolga to‘g‘ri javob berish kerak edi.\n"
                    f"Yana bir bor urinib ko‘ring!"
                ),
                reply_markup=main_menu(),
                parse_mode="HTML"
            )

# =========================================================================
# 👨 KATTALAR BELLASHUVI (PUL YUTUG'I VA CHEK SKRINSHOT TIZIMI)
# =========================================================================
@router.callback_query(F.data == "adult_intro")
async def adult_intro_handler(callback: CallbackQuery):
    text = (
        "👨 <b>KATTALAR UCHUN BELLASHUV — QOIDALAR</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ O'yin turini (<b>2 yoki 4 kishilik</b>) va o'zingiz yaxshi biladigan <b>fanni</b> tanlaysiz.\n"
        "2️⃣ Karta raqamiga to'lov qilib, chek skrinshotini botga yuborasiz.\n"
        "3️⃣ Admin tasdiqlagach, navbatga qo'shilasiz va ishtirokchilar yig'ilishi bilan 3 ta murakkab savollik duel boshlanadi!\n\n"
        "💰 <b>Yutuq miqdori:</b>\n"
        "• 👥 2 kishilik (kirish 12,000 so'm) 👉 Yutuq: <b>18,000 so'm</b>\n"
        "• 👥 4 kishilik (kirish 17,000 so'm) 👉 Yutuq: <b>25,500 so'm</b>\n"
        "<i>(Admin yutuqni kartangizga tashlab, bot orqali chek skrinshotini jo‘natadi!)</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>Bellashuv turini tanlang:</b>"
    )
    await callback.message.edit_text(text, reply_markup=adult_mode_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("adult_mode:"))
async def adult_choose_subj(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]
    await state.update_data(mode=mode)
    text = (
        f"🎮 Rejim: <b>{'2 kishilik (Yutuq: 18,000 so\'m)' if mode == 'pay_2' else '4 kishilik (Yutuq: 25,500 so\'m)'}</b>\n\n"
        f"📚 <b>O‘zingiz eng yaxshi biladigan fanni tanlang:</b>"
    )
    await callback.message.edit_text(text, reply_markup=subject_menu_kb("asubj"), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("asubj:"))
async def adult_pay_instructions(callback: CallbackQuery, state: FSMContext):
    subj = callback.data.split(":")[1]
    data = await state.get_data()
    mode = data.get("mode", "pay_2")

    await state.update_data(mode=mode, subject=subj)
    await state.set_state(GameStates.waiting_for_receipt)

    amount = "12,000" if mode == "pay_2" else "17,000"
    prize = "18,000" if mode == "pay_2" else "25,500"
    subj_name = SUBJECTS.get(subj, "🌐 Aralash")

    text = (
        f"💳 <b>TO'LOV MA'LUMOTLARI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 Rejim: <b>{'2 kishilik' if mode == 'pay_2' else '4 kishilik'}</b> (Yutuq: <b>{prize} so'm</b>)\n"
        f"📚 Faningiz: <b>{subj_name}</b>\n"
        f"💰 To'lov summasi: <b>{amount} so'm</b>\n\n"
        f"Quyidagi kartaga to'lovni o'tkazing:\n"
        f"💳 Karta: <code>{KARTA_RAQAMI}</code>\n"
        f"👤 Karta egasi: <b>{KARTA_EGASI}</b>\n\n"
        f"📸 <b>To'lov qilgach, chek skrinshotini (rasm qilib) shu yerga yuboring:</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@router.message(F.photo | F.document)
async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
    cur_state = await state.get_state()
    
    # 1. Agar Admin g'olibga to'lov cheki skrinshotini yuborayotgan bo'lsa
    if cur_state == GameStates.admin_send_check.state and message.from_user.id == BOSH_ADMIN_ID:
        data = await state.get_data()
        target_uid = data.get("target_user_id")
        photo_id = message.photo[-1].file_id if message.photo else message.document.file_id

        try:
            caption_text = "✅ <b>Yutug‘ingiz kartangizga tashlab berildi!</b>\nTo‘lov cheki yuqorida. Ishtirokingiz uchun rahmat!"
            if message.photo:
                await bot.send_photo(chat_id=target_uid, photo=photo_id, caption=caption_text, parse_mode="HTML")
            else:
                await bot.send_document(chat_id=target_uid, document=photo_id, caption=caption_text, parse_mode="HTML")

            await message.answer("✅ To‘lov cheki muvaffaqiyatli g‘olibga yuborildi!")
        except Exception as e:
            await message.answer(f"❌ Xatolik yuz berdi: {e}")
        await state.clear()
        return

    # 2. Oddiy ishtirokchi bellashuv uchun to'lov cheki tashlaganida
    user_id = message.from_user.id
    data = await state.get_data()
    mode = data.get("mode", "pay_2")
    subj = data.get("subject", "aralash")

    await state.clear()
    amount = "12,000" if mode == "pay_2" else "17,000"
    subj_name = SUBJECTS.get(subj, "🌐 Aralash")

    admin_text = (
        f"🧾 <b>Yangi to‘lov cheki keldi!</b>\n"
        f"👤 Ism: <b>{html.escape(message.from_user.full_name or 'Ishtirokchi')}</b>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Summa: <b>{amount} so'm</b>\n"
        f"🎮 Turi: <b>{'2 kishilik' if mode == 'pay_2' else '4 kishilik'}</b>\n"
        f"📚 Tanlagan fani: <b>{subj_name}</b>\n\n"
        f"Tasdiqlaysizmi?"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"approve:{mode}:{user_id}:{subj}")
    builder.button(text="❌ Rad etish", callback_data=f"reject:{user_id}")

    try:
        if message.photo:
            await bot.send_photo(BOSH_ADMIN_ID, message.photo[-1].file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        elif message.document:
            await bot.send_document(BOSH_ADMIN_ID, message.document.file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await message.answer("⏳ <b>Chek adminga yuborildi!</b> Tasdiqlanishini kuting...", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")

@router.callback_query(F.data.startswith("approve:"))
async def approve_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return await callback.answer("Siz admin emassiz!", show_alert=True)

    _, mode, user_id_str, subj = callback.data.split(":")
    user_id = int(user_id_str)

    await callback.answer("✅ To‘lov tasdiqlandi!")
    try:
        await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML")
    except Exception:
        pass

    required = 2 if mode == "pay_2" else 4
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO queues (user_id, mode, status, duel_id, subject) VALUES (?, ?, 'waiting', 0, ?)", (user_id, mode, subj))
        await db.commit()

        cursor = await db.execute("SELECT id, user_id, subject FROM queues WHERE mode = ? AND status = 'waiting' ORDER BY id ASC LIMIT ?", (mode, required))
        waiting_rows = await cursor.fetchall()

    if len(waiting_rows) < required:
        try:
            await bot.send_message(user_id, f"✅ <b>To‘lovingiz tasdiqlandi!</b>\n⏳ Navbatda: <b>{len(waiting_rows)}/{required}</b>. Raqiblar yig‘ilishi bilan bellashuv boshlanadi!", parse_mode="HTML")
        except Exception:
            pass
    else:
        q_ids = [r[0] for r in waiting_rows]
        players = [r[1] for r in waiting_rows]
        subjects = [r[2] for r in waiting_rows]
        duel_id = random.randint(1000, 9999)

        async with aiosqlite.connect(DB_PATH) as db:
            p_marks = ",".join("?" * len(q_ids))
            await db.execute(f"UPDATE queues SET status = 'playing', duel_id = ? WHERE id IN ({p_marks})", [duel_id] + q_ids)
            await db.commit()

        prize = 18000 if mode == "pay_2" else 25500
        duel_name = "2 kishilik" if mode == "pay_2" else "4 kishilik"
        asyncio.create_task(launch_duel(bot, duel_id, players, subjects, duel_name, prize))

@router.callback_query(F.data.startswith("reject:"))
async def reject_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != BOSH_ADMIN_ID:
        return
    rejected_id = int(callback.data.split(":")[1])
    await callback.answer("❌ Rad etildi!")
    try:
        await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")
        await bot.send_message(rejected_id, "❌ <b>Afsuski, to‘lov chekingiz rad etildi.</b> Iltimos, ma’lumotlarni tekshirib qaytadan urinib ko‘ring.", parse_mode="HTML")
    except Exception:
        pass

# =========================================================================
# ⚔️ DUEL JARAYONI (3 TA SAVOL + TEZLIK + G'OLIB)
# =========================================================================
async def launch_duel(bot: Bot, duel_id: int, players: list, subjects: list, duel_name: str, prize: int):
    unique_players = list(dict.fromkeys(players))
    savollar = []
    for i in range(3):
        s = subjects[i % len(subjects)]
        q = await get_fresh_question(unique_players, subject=s, difficulty="hard")
        v = [q["opt1"], q["opt2"], q["opt3"], q["opt4"]]
        random.shuffle(v)
        savollar.append({"savol": q["question"], "variantlar": v, "javob": q["opt1"]})

    active_duels[duel_id] = {
        "duel_name": duel_name,
        "prize": prize,
        "savollar": savollar,
        "players": {},
        "finished": False
    }

    prep = (
        f"⚔️ <b>BARCHA ISHTIROKCHILAR YIG‘ILDI!</b> ⚔️\n"
        f"🎮 Rejim: <b>{duel_name}</b> | 🏆 Yutuq: <b>{prize:,} so'm</b>\n\n"
        f"📋 3 ta murakkab savol beriladi. Eng ko‘p to‘g‘ri javob topgan va tezroq ishlagan g‘olib bo‘ladi!\n\n"
        f"⏳ <b>5 soniyadan keyin boshlanadi...</b>"
    )
    for uid in unique_players:
        try:
            c = await bot.get_chat(uid)
            p_name = c.full_name or f"Ishtirokchi {uid}"
        except Exception:
            p_name = f"Ishtirokchi {uid}"

        active_duels[duel_id]["players"][uid] = {
            "name": p_name,
            "indeks": 0,
            "score": 0,
            "start_time": 0.0,
            "elapsed": 999.0,
            "done": False
        }
        try:
            await bot.send_message(uid, prep, parse_mode="HTML")
        except Exception:
            pass

    await asyncio.sleep(5.0)
    now = time.monotonic()
    for uid in unique_players:
        active_duels[duel_id]["players"][uid]["start_time"] = now
        await send_duel_q(bot, duel_id, uid, 0)

async def send_duel_q(bot: Bot, duel_id: int, user_id: int, step_idx: int, edit_msg: Message = None):
    duel = active_duels.get(duel_id)
    if not duel or duel["finished"]:
        return

    q = duel["savollar"][step_idx]
    builder = InlineKeyboardBuilder()
    for opt in q["variantlar"]:
        is_corr = 1 if opt == q["javob"] else 0
        builder.button(text=opt, callback_data=f"dans:{duel_id}:{step_idx}:{is_corr}")
    builder.adjust(1)

    text = f"⚔️ <b>BELLASHUV: {step_idx + 1}/3-SAVOL</b>\n\n❓ {html.escape(q['savol'])}"
    try:
        if edit_msg:
            await edit_msg.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        else:
            await bot.send_message(user_id, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data.startswith("dans:"))
async def duel_ans(callback: CallbackQuery, bot: Bot):
    _, duel_id_str, step_str, corr_str = callback.data.split(":")
    duel_id, step_idx, is_corr = int(duel_id_str), int(step_str), (corr_str == "1")
    user_id = callback.from_user.id

    duel = active_duels.get(duel_id)
    if not duel or duel["finished"] or user_id not in duel["players"]:
        return await callback.answer("Bellashuv yakunlangan!", show_alert=True)

    p = duel["players"][user_id]
    if p["done"] or p["indeks"] != step_idx:
        return await callback.answer("Javob berib bo‘lgansiz!")

    await callback.answer("To‘g‘ri!" if is_corr else "Xato!")
    if is_corr:
        p["score"] += 1
    p["indeks"] += 1

    if p["indeks"] < 3:
        await send_duel_q(bot, duel_id, user_id, p["indeks"], edit_msg=callback.message)
    else:
        p["elapsed"] = round(time.monotonic() - p["start_time"], 2)
        p["done"] = True

        if all(pl["done"] for pl in duel["players"].values()):
            await finalize_duel(bot, duel_id)
        else:
            await callback.message.edit_text(
                f"🏁 <b>Barcha savollarga javob berdingiz!</b>\n"
                f"📊 Natijangiz: <b>{p['score']}/3 ta</b> ({p['elapsed']} sek)\n\n"
                f"⏳ Raqibingiz yakunlashini kuting...",
                parse_mode="HTML"
            )

async def finalize_duel(bot: Bot, duel_id: int):
    duel = active_duels.get(duel_id)
    if not duel or duel["finished"]:
        return
    duel["finished"] = True

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM queues WHERE duel_id = ?", (duel_id,))
        await db.commit()

    ranking = sorted(duel["players"].items(), key=lambda x: (-x[1]["score"], x[1]["elapsed"]))
    winner_id, winner_info = ranking[0]
    prize = duel["prize"]

    board = []
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    for i, (uid, info) in enumerate(ranking):
        m = medals[i] if i < len(medals) else "▫️"
        board.append(f"{m} <b>{html.escape(info['name'])}</b>: {info['score']}/3 ({info['elapsed']} sek)")
    board_text = "\n".join(board)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET status = ? WHERE user_id = ?", (f"won_{prize}", winner_id))
        await db.commit()

    try:
        await bot.send_message(
            winner_id,
            f"🎉 <b>TABRIKLAYMIZ, SIZ G‘OLIB BO‘LDINGIZ!</b> 🎉\n\n"
            f"📊 <b>Natijalar:</b>\n{board_text}\n\n"
            f"💰 Yutuq: <b>{prize:,} so'm!</b>\n"
            f"💳 Admin pulni tashlashi uchun <b>plastik karta raqamingizni</b> shu yerga yozib yuboring:",
            parse_mode="HTML"
        )
    except Exception:
        pass

    for uid, _ in ranking[1:]:
        try:
            await bot.send_message(
                uid,
                f"🚨 <b>Bellashuv yakunlandi!</b>\n\n📊 <b>Natijalar:</b>\n{board_text}\n\nRaqibingiz tezroq bo‘lib chiqdi. Keyingi safar albatta yutasiz!",
                reply_markup=main_menu(),
                parse_mode="HTML"
            )
        except Exception:
            pass

    active_duels.pop(duel_id, None)

# =========================================================================
# 💳 G'OLIB KARTASI VA SAVOL QO'SHISH MATNLARINI TUTISH
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
            f"🏆 <b>Yangi g‘olib karta raqamini yubordi!</b>\n\n"
            f"👤 Ism: <b>{html.escape(message.from_user.full_name or 'G‘olib')}</b>\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💰 Yutuq summasi: <b>{prize:,} so‘m</b>\n"
            f"💳 Karta raqami: <code>{html.escape(message.text)}</code>\n\n"
            f"<i>Pulni o‘tkazib, pastdagi tugma orqali chek skrinshotini yuboring:</i>",
            reply_markup=btn.as_markup(),
            parse_mode="HTML"
        )

        await message.answer(
            "✅ <b>Karta ma’lumotlaringiz adminga yetkazildi!</b>\nPul o‘tkazilgach, to‘lov chek skrinshoti shu yerga tashlanadi.",
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
# 🛠 ADMIN VA KASSIR TUGMALARI HAMDA BUYRUQLARI
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
    await callback.answer("⏳ Excel tayyorlanmoqda...")
    stream = await generate_excel_report()
    fayl = BufferedInputFile(file=stream.getvalue(), filename="vaucherlar_hisoboti.xlsx")
    await callback.message.answer_document(document=fayl, caption="📊 <b>Barcha vaucherlar bazasi Excel formatida tayyor.</b>")

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
        f"💡 <i>Yoki qo‘lda qo‘shish uchun:</i> <code>/kassir_qosh ID Ism</code>",
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
    await callback.answer("✅ O'yinchilar ko'rgan savollar tarixi tozalandi!", show_alert=True)

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

# Matnli buyruqlar (/statistika, /excel, /kassir_qosh, /kassir_ochir, /kassirlar, /admin)
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
    await message.answer("⏳ Excel hisobot tayyorlanmoqda...")
    stream = await generate_excel_report()
    fayl = BufferedInputFile(file=stream.getvalue(), filename="vaucherlar_hisoboti.xlsx")
    await message.answer_document(document=fayl, caption="📊 <b>Barcha vaucherlar bazasi Excel formatida tayyor.</b>")

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
# ⏰ HAR KUNI 21:00 DA AVTO-HISOBOT VA WEB SERVER
# =========================================================================
async def kunlik_avto_hisobot(bot: Bot):
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
    try:
        await bot.send_message(chat_id=BOSH_ADMIN_ID, text=xabar, parse_mode="HTML")
    except Exception:
        pass

async def handle(request):
    return web.Response(text="Bot 24/7 faol ishlamoqda! 🚀")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# =========================================================================
# 🚀 ASOSIY ISHGA TUSHIRISH (MAIN)
# =========================================================================
async def main():
    await init_db()
    bot = Bot(token=TOKEN)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    dp = Dispatcher()
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(
        kunlik_avto_hisobot,
        trigger=CronTrigger(hour=21, minute=0, timezone="Asia/Tashkent"),
        kwargs={"bot": bot}
    )
    scheduler.start()

    asyncio.create_task(web_server())

    print("🤖 Barcha tizimlari integratsiya qilingan Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
