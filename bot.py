import asyncio
import logging
import aiosqlite
import random
import os
import html
import time
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN", "9237388648:AAHqC1UHqbkMUFwEIW-vE59Oj990Zp2Ar4w") 
ADMIN_ID = 1302845749
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
    waiting_for_receipt = State()
    waiting_for_card = State()
    adding_single_question = State()
    adding_bulk_questions = State()

# =========================================================================
# 📚 OSON (YOSHLAR) VA MURAKKAB (KATTALAR) SAVOLLAR BAZASI
# =========================================================================

# 1. ADABIYOT
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
    ("Cho'lponning «Kecha va kunduz» romanida Razzoq so'fining qizi kim?", "Zebi", "Maryam", "Xadicha", "jiyda"),
    ("Abdulla Qodiriyning «Mehrobdan chayon» romanida bosh qahramonlar kimlar?", "Anvar va Ra'no", "Otabek va Kumush", "Yo'lchi va Gulnor", "Saidiy va Munisxon"),
    ("Pirimqul Qodirovning «Avlodlar dovoni» romanida Boburning qaysi o'g'li tarixi aks etgan?", "Humoyun va Akbar", "Komron Mirzo", "Askariy Mirzo", "Hindol Mirzo"),
    ("Oybekning «Qutlug' qon» romanidagi bosh qahramon kim?", "Yo'lchi", "Mirzakarimboy", "Otabek", "Tantiboyvachcha")
]

# 2. TARIX
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
    ("Ilyosxo'ja va Amir Temur/Amir Husayn o'rtasidagi «Loy jangi» qachon bo'lgan?", "1365-yil 22-may", "1370-yil 10-aprel", "1360-yil 15-mart", "1388-yil 12-iyun"),
    ("Jaloliddin Manguberdi mo'g'ullar ustidan g'alaba qozongan Parvon jangi qaysi yilda bo'lgan?", "1221-yil", "1219-yil", "1225-yil", "1231-yil"),
    ("O'zbekiston Respublikasi BMTga qachon a'zo bo'lgan?", "1992-yil 2-mart", "1991-yil 18-noyabr", "1992-yil 8-dekabr", "1993-yil 10-yanvar"),
    ("Aleksandr Makedonskiyga qarshi Spitamen qo'zg'oloni qachon boshlangan?", "Mil. avv. 329-yil", "Mil. avv. 330-yil", "Mil. avv. 327-yil", "Mil. avv. 323-yil"),
    ("Toshkent shahrida Markaziy Osiyodagi ilk metropoliten qachon ishga tushirilgan?", "1977-yil", "1966-yil", "1980-yil", "1972-yil"),
    ("Zahiriddin Muhammad Bobur Hindistonda Boburiylar saltanatiga qachon asos solgan?", "1526-yil (Panipat jangi)", "1512-yil", "1530-yil", "1504-yil")
]

# 3. BIOLOGIYA
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
    ("Odamda ko'rish qobiliyatining pasayishi (shabko'rlik) qaysi vitamin yetishmasligidan kelib chiqadi?", "A vitamini (Retinol)", "D vitamini (Kalsiferol)", "C vitamini", "K vitamini"),
    ("Zamburug'lar dunyosini o'rganuvchi biologiya bo'limi qanday ataladi?", "Mikologiya", "Briologiya", "Algologiya", "Entomologiya")
]

# 4. ONA TILI
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
    ("Talaffuzi yaqin, ammo ma'nosi va yozilishi farq qiluvchi so'zlar (masalan: asr - asir) nima deyiladi?", "Paronimlar", "Omonimlar", "Sinonimlar", "Arxaizmlar"),
    ("Qaysi qatorda barcha so'zlar to'g'ri yozilgan?", "Munosabat, xushomad, tafakkur", "Munosobat, hushomad, tafakkur", "Munasabat, xushomat, tafakur", "Munosabat, hushomat, tafakkur"),
    ("«O'qigan bola» birikmasidagi «o'qigan» so'zi fe'lning qaysi vazifa shakliga kiradi?", "Sifatdosh", "Ravishdosh", "Harakat nomi", "Sof fe'l"),
    ("Ko'makchi fe'lli so'z qo'shilmasini toping:", "O'qib chiqdi", "Sotib oldi", "Qarab qoldi", "Barchasi to'g'ri"),
    ("Gapda «Qanday qilib? Qay tarzda?» so'roqlariga javob bo'luvchi bo'lak qaysi?", "Ravish holi", "Sifatlovchi aniqlovchi", "Vositali to'ldiruvchi", "Maqsad holi")
]

# 5. HUQUQ
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
    """Tanlangan fan va qiyinlik darajasi ('easy' yoki 'hard') bo'yicha savol tuzadi"""
    if subject == "aralash" or subject not in SUBJECTS:
        subject = random.choice(["matematika", "fizika", "adabiyot", "ona_tili", "biologiya", "tarix", "huquq"])

    # 1. MATEMATIKA
    if subject == "matematika":
        if difficulty == "easy":
            turi = random.choice(["add_sub", "mult"])
            if turi == "add_sub":
                a, b, c = random.randint(25, 90), random.randint(10, 40), random.randint(5, 30)
                ans = a + b - c
                q_text = f"📐 Matematika (Oson): Hisoblang: {a} + {b} - {c} = ?"
            else:
                a, b, c = random.randint(4, 12), random.randint(3, 9), random.randint(5, 25)
                ans = a * b + c
                q_text = f"📐 Matematika (Oson): Hisoblang: {a} × {b} + {c} = ?"
        else:
            turi = random.choice(["tenglama", "foiz", "kvadrat_kompleks"])
            if turi == "tenglama":
                x = random.randint(6, 19)
                a = random.randint(4, 12)
                b = random.randint(15, 60)
                res = a * x - b
                ans = x
                q_text = f"📐 Matematika (Bellashuv): Tenglamani yeching: {a}x - {b} = {res}"
            elif turi == "foiz":
                son = random.choice([200, 300, 400, 500, 600, 800, 1200])
                foiz = random.choice([15, 25, 35, 45, 65])
                ans = (son * foiz) // 100
                q_text = f"📐 Matematika (Bellashuv): {son} sonining {foiz}% ini toping."
            else:
                a = random.randint(12, 24)
                b = random.randint(4, 9)
                c = random.randint(5, 12)
                ans = (a * a) - (b * c)
                q_text = f"📐 Matematika (Bellashuv): Hisoblang: {a}² - ({b} × {c}) = ?"

        wrongs = set()
        while len(wrongs) < 3:
            w = ans + random.choice([-12, -8, -5, -3, -2, -1, 1, 2, 3, 5, 8, 12])
            if w != ans and w > 0:
                wrongs.add(str(w))
        w_list = list(wrongs)
        return {"question": q_text, "opt1": str(ans), "opt2": w_list[0], "opt3": w_list[1], "opt4": w_list[2], "correct_opt": 1, "subject": "matematika", "difficulty": difficulty}

    # 2. FIZIKA
    elif subject == "fizika":
        if difficulty == "easy":
            turi = random.choice(["tezlik", "masofa"])
            v = random.choice([40, 50, 60, 70, 80, 90])
            t = random.randint(2, 5)
            s = v * t
            if turi == "tezlik":
                ans = f"{v} km/soat"
                wrongs = [f"{v + 10} km/soat", f"{v - 15} km/soat", f"{v + 20} km/soat"]
                q_text = f"⚡ Fizika (Oson): Avtomobil {s} km masofani {t} soatda bosib o'tdi. Tezligini toping."
            else:
                ans = f"{s} km"
                wrongs = [f"{s + 40} km", f"{max(20, s - 30)} km", f"{v + t} km"]
                q_text = f"⚡ Fizika (Oson): Poezd {v} km/soat tezlik bilan {t} soat yurdi. Qancha yo'l bosgan?"
        else:
            turi = random.choice(["om_qonuni", "kinetik", "quvvat", "nyuton"])
            if turi == "om_qonuni":
                i_val = random.randint(3, 12)
                r_val = random.randint(5, 25)
                u_val = i_val * r_val
                ans = f"{r_val} Om"
                wrongs = [f"{r_val + 4} Om", f"{max(2, r_val - 3)} Om", f"{r_val * 2} Om"]
                q_text = f"⚡ Fizika (Bellashuv): Kuchlanishi {u_val} V bo'lgan o'tkazgichdan {i_val} A tok o'tmoqda. Qarshilikni (R) toping."
            elif turi == "kinetik":
                m = random.choice([2, 4, 6, 8, 10])
                v = random.randint(3, 9)
                ek = (m * (v ** 2)) // 2
                ans = f"{ek} J"
                wrongs = [f"{ek * 2} J", f"{ek + 12} J", f"{m * v} J"]
                q_text = f"⚡ Fizika (Bellashuv): Massasi {m} kg bo'lgan jism {v} m/s tezlik bilan harakatlanmoqda. Kinetik energiyasini (Ek = mv²/2) toping."
            elif turi == "quvvat":
                i_val = random.randint(3, 12)
                t_sec = random.choice([10, 20, 30])
                u_val = 220
                p_val = u_val * i_val
                ans = f"{p_val} Vt"
                wrongs = [f"{p_val + 220} Vt", f"{p_val - 110} Vt", f"{u_val * t_sec} Vt"]
                q_text = f"⚡ Fizika (Bellashuv): 220 V kuchlanishda {i_val} A tok iste'mol qiluvchi dvigatelning quvvati (P) qanchaga teng?"
            else:
                m = random.randint(5, 20)
                a = random.randint(3, 9)
                f_val = m * a
                ans = f"{a} m/s²"
                wrongs = [f"{a + 2} m/s²", f"{max(1, a - 1)} m/s²", f"{a * 2} m/s²"]
                q_text = f"⚡ Fizika (Bellashuv): Massasi {m} kg bo'lgan jismga {f_val} N kuch ta'sir qilmoqda. Tezlanishni (a) toping."
        return {"question": q_text, "opt1": ans, "opt2": wrongs[0], "opt3": wrongs[1], "opt4": wrongs[2], "correct_opt": 1, "subject": "fizika", "difficulty": difficulty}

    # 3. ADABIYOT, TARIX, BIOLOGIYA, ONA TILI, HUQUQ
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
    label = "Oson" if difficulty == "easy" else "Bellashuv"
    return {
        "question": f"{prefix} ({label}): {q_raw}",
        "opt1": o1, "opt2": o2, "opt3": o3, "opt4": o4,
        "correct_opt": 1, "subject": subject, "difficulty": difficulty
    }


# --- BAZA VA AVTOMATIK MIGRATSIYA ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS questions 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT UNIQUE, opt1 TEXT, opt2 TEXT, opt3 TEXT, opt4 TEXT, correct_opt INTEGER, subject TEXT DEFAULT 'aralash', difficulty TEXT DEFAULT 'easy')""")
        await db.execute("""CREATE TABLE IF NOT EXISTS users 
            (user_id INTEGER PRIMARY KEY, role TEXT, status TEXT, pending_mode TEXT DEFAULT 'pay_2', pending_subject TEXT DEFAULT 'aralash')""")
        await db.execute("""CREATE TABLE IF NOT EXISTS user_seen_questions 
            (user_id INTEGER, question_id INTEGER, PRIMARY KEY (user_id, question_id))""")

        # Eski jadvallarga yangi ustunlarni xatosiz qo'shish
        for alter_sql in [
            "ALTER TABLE questions ADD COLUMN subject TEXT DEFAULT 'aralash'",
            "ALTER TABLE questions ADD COLUMN difficulty TEXT DEFAULT 'easy'",
            "ALTER TABLE users ADD COLUMN pending_mode TEXT DEFAULT 'pay_2'",
            "ALTER TABLE users ADD COLUMN pending_subject TEXT DEFAULT 'aralash'"
        ]:
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        cursor = await db.execute("PRAGMA table_info(queues)")
        cols = [row[1] for row in await cursor.fetchall()]
        if not cols:
            await db.execute("""CREATE TABLE queues 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, mode TEXT, status TEXT DEFAULT 'waiting', duel_id INTEGER DEFAULT 0, subject TEXT DEFAULT 'aralash')""")
        else:
            if "id" not in cols:
                await db.execute("ALTER TABLE queues RENAME TO queues_old")
                await db.execute("""CREATE TABLE queues 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, mode TEXT, status TEXT DEFAULT 'waiting', duel_id INTEGER DEFAULT 0, subject TEXT DEFAULT 'aralash')""")
                await db.execute("INSERT INTO queues (user_id, mode, status) SELECT user_id, mode, status FROM queues_old")
                await db.execute("DROP TABLE queues_old")
            try:
                await db.execute("ALTER TABLE queues ADD COLUMN subject TEXT DEFAULT 'aralash'")
            except Exception:
                pass

        await db.commit()

        # Barcha fanlardan Easy va Hard savollarni bazaga yozib qo'yamiz
        for subj in ["matematika", "fizika", "adabiyot", "ona_tili", "biologiya", "tarix", "huquq"]:
            for diff in ["easy", "hard"]:
                for _ in range(12):
                    dq = generate_subject_question(subj, diff)
                    await db.execute(
                        "INSERT OR IGNORE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?,?,?,?,?,1,?,?)",
                        (dq["question"], dq["opt1"], dq["opt2"], dq["opt3"], dq["opt4"], dq["subject"], dq["difficulty"])
                    )
        await db.commit()


async def get_fresh_question(user_ids: list, subject: str = "aralash", difficulty: str = "easy"):
    """Foydalanuvchi tanlagan fan va qiyinlik darajasi bo'yicha yangi savol qaytaradi"""
    new_q = generate_subject_question(subject, difficulty)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?,?,?,?,?,1,?,?)",
            (new_q["question"], new_q["opt1"], new_q["opt2"], new_q["opt3"], new_q["opt4"], new_q["subject"], new_q["difficulty"])
        )
        await db.commit()

        # Matematika va Fizikadan har safar yangi sonli misol tushishi uchun 55% dinamik qaytaramiz
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


# --- XOTIRA VA KLAVIATURALAR ---
class GameCB(CallbackData, prefix="gm"):
    action: str
    val: int = 0

active_timers = {}
youth_sessions = {}  # user_id -> {"subject": str, "step": int, "score": int, "opened": dict, "current_card": int}
active_duels = {}    # duel_id -> duel ma'lumotlari

CARD_EMOJIS = ["🎁", "🎈", "🌟", "🍎", "🚗", "🐶", "🎸", "💎", "🏀"]

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="👦 Yoshlar uchun (Bepul • 3 savol)", callback_data="youth_choose_subj")
    builder.button(text="👨 Kattalar uchun (Bellashuv • Yutuqli)", callback_data="adult_intro")
    builder.adjust(1)
    return builder.as_markup()

def subject_menu_kb(target_prefix: str):
    """Fan tanlash menyusi (target_prefix: 'ysubj' yoki 'asubj')"""
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
    """3x3 formatdagi 9 ta karta"""
    session = youth_sessions.get(user_id, {})
    opened = session.get("opened", {})
    builder = InlineKeyboardBuilder()
    for i in range(1, 10):
        if i in opened:
            builder.button(text=opened[i], callback_data="card_already_opened")
        else:
            emoji = CARD_EMOJIS[i - 1]
            builder.button(text=f"{emoji} {i}", callback_data=GameCB(action="open_card", val=i).pack())
    builder.adjust(3)
    return builder.as_markup()

def admin_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Bitta savol qo'shish", callback_data="admin_add_one")
    builder.button(text="📥 Ko'p savol qo'shish (Ro'yxat)", callback_data="admin_add_bulk")
    builder.button(text="⚡ Avto-generatordan 50 ta qo'shish", callback_data="admin_auto_gen")
    builder.button(text="🔄 Savollar tarixini tozalash", callback_data="admin_reset_seen")
    builder.button(text="🧹 Navbatni tozalash (Reset)", callback_data="admin_clear_queue")
    builder.button(text="📊 Baza statistikasi", callback_data="admin_stats")
    builder.adjust(1)
    return builder.as_markup()


# --- HANDLERLAR ---
router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, role, status, pending_mode, pending_subject) VALUES (?, 'user', 'none', 'pay_2', 'aralash')",
            (message.from_user.id,)
        )
        await db.commit()
        
    safe_name = html.escape(message.from_user.first_name or "Do'stim")
    text = (
        f"👋 Salom, <b>{safe_name}</b>!\n\n"
        f"🃏 Men <b>Joker</b>! Intellektual o'yinimga xush kelibsiz!\n\n"
        f"👦 <b>Yoshlar bo'limi:</b> 9 ta kartadan 3 tasini ochib, oson savollarga javob bering va <b>15% gacha chegirma</b> yuting!\n"
        f"👨 <b>Kattalar bellashuvi:</b> 2 yoki 4 kishi o'rtasida 3 ta savollik tezkor duelda qatnashib, <b>pul yutuqlarini</b> qo'lga kiriting!\n\n"
        f"👇 O'yin turini tanlang:"
    )
    try:
        await message.answer_photo(photo=JOKER_IMG_URL, caption=text, reply_markup=main_menu(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("🏠 <b>Asosiy menyu:</b>", reply_markup=main_menu(), parse_mode="HTML")
    await callback.answer()


# =========================================================================
# 👦 YOSHLAR O'YINI (FAN TANLASH + 9 KARTA + 3 SAVOL + OSON DARAJA)
# =========================================================================

@router.callback_query(F.data == "youth_choose_subj")
async def youth_choose_subj(callback: CallbackQuery):
    text = (
        "👦 <b>Yoshlar uchun bepul o'yin!</b>\n\n"
        "📋 <b>Qoida:</b> 9 ta yashirin kartadan <b>3 tasini</b> tanlaysiz. "
        "Har bir kartada bittadan oson savol bor.\n"
        "• 3 tadan 3 ta topsangiz — <b>15% CHEGIRMA!</b>\n"
        "• 3 tadan 2 ta topsangiz — <b>5% CHEGIRMA!</b>\n\n"
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

@router.callback_query(GameCB.filter(F.action == "open_card"))
async def open_card(callback: CallbackQuery, callback_data: GameCB):
    user_id = callback.from_user.id
    session = youth_sessions.get(user_id)
    if not session:
        youth_sessions[user_id] = {"subject": "aralash", "step": 0, "score": 0, "opened": {}, "current_card": None}
        session = youth_sessions[user_id]

    card_num = callback_data.val
    if card_num in session["opened"]:
        return await callback.answer("⚠️ Bu karta ochilgan!", show_alert=True)

    await callback.answer()
    session["current_card"] = card_num
    subj = session["subject"]
    current_q_num = session["step"] + 1

    # Yoshlar uchun 'easy' (oson) savol olamiz
    q = await get_fresh_question([user_id], subject=subj, difficulty="easy")
    options = [q['opt1'], q['opt2'], q['opt3'], q['opt4']]
    random.shuffle(options)
    correct_text = q[f"opt{q['correct_opt']}"]
    
    builder = InlineKeyboardBuilder()
    for opt in options:
        is_correct = 1 if opt == correct_text else 0
        builder.button(text=opt, callback_data=GameCB(action="youth_answer", val=is_correct).pack())
    builder.adjust(2)
    
    text = (
        f"🃏 <b>{card_num}-karta ochildi! ({current_q_num}/3-savol)</b>\n\n"
        f"❓ {html.escape(q['question'])}\n\n"
        f"⏳ Javob berish uchun <b>20 soniya</b> vaqt:"
    )
    msg = await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    
    if user_id in active_timers:
        active_timers[user_id].cancel()
    active_timers[user_id] = asyncio.create_task(youth_timeout(msg, user_id))

async def youth_timeout(message: Message, user_id: int):
    try:
        await asyncio.sleep(20.0)
        session = youth_sessions.get(user_id)
        if not session:
            return
        card_num = session.get("current_card") or 1
        session["opened"][card_num] = "⏳"
        session["step"] += 1
        await proceed_youth_game(message, user_id, "⏳ <b>Vaqt tugadi!</b>")
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
    finally:
        active_timers.pop(user_id, None)

@router.callback_query(GameCB.filter(F.action == "youth_answer"))
async def youth_check_answer(callback: CallbackQuery, callback_data: GameCB):
    user_id = callback.from_user.id
    if user_id in active_timers:
        active_timers[user_id].cancel()
        active_timers.pop(user_id, None)

    session = youth_sessions.get(user_id)
    if not session:
        return await callback.message.edit_text("🏠 Asosiy menyu:", reply_markup=main_menu())

    await callback.answer()
    card_num = session.get("current_card") or 1
    session["step"] += 1

    if callback_data.val == 1:
        session["score"] += 1
        session["opened"][card_num] = "✅"
        status_line = "✅ <b>Barakalla, to'g'ri javob!</b>"
    else:
        session["opened"][card_num] = "❌"
        status_line = "❌ <b>Afsuski, xato javob!</b>"

    await proceed_youth_game(callback.message, user_id, status_line)

async def proceed_youth_game(message: Message, user_id: int, status_line: str):
    session = youth_sessions.get(user_id)
    if not session:
        return
    step = session["step"]
    score = session["score"]
    subj_name = SUBJECTS.get(session["subject"], "🌐 Aralash")

    # Agar hali 3 ta savol tugamagan bo'lsa, 9 ta kartani qayta ko'rsatamiz
    if step < 3:
        text = (
            f"{status_line}\n\n"
            f"📚 Fan: <b>{subj_name}</b>\n"
            f"📊 Natija: <b>{step}/3 savol</b> (To'g'ri: <b>{score} ta</b>)\n\n"
            f"👇 <b>Navbatdagi ({step + 1}-chi) kartani tanlang:</b>"
        )
        await message.edit_text(text, reply_markup=get_9_cards_kb(user_id), parse_mode="HTML")
    else:
        # 3 ta savol yakunlandi!
        youth_sessions.pop(user_id, None)
        if score == 3:
            text = (
                f"{status_line}\n\n"
                f"🎉 <b>TABRIKLAYMIZ, SIZ 3/3 NATIJA BILAN YUTDINGIZ!</b> 🎉\n\n"
                f"🎁 Yutug'ingiz: <b>15% CHEGIRMA VAUCHERI!</b>\n"
                f"📍 Urgut tumanidagi 3-umumta'lim maktabi ro'parasidagi <b>Super Mini Market</b>dan xarid qiling.\n\n"
                f"📸 Chegirmadan foydalanish uchun ushbu xabarni <b>skrinshot</b> qilib oling!"
            )
        elif score == 2:
            text = (
                f"{status_line}\n\n"
                f"👏 <b>Yaxshi natija! Siz 3 tadan 2 ta savolni topdingiz!</b>\n\n"
                f"🎁 Rag'batlantiruvchi yutuq: <b>5% CHEGIRMA!</b>\n"
                f"📍 Urgut tumanidagi 3-umumta'lim maktabi ro'parasidagi <b>Super Mini Market</b>dan xarid qiling.\n"
                f"<i>(15% chegirma yutish uchun yana urinib ko'rishingiz mumkin!)</i>"
            )
        else:
            text = (
                f"{status_line}\n\n"
                f"📉 <b>Natijangiz: 3 tadan {score} ta to'g'ri.</b>\n\n"
                f"🎰 Senga Jokerning xabari bor, o'qib ko'r:\n"
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
        "• Har bir ishtirokchiga ketma-ket <b>3 ta murakkabroq savol</b> beriladi (ishtirokchilar tanlagan fanlardan).\n"
        "• Kim 3 ta savoldan <b>eng ko'p to'g'ri javob</b> topsa — o'sha g'olib!\n"
        "• Agar to'g'ri javoblar soni teng bo'lib qolsa (masalan, 3/3 va 3/3), savollarga <b>eng qisqa vaqt (soniya)</b> sarflagan ishtirokchi yutadi!\n\n"
        "💰 <b>Yutuq miqdori:</b>\n"
        "• 👥 2 kishilik (kirish 12,000 so'm) 👉 Yutuq: <b>18,000 so'm</b>\n"
        "• 👥 4 kishilik (kirish 17,000 so'm) 👉 Yutuq: <b>25,500 so'm</b>\n"
        "<i>(Yutuq g'olibning plastik kartasiga darhol o'tkazib beriladi!)</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>Bellashuv turini tanlang:</b>"
    )
    await callback.message.answer(text, reply_markup=adult_mode_kb(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("adult_mode:"))
async def adult_choose_subj(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[1]  # pay_2 yoki pay_4
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
        f"📚 <b>Endi o'zingiz eng yaxshi biladigan fanni tanlang!</b>\n"
        f"<i>(Bellashuvdagi 3 ta savolning biri aynan siz tanlagan fandan tushadi):</i>"
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


# --- CHEK QABUL QILISH VA ADMIN TASDIQLASHI ---
@router.message(F.photo | F.document)
async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
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
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        elif message.document:
            await bot.send_document(ADMIN_ID, message.document.file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
            
        await message.answer("⏳ <b>Chek adminga muvaffaqiyatli yuborildi!</b>\nTasdiqlanishini kuting...", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}")

@router.message(StateFilter(GameStates.waiting_for_receipt))
async def wrong_receipt_format(message: Message):
    if message.text and message.text.startswith("/"):
        return
    await message.answer("⚠️ <b>Iltimos, to'lov chekining skrinshotini (rasm yoki fayl shaklida) yuboring!</b>", parse_mode="HTML")

@router.callback_query(F.data.startswith("approve"))
async def approve_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Siz admin emassiz!", show_alert=True)
    
    data_str = callback.data
    try:
        if ":" in data_str:
            _, mode, user_id_str = data_str.split(":")
            user_id = int(user_id_str)
        else:
            prefix_and_mode, user_id_str = data_str.rsplit("_", 1)
            mode = prefix_and_mode.replace("approve_", "")
            user_id = int(user_id_str)
    except Exception as e:
        return await callback.answer(f"Xato: {e}", show_alert=True)

    await callback.answer("✅ To'lov tasdiqlandi!")
    
    try:
        old_caption = callback.message.caption or "🧾 Chek"
        await callback.message.edit_caption(caption=old_caption + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML", reply_markup=None)
    except Exception:
        pass

    try:
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
                    f"Qolgan ishtirokchilar qo'shilishi bilan 5 soniyalik ogohlantirish keladi va o'yin boshlanadi!",
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
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"⚠️ Xato: {e}")

@router.callback_query(F.data.startswith("reject"))
async def reject_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Siz admin emassiz!", show_alert=True)
    
    data_str = callback.data
    try:
        rejected_user_id = int(data_str.split(":")[1] if ":" in data_str else data_str.rsplit("_", 1)[1])
    except Exception as e:
        return await callback.answer(f"Xato: {e}", show_alert=True)
    
    await callback.answer("❌ Rad etildi!")
    try:
        old_caption = callback.message.caption or "🧾 Chek"
        await callback.message.edit_caption(caption=old_caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML", reply_markup=None)
    except Exception:
        pass
    
    try:
        await bot.send_message(rejected_user_id, "❌ <b>Afsuski, chekingiz rad etildi.</b> Iltimos, qaytadan urinib ko'ring.", parse_mode="HTML")
    except Exception:
        pass


# =========================================================================
# ⚔️ KATTALAR 3 SAVOLLIK DUEL TIZIMI (BALL + TEZLIK + JADVAL)
# =========================================================================

async def launch_3_question_duel(bot: Bot, duel_id: int, players: list, subjects: list, duel_type: str, prize: int):
    unique_players = list(dict.fromkeys(players))
    
    # 3 ta savolning fanlarini ishtirokchilar tanlagan fanlardan shakllantiramiz
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

    # 1. Barcha ishtirokchilarga 5 soniyalik tayyorgarlik va tushuntirish xabarini yuboramiz
    prep_text = (
        f"⚔️ <b>DIQQAT! BARCHA ISHTIROKCHILAR YIG'ILDI!</b> ⚔️\n"
        f"🎮 Rejim: <b>{duel_type}</b> | 🏆 Yutuq: <b>{prize:,} so'm</b>\n\n"
        f"📋 <b>Eslatma:</b> Sizga ketma-ket <b>3 ta savol</b> beriladi.\n"
        f"• Eng ko'p to'g'ri javob topgan va eng kam vaqt sarflagan ishtirokchi g'olib bo'ladi!\n\n"
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

    # 2. Har bir o'yinchiga 1-savolni yuboramiz va vaqtni boshlaymiz
    now = time.monotonic()
    for uid in unique_players:
        active_duels[duel_id]["players"][uid]["start_time"] = now
        await send_duel_question(bot, duel_id, uid, 0)

    # 3. Umumiy duel taymeri (60 soniya ichida javob bermaganlar uchun)
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
        # val ichida: duel_id (4 xona) + step_idx (1 xona) + is_correct (1 xona)
        packed_val = int(f"{duel_id}{step_idx}{is_correct}")
        builder.button(text=opt, callback_data=GameCB(action="duel_ans", val=packed_val).pack())
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

@router.callback_query(GameCB.filter(F.action == "duel_ans"))
async def handle_duel_answer(callback: CallbackQuery, callback_data: GameCB, bot: Bot):
    val_str = str(callback_data.val)
    duel_id = int(val_str[:-2])
    step_idx = int(val_str[-2])
    is_correct = (val_str[-1] == "1")
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

    # Agar 3 ta savol hali tugamagan bo'lsa, darhol keyingi savolni chiqaramiz
    if p_data["step"] < 3:
        await send_duel_question(bot, duel_id, user_id, p_data["step"], edit_msg=callback.message)
    else:
        # Shu o'yinchi 3 ta savolni tugatdi! Vaqtini yozib olamiz
        p_data["elapsed"] = round(time.monotonic() - p_data["start_time"], 2)
        p_data["done"] = True

        # Barcha o'yinchilar tugatganini tekshiramiz
        all_done = all(p["done"] for p in duel["players"].values())
        if all_done:
            await finalize_duel(bot, duel_id)
        else:
            try:
                await callback.message.edit_text(
                    f"🏁 <b>Siz barcha 3 ta savolga javob berdingiz!</b>\n\n"
                    f"📊 Natijangiz: <b>3 tadan {p_data['score']} ta to'g'ri</b>\n"
                    f"⏱ Sarflangan vaqt: <b>{p_data['elapsed']} soniya</b>\n\n"
                    f"⏳ Raqibingiz javob berishini kuting, hozir yakuniy natija chiqadi...",
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

    # O'yinchilarni (1) eng ko'p to'g'ri javob va (2) eng kam vaqt bo'yicha saralaymiz
    ranking = sorted(
        duel["players"].items(),
        key=lambda item: (-item[1]["score"], item[1]["elapsed"])
    )

    winner_id, winner_info = ranking[0]
    prize = duel["prize"]

    # Umumiy natijalar jadvalini tuzamiz
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    board_lines = []
    for idx, (uid, info) in enumerate(ranking):
        medal = medals[idx] if idx < len(medals) else "▫️"
        time_str = f"{info['elapsed']} sek" if info["done"] else "vaqt tugadi"
        board_lines.append(f"{medal} <b>{html.escape(info['name'])}</b> — {info['score']}/3 ta ({time_str})")
    leaderboard_text = "\n".join(board_lines)

    # G'olibga xabar
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET status = ? WHERE user_id = ?", (f"won_{prize}", winner_id))
            await db.commit()

        winner_msg = (
            f"🎉 <b>TABRIKLAYMIZ, BELLASHUVDA SIZ G'OLIB BO'LDINGIZ!</b> 🎉\n\n"
            f"📊 <b>Yakuniy natijalar jadvali:</b>\n{leaderboard_text}\n\n"
            f"💰 Yutug'ingiz: <b>{prize:,} so'm!</b>\n"
            f"💳 Admin pul o'tkazishi uchun <b>karta raqamingiz va ism-sharifingizni</b> bitta xabarda yozib yuboring:"
        )
        await bot.send_message(winner_id, winner_msg, parse_mode="HTML")
        await bot.send_message(
            ADMIN_ID,
            f"⚔️ <b>Bellashuv yakunlandi!</b>\n"
            f"🏆 G'olib: <b>{html.escape(winner_info['name'])}</b> (ID: <code>{winner_id}</code>)\n"
            f"📊 Natijasi: {winner_info['score']}/3 ta ({winner_info['elapsed']} sek)\n"
            f"💰 Yutuq: <b>{prize:,} so'm</b>\n\n"
            f"⏳ G'olibdan karta raqami kutilmoqda...",
            parse_mode="HTML"
        )
    except Exception:
        pass

    # Yutqazganlarga natijalar jadvali va Joker xabari
    for uid, info in ranking[1:]:
        loser_msg = (
            f"🚨 <b>BELLASHUV YAKUNLANDI — YUTQAZDINGIZ!</b> 🚨\n\n"
            f"📊 <b>Yakuniy natijalar jadvali:</b>\n{leaderboard_text}\n\n"
            f"Raqibingiz sizdan ancha tezroq va aniqroq bo'lib chiqdi.\n"
            f"Keyingi safar albatta yutasiz! 🧠🔥"
        )
        try:
            await bot.send_message(uid, loser_msg, reply_markup=main_menu(), parse_mode="HTML")
        except Exception:
            pass

    active_duels.pop(duel_id, None)


# --- G'OLIBDAN KARTA RAQAMINI QABUL QILISH ---
@router.message(F.text & ~F.text.startswith("/"))
async def catch_text_messages(message: Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    if current_state == GameStates.adding_single_question.state:
        return await process_single_question(message, state)
    elif current_state == GameStates.adding_bulk_questions.state:
        return await process_bulk_questions(message, state)

    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()

    if row and row[0] and row[0].startswith("won_"):
        prize = int(row[0].split("_")[1])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET status = 'none' WHERE user_id = ?", (user_id,))
            await db.commit()

        safe_name = html.escape(message.from_user.full_name or "G'olib")
        safe_card = html.escape(message.text)

        await bot.send_message(
            ADMIN_ID,
            f"💳 <b>G'olib karta raqamini yubordi!</b>\n\n"
            f"👤 Ism: <b>{safe_name}</b>\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💰 Yutuq: <b>{prize:,} so'm</b>\n"
            f"📝 Karta: <code>{safe_card}</code>",
            parse_mode="HTML"
        )
        await message.answer(
            "✅ <b>Karta raqamingiz adminga yuborildi!</b> Tez orada yutug'ingiz tashlab beriladi.",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )


# --- ADMIN PANEL HANDLERLARI (/admin) ---
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer("🛠 <b>Admin panelga xush kelibsiz!</b>\nSavollarni yangilash va boshqarish:", reply_markup=admin_menu_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_clear_queue")
async def admin_clear_queue(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM queues")
        await db.commit()
    await callback.answer("🧹 Navbat to'liq tozalandi!", show_alert=True)

@router.callback_query(F.data == "admin_auto_gen")
async def admin_auto_gen(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
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
    await callback.answer(f"⚡ 7 ta fandan {added} ta yangi savol bazaga qo'shildi!", show_alert=True)

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        q_count = (await (await db.execute("SELECT COUNT(*) FROM questions")).fetchone())[0]
        u_count = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        w2_count = (await (await db.execute("SELECT COUNT(*) FROM queues WHERE status = 'waiting' AND mode = 'pay_2'")).fetchone())[0]
        w4_count = (await (await db.execute("SELECT COUNT(*) FROM queues WHERE status = 'waiting' AND mode = 'pay_4'")).fetchone())[0]
    
    text = (
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"❓ Bazadagi savollar: <b>{q_count} ta</b>\n"
        f"👥 Foydalanuvchilar: <b>{u_count} ta</b>\n"
        f"⏳ 2 kishilik navbatda: <b>{w2_count}/2 ta</b>\n"
        f"⏳ 4 kishilik navbatda: <b>{w4_count}/4 ta</b>"
    )
    try:
        await callback.message.edit_text(text, reply_markup=admin_menu_kb(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "admin_reset_seen")
async def admin_reset_seen(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_seen_questions")
        await db.commit()
    await callback.answer("✅ Tarix tozalandi!", show_alert=True)

@router.callback_query(F.data == "admin_add_one")
async def admin_add_one(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(GameStates.adding_single_question)
    await callback.message.answer("✍️ <code>Savol | To'g'ri | Xato1 | Xato2 | Xato3</code> formatida yuboring:", parse_mode="HTML")
    await callback.answer()

async def process_single_question(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 5:
        return await message.answer("❌ Format xato!", parse_mode="HTML")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?, ?, ?, ?, ?, 1, 'aralash', 'hard')", parts)
        await db.commit()
    await state.clear()
    await message.answer("✅ Savol qo'shildi!", reply_markup=admin_menu_kb())

@router.callback_query(F.data == "admin_add_bulk")
async def admin_add_bulk(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(GameStates.adding_bulk_questions)
    await callback.message.answer("📥 Har bir qatorda bittadan savol yuboring:", parse_mode="HTML")
    await callback.answer()

async def process_bulk_questions(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    added = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for line in message.text.strip().split("\n"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 5:
                await db.execute("INSERT OR REPLACE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt, subject, difficulty) VALUES (?, ?, ?, ?, ?, 1, 'aralash', 'hard')", parts)
                added += 1
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Jami {added} ta savol qo'shildi!", reply_markup=admin_menu_kb())


# --- RENDER SERVER (24/7 UZLUKSIZ ISHLASHI UCHUN) ---
async def handle(request):
    return web.Response(text="Bot ishlayapti! 🤖")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- ISHGA TUSHIRISH ---
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
    
    print("🤖 Bot yangilangan 9-karta, 3-savol va fan tanlash tizimi bilan ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
