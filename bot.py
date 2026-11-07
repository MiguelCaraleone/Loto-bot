import asyncio
import logging
import aiosqlite
import random
import os
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

# --- FSM HOLATLARI ---
class GameStates(StatesGroup):
    waiting_for_receipt = State()
    waiting_for_card = State()
    adding_single_question = State()
    adding_bulk_questions = State()

# =========================================================================
# 📚 7 TA FAN BO'YICHA AVTOMATIK SAVOL GENERATORI BAZASI
# =========================================================================

ADABIYOT_DATA = [
    ("«O'tkan kunlar» romani", "Abdulla Qodiriy"),
    ("«Mehrobdan chayon» romani", "Abdulla Qodiriy"),
    ("«Kecha va kunduz» romani", "Cho'lpon"),
    ("«Yulduzli tunlar» romani", "Pirimqul Qodirov"),
    ("«Avlodlar dovoni» romani", "Pirimqul Qodirov"),
    ("«Ulug'bek xazinasi» romani", "Odil Yoqubov"),
    ("«Dunyoning ishlari» qissasi", "O'tkir Hoshimov"),
    ("«Ikki eshik orasi» romani", "O'tkir Hoshimov"),
    ("«Tushda kechgan umrlar» romani", "O'tkir Hoshimov"),
    ("«Sariq devni minib» asari", "Xudoyberdi To'xtaboyev"),
    ("«Shum bola» qissasi", "G'afur G'ulom"),
    ("«Yodgor» qissasi", "G'afur G'ulom"),
    ("«Sarob» romani", "Abdulla Qahhor"),
    ("«O'g'ri» hikoyasi", "Abdulla Qahhor"),
    ("«Bemor» hikoyasi", "Abdulla Qahhor"),
    ("«Qutlug' qon» romani", "Oybek"),
    ("«Navoiy» romani", "Oybek"),
    ("«Xamsa» asari (turkiy tilda)", "Alisher Navoiy"),
    ("«Lison ut-tayr» dostoni", "Alisher Navoiy"),
    ("«Boburnoma» memuar asari", "Zahiriddin Muhammad Bobur"),
    ("«Ufq» trilogiyasi", "Said Ahmad"),
    ("«Kelinlar qo'zg'oloni» komediyasi", "Said Ahmad"),
    ("«O'zbegim» qasidasi", "Erkin Vohidov"),
    ("«Ruhlar isyoni» dostoni", "Erkin Vohidov"),
    ("«O'zbekiston» qasidasi", "Abdulla Oripov"),
    ("«Sohibqiron» dramasi", "Abdulla Oripov"),
    ("«Alpomish» dostoni", "Xalq og'zaki ijodi"),
    ("«Chinor» romani", "Asqad Muxtor"),
    ("«Qora ko'zlar» romani", "Parda Tursun"),
    ("«Me'mor» romani", "Mirmuhsin")
]

TARIX_SANALAR = [
    ("Amir Temur tavallud topgan yil", "1336-yil"),
    ("Zahiriddin Muhammad Bobur tug'ilgan yil", "1483-yil"),
    ("Alisher Navoiy tavallud topgan yil", "1441-yil"),
    ("Mirzo Ulug'bek tavallud topgan yil", "1394-yil"),
    ("Jaloliddin Manguberdi vafot etgan yil", "1231-yil"),
    ("O'zbekiston BMTga a'zo bo'lgan yil", "1992-yil 2-mart"),
    ("O'zbekiston Konstitutsiyasi qabul qilingan kun", "1992-yil 8-dekabr"),
    ("O'zbekiston Davlat bayrog'i qabul qilingan yil", "1991-yil 18-noyabr"),
    ("O'zbekiston Davlat gerbi qabul qilingan yil", "1992-yil 2-iyul"),
    ("O'zbekiston milliy valyutasi — so'm muomalaga kiritilgan yil", "1994-yil 1-iyul"),
    ("Ikkinchi jahon urushi boshlangan yil", "1939-yil"),
    ("Birinchi jahon urushi yakunlangan yil", "1918-yil"),
    ("Toshkentda birinchi metro ishga tushgan yil", "1977-yil"),
    ("Loy jangi bo'lib o'tgan yil", "1365-yil"),
    ("Anqara jangi bo'lib o'tgan yil", "1402-yil"),
    ("Parfiya jangi (Jaloliddin va mo'g'ullar o'rtasida)", "1221-yil"),
    ("Spitamen qo'zg'oloni boshlangan davr", "Mil. avv. 329-yil")
]

BIOLOGIYA_DATA = [
    ("Hujayraning energiya stansiyasi qaysi organoid hisoblanadi?", "Mitoxondriya"),
    ("O'simlik bargiga yashil rang beruvchi plastida qaysi?", "Xloroplast"),
    ("Hujayrada oqsil sintezi qayerda amalga oshadi?", "Ribosoma"),
    ("Irsiy axborot (DNK) hujayraning qaysi qismida saqlanadi?", "Yadro"),
    ("Inson yuragi nechta kameradan iborat?", "4 ta"),
    ("Baliqlar yuragi nechta kameradan iborat?", "2 ta"),
    ("Baqa va qurbaqalar yuragi nechta kameradan iborat?", "3 ta"),
    ("Qonda kislorod tashuvchi modda va hujayra qaysi?", "Eritrotsit (Gemoglobin)"),
    ("Organizmni mikroblardan himoya qiluvchi qon hujayrasi?", "Leykotsit"),
    ("Qonning ivishida ishtirok etuvchi qon plastinkalari?", "Trombotsit"),
    ("Ko'rish qobiliyati pasayganda (shabko'rlikda) qaysi vitamin yetishmaydi?", "A vitamini"),
    ("Suyaklar mustahkamligi va raxit kasalligi oldini olish uchun zarur vitamin?", "D vitamini"),
    ("Immunitetni oshiruvchi va singa kasalligini oldini oluvchi vitamin?", "C vitamini"),
    ("Biologiyada irsiyat va o'zgaruvchanlikni o'rganuvchi fan?", "Genetika"),
    ("Tirik organizmlarning tashqi va ichki tuzilishini o'rganuvchi fan?", "Morfologiya va Anatomiya"),
    ("Zamburug'larni o'rganuvchi biologiya bo'limi?", "Mikologiya"),
    ("Qushlarni o'rganuvchi zoologiya bo'limi?", "Ornitologiya")
]

ONA_TILI_DATA = [
    ("Ona tili: Qaysi qatorda so'z to'g'ri yozilgan?", "Taassurot", "Tassurot", "Taasurot", "Tasurot"),
    ("Ona tili: Qaysi so'z imlo qoidasiga ko'ra to'g'ri yozilgan?", "Munosabat", "Munosobat", "Munasabat", "Munozabat"),
    ("Ona tili: To'g'ri yozilgan so'zni toping:", "Xushomad", "Hushomad", "Xushomat", "Hushomat"),
    ("Ona tili: «Kitob» so'zi qaysi so'z turkumiga kiradi?", "Ot", "Sifat", "Fe'l", "Ravish"),
    ("Ona tili: «Chiroyli» so'zi qaysi so'z turkumiga kiradi?", "Sifat", "Ot", "Son", "Olmosh"),
    ("Ona tili: «Men, sen, u» so'zlari qaysi so'z turkumiga mansub?", "Kishilik olmoshi", "Ot", "Ravish", "Sifat"),
    ("Ona tili: Gapning eng asosiy bosh bo'laklari qaysilar?", "Ega va kesim", "Aniqlovchi va to'ldiruvchi", "Hol va ega", "Kesim va to'ldiruvchi"),
    ("Ona tili: Shakldosh so'zlar tilshunoslikda nima deb ataladi?", "Omonimlar", "Sinonimlar", "Antonimlar", "Paronimlar"),
    ("Ona tili: Ma'nodosh so'zlar tilshunoslikda nima deb ataladi?", "Sinonimlar", "Omonimlar", "Antonimlar", "Uyadosh so'zlar"),
    ("Ona tili: Zid ma'noli so'zlar tilshunoslikda nima deb ataladi?", "Antonimlar", "Sinonimlar", "Omonimlar", "Ko'p ma'noli so'zlar"),
    ("Ona tili: O'zbek lotin alifbosida nechta harf va harf birikmasi bor?", "29 ta (va 1 ta tutuq belgisi)", "33 ta", "26 ta", "35 ta"),
    ("Ona tili: «Kim? Nima? Qayer?» so'roqlariga javob bo'luvchi so'z turkumi?", "Ot", "Fe'l", "Sifat", "Son"),
    ("Ona tili: «Qanday? Qanaqa?» so'roqlariga javob bo'luvchi gap bo'lagi?", "Sifatlovchi aniqlovchi", "To'ldiruvchi", "Ega", "Kesim")
]

HUQUQ_DATA = [
    ("Huquq: Yangi tahrirdagi O'zbekiston Konstitutsiyasi nechta bob va moddadan iborat?", "6 bo'lim, 27 bob, 155 modda", "6 bo'lim, 26 bob, 128 modda", "5 bo'lim, 25 bob, 150 modda", "7 bo'lim, 30 bob, 160 modda"),
    ("Huquq: Yangi tahrirdagi O'zbekiston Konstitutsiyasi qachon referendumda qabul qilindi?", "2023-yil 30-aprel", "2022-yil 8-dekabr", "2021-yil 1-sentabr", "2024-yil 1-yanvar"),
    ("Huquq: O'zbekistonda davlat hokimiyatining yagona manbai kim?", "Xalq", "Vazirlar Mahkamasi", "Oliy Majlis", "Konstitutsiyaviy sud"),
    ("Huquq: O'zbekiston Respublikasida qonun chiqaruvchi oliy organ qaysi?", "Oliy Majlis (Qonunchilik palatasi va Senat)", "Vazirlar Mahkamasi", "Adliya vazirligi", "Oliy sud"),
    ("Huquq: O'zbekiston Respublikasida ijro etuvchi hokimiyatni kim amalga oshiradi?", "Vazirlar Mahkamasi", "Oliy Majlis", "Prokuratura", "Konstitutsiyaviy sud"),
    ("Huquq: O'zbekistonda fuqarolar necha yoshdan saylash huquqiga ega bo'ladilar?", "18 yoshdan", "16 yoshdan", "21 yoshdan", "25 yoshdan"),
    ("Huquq: O'zbekiston Respublikasi Prezidenti necha yil muddatga saylanadi?", "7 yil", "5 yil", "4 yil", "6 yil"),
    ("Huquq: Umumiy jinoiy javobgarlikka tortish necha yoshdan boshlanadi (og'ir jinoyatlardan tashqari)?", "16 yoshdan", "18 yoshdan", "14 yoshdan", "20 yoshdan"),
    ("Huquq: O'zbekistonda nikoh yoshi erkaklar va ayollar uchun necha yosh etib belgilangan?", "18 yosh", "17 va 18 yosh", "20 yosh", "16 va 18 yosh"),
    ("Huquq: Mehnat kodeksiga ko'ra, xodim uchun normal ish vaqti haftasiga necha soatdan oshmasligi kerak?", "40 soatdan", "48 soatdan", "36 soatdan", "50 soatdan"),
    ("Huquq: BMT tomonidan «Inson huquqlari umumjahon deklaratsiyasi» qachon qabul qilingan?", "1948-yil 10-dekabr", "1945-yil 24-oktabr", "1991-yil 31-avgust", "1950-yil 1-iyun")
]

def generate_multi_subject_question():
    subject = random.choice(["matematika", "fizika", "adabiyot", "tarix", "biologiya", "ona_tili", "huquq"])

    if subject == "matematika":
        turi = random.choice(["ko'paytirish", "qo'shish_ayirish", "kvadrat", "tenglama"])
        if turi == "ko'paytirish":
            a, b, c = random.randint(6, 18), random.randint(4, 14), random.randint(10, 50)
            ans = a * b + c
            question = f"📐 Matematika: Hisoblang: {a} × {b} + {c} = ?"
        elif turi == "qo'shish_ayirish":
            a, b, c = random.randint(60, 200), random.randint(20, 80), random.randint(15, 60)
            ans = a - b + c
            question = f"📐 Matematika: Hisoblang: {a} - {b} + {c} = ?"
        elif turi == "kvadrat":
            a, b = random.randint(11, 22), random.randint(10, 40)
            ans = (a * a) - b
            question = f"📐 Matematika: Hisoblang: {a}² - {b} = ?"
        else:
            x = random.randint(3, 15)
            a = random.randint(2, 9)
            b = random.randint(5, 30)
            res = a * x + b
            ans = x
            question = f"📐 Matematika: Tenglamani yeching: {a}x + {b} = {res}"

        wrongs = set()
        while len(wrongs) < 3:
            w = ans + random.choice([-10, -6, -4, -2, -1, 1, 2, 4, 6, 10])
            if w != ans and w > 0:
                wrongs.add(str(w))
        w_list = list(wrongs)
        return {"question": question, "opt1": str(ans), "opt2": w_list[0], "opt3": w_list[1], "opt4": w_list[2], "correct_opt": 1}

    elif subject == "fizika":
        turi = random.choice(["tezlik", "kuch", "om_qonuni", "quvvat"])
        if turi == "tezlik":
            v = random.choice([40, 50, 60, 70, 80, 90, 100])
            t = random.randint(2, 6)
            s = v * t
            ans = f"{v} km/soat"
            wrongs = [f"{v + 15} km/soat", f"{max(10, v - 20)} km/soat", f"{v + 25} km/soat"]
            question = f"⚡ Fizika: Avtomobil {s} km masofani {t} soatda bosib o'tdi. Uning tezligini toping."
        elif turi == "kuch":
            m = random.randint(4, 25)
            a = random.randint(2, 8)
            f_val = m * a
            ans = f"{f_val} N"
            wrongs = [f"{f_val + 10} N", f"{max(2, f_val - 6)} N", f"{m + a} N"]
            question = f"⚡ Fizika: Massasi {m} kg bo'lgan jismga {a} m/s² tezlanish berish uchun qancha kuch (F) kerak?"
        elif turi == "om_qonuni":
            i_val = random.randint(2, 10)
            r_val = random.randint(4, 20)
            u_val = i_val * r_val
            ans = f"{i_val} A"
            wrongs = [f"{i_val + 3} A", f"{max(1, i_val - 1)} A", f"{i_val * 2} A"]
            question = f"⚡ Fizika: Kuchlanishi {u_val} V va qarshiligi {r_val} Om bo'lgan o'tkazgichdan qanday tok kuchi (I) o'tadi?"
        else:
            u_val = 220
            i_val = random.randint(2, 10)
            p_val = u_val * i_val
            ans = f"{p_val} Vt"
            wrongs = [f"{p_val + 220} Vt", f"{p_val - 110} Vt", f"{u_val + i_val} Vt"]
            question = f"⚡ Fizika: 220 V kuchlanishli tarmoqda {i_val} A tok oladigan elektr jihozining quvvati (P) qanchaga teng?"

        return {"question": question, "opt1": ans, "opt2": wrongs[0], "opt3": wrongs[1], "opt4": wrongs[2], "correct_opt": 1}

    elif subject == "adabiyot":
        work, author = random.choice(ADABIYOT_DATA)
        all_authors = list({a for _, a in ADABIYOT_DATA if a != author})
        wrongs = random.sample(all_authors, 3)
        question = f"📚 Adabiyot: Mashhur {work} muallifi kim?"
        return {"question": question, "opt1": author, "opt2": wrongs[0], "opt3": wrongs[1], "opt4": wrongs[2], "correct_opt": 1}

    elif subject == "tarix":
        event, date_ans = random.choice(TARIX_SANALAR)
        all_dates = list({d for _, d in TARIX_SANALAR if d != date_ans})
        wrongs = random.sample(all_dates, 3)
        question = f"🏛 Tarix: {event} qaysi qatorda to'g'ri ko'rsatilgan?"
        return {"question": question, "opt1": date_ans, "opt2": wrongs[0], "opt3": wrongs[1], "opt4": wrongs[2], "correct_opt": 1}

    elif subject == "biologiya":
        q_text, ans = random.choice(BIOLOGIYA_DATA)
        all_ans = list({a for _, a in BIOLOGIYA_DATA if a != ans})
        wrongs = random.sample(all_ans, 3)
        question = f"🧬 Biologiya: {q_text}"
        return {"question": question, "opt1": ans, "opt2": wrongs[0], "opt3": wrongs[1], "opt4": wrongs[2], "correct_opt": 1}

    elif subject == "ona_tili":
        q_text, opt1, opt2, opt3, opt4 = random.choice(ONA_TILI_DATA)
        return {"question": f"📝 {q_text}", "opt1": opt1, "opt2": opt2, "opt3": opt3, "opt4": opt4, "correct_opt": 1}

    else:
        q_text, opt1, opt2, opt3, opt4 = random.choice(HUQUQ_DATA)
        return {"question": f"⚖️ {q_text}", "opt1": opt1, "opt2": opt2, "opt3": opt3, "opt4": opt4, "correct_opt": 1}


# --- BAZA VA AVTOMATIK MIGRATSIYA ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS questions 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT UNIQUE, opt1 TEXT, opt2 TEXT, opt3 TEXT, opt4 TEXT, correct_opt INTEGER)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS users 
            (user_id INTEGER PRIMARY KEY, role TEXT, status TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS queues 
            (user_id INTEGER PRIMARY KEY, mode TEXT, status TEXT DEFAULT 'waiting', duel_id INTEGER DEFAULT 0)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS user_seen_questions 
            (user_id INTEGER, question_id INTEGER, PRIMARY KEY (user_id, question_id))""")
        
        # MUHIM TUZATISH: Agar eski bazada duel_id ustuni bo'lmasa, avtomatik qo'shamiz
        try:
            await db.execute("ALTER TABLE queues ADD COLUMN duel_id INTEGER DEFAULT 0")
        except Exception:
            pass
            
        await db.commit()

        cursor = await db.execute("SELECT COUNT(*) FROM questions")
        count = (await cursor.fetchone())[0]

        if count == 0:
            print("⏳ Barcha fanlardan boshlang'ich savollar bazaga yozilmoqda...")
            savollar = [
                ("O'zbekistonning poytaxti qaysi shahar?", "Toshkent", "Samarqand", "Buxoro", "Namangan", 1),
                ("📚 Adabiyot: «O'tkan kunlar» romanining bosh qahramoni kim?", "Otabek", "Anvar", "Yo'lchi", "Me'mor", 1),
                ("📝 Ona tili: O'zbek tiliga Davlat tili maqomi qachon berilgan?", "1989-yil 21-oktabr", "1991-yil 1-sentabr", "1992-yil 8-dekabr", "1990-yil 20-iyun", 1),
                ("⚡ Fizika: Yorug'likning vakuumdagi tezligi sekundiga necha km?", "300 000 km/s", "150 000 km/s", "340 m/s", "100 000 km/s", 1),
                ("🧬 Biologiya: Inson tanasidagi eng katta bez qaysi?", "Jigar", "Oshqozon osti bezi", "Qalqonsimon bez", "So'lak bezi", 1),
                ("🏛 Tarix: Amir Temur tuzgan davlatning poytaxti qaysi shahar bo'lgan?", "Samarqand", "Buxoro", "Hirot", "Shosh", 1),
                ("⚖️ Huquq: Konstitutsiya so'zining lug'aviy ma'nosi nima?", "Tuzilish, tuzuk", "Qonunlar to'plami", "Adolat mezoni", "Davlat boshqaruvi", 1),
                ("📐 Matematika: Pi (π) sonining taqribiy qiymati nechaga teng?", "3,14", "2,71", "1,41", "3,41", 1),
                ("📚 Adabiyot: Alisher Navoiyning «Xamsa» asari nechta dostondan iborat?", "5 ta", "4 ta", "6 ta", "7 ta", 1),
                ("⚡ Fizika: Kuchning Xalqaro birliklar tizimidagi (SI) o'lchov birligi nima?", "Nyuton (N)", "Joul (J)", "Vatt (Vt)", "Paskal (Pa)", 1),
                ("🧬 Biologiya: Odamda nechta xromosoma mavjud?", "46 ta (23 juft)", "48 ta (24 juft)", "44 ta (22 juft)", "42 ta (21 juft)", 1),
                ("🏛 Tarix: Buyuk Ipak yo'li qaysi davlatdan boshlangan?", "Xitoy", "Hindiston", "Eron", "Misr", 1),
                ("⚖️ Huquq: Bola huquqlari to'g'risidagi konvensiya bo'yicha kim bola hisoblanadi?", "18 yoshga to'lmagan har qanday inson", "16 yoshgacha bo'lganlar", "14 yoshgacha bo'lganlar", "Maktab o'quvchilari", 1),
                ("📝 Ona tili: Fe'lning nechta zamon shakli bor?", "3 ta (o'tgan, hozirgi, kelasi)", "2 ta", "4 ta", "5 ta", 1)
            ]
            for _ in range(60):
                dq = generate_multi_subject_question()
                savollar.append((dq["question"], dq["opt1"], dq["opt2"], dq["opt3"], dq["opt4"], 1))

            for q in savollar:
                await db.execute("INSERT OR IGNORE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,?)", q)
            await db.commit()
            print("✅ Barcha fanlardan savollar bazaga yozildi!")


async def get_fresh_question(user_ids: list):
    new_gen_q = generate_multi_subject_question()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,1)",
            (new_gen_q["question"], new_gen_q["opt1"], new_gen_q["opt2"], new_gen_q["opt3"], new_gen_q["opt4"])
        )
        await db.commit()

        if random.random() < 0.40:
            return new_gen_q

        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" * len(user_ids))
        query = f"""
            SELECT * FROM questions 
            WHERE id NOT IN (
                SELECT question_id FROM user_seen_questions WHERE user_id IN ({placeholders})
            )
            ORDER BY RANDOM() LIMIT 1
        """
        cursor = await db.execute(query, user_ids)
        q = await cursor.fetchone()

        if not q:
            await db.execute(f"DELETE FROM user_seen_questions WHERE user_id IN ({placeholders})", user_ids)
            await db.commit()
            cursor = await db.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
            q = await cursor.fetchone()

        if q:
            for uid in user_ids:
                await db.execute(
                    "INSERT OR IGNORE INTO user_seen_questions (user_id, question_id) VALUES (?, ?)",
                    (uid, q["id"])
                )
            await db.commit()
            return dict(q)

    return new_gen_q

# --- KLAVIATURALAR VA TAYMERLAR ---
class GameCB(CallbackData, prefix="gm"):
    action: str
    val: int = 0

active_timers = {}

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="👦 Yoshlar uchun (Bepul)", callback_data=GameCB(action="youth_start").pack())
    builder.button(text="👨 Kattalar uchun (Bellashuv)", callback_data=GameCB(action="adult_menu").pack())
    builder.adjust(1)
    return builder.as_markup()

def adult_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 2 kishilik (12,000 so'm)", callback_data=GameCB(action="pay_2").pack())
    builder.button(text="👥 4 kishilik (17,000 so'm)", callback_data=GameCB(action="pay_4").pack())
    builder.button(text="🔙 Orqaga", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()

def admin_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Bitta savol qo'shish", callback_data="admin_add_one")
    builder.button(text="📥 Ko'p savol qo'shish (Ro'yxat)", callback_data="admin_add_bulk")
    builder.button(text="⚡ Avto-generatordan 50 ta qo'shish", callback_data="admin_auto_gen")
    builder.button(text="🔄 Savollar tarixini tozalash", callback_data="admin_reset_seen")
    builder.button(text="📊 Baza statistikasi", callback_data="admin_stats")
    builder.adjust(1)
    return builder.as_markup()

def get_cards():
    builder = InlineKeyboardBuilder()
    for i in range(1, 51):
        emoji = random.choice(["🎁", "🎈", "🌟", "🍎", "🚗", "🐶", "🎸", "💎", "🍕", "🏀"])
        builder.button(text=emoji, callback_data=GameCB(action="open_card", val=i).pack())
    builder.adjust(5) 
    return builder.as_markup()

# --- HANDLERLAR ---
router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, role, status) VALUES (?, 'user', 'none')", (message.from_user.id,))
        await db.commit()
        
    text = (
        f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n"
        f"🃏 Men Joker! Sizni o'z o'yinimga taklif etaman.\n"
        f"📚 Savollar: <b>Matematika, Fizika, Adabiyot, Ona tili, Biologiya, Tarix va Huquq</b> fanlaridan!\n"
        f"🎁 Bilimingiz va omadingizni sinab ko'ring!\n\n"
        f"👇 O'yin turini tanlang:"
    )
    try:
        await message.answer_photo(photo=JOKER_IMG_URL, caption=text, reply_markup=main_menu(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

# --- ADMIN PANEL HANDLERLARI (/admin) ---
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer("🛠 <b>Admin panelga xush kelibsiz!</b>\nSavollarni yangilash va boshqarish:", reply_markup=admin_menu_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_auto_gen")
async def admin_auto_gen(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    added = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for _ in range(50):
            dq = generate_multi_subject_question()
            cursor = await db.execute(
                "INSERT OR IGNORE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,1)",
                (dq["question"], dq["opt1"], dq["opt2"], dq["opt3"], dq["opt4"])
            )
            if cursor.rowcount > 0:
                added += 1
        await db.commit()
    await callback.answer(f"⚡ 7 ta fandan {added} ta yangi noyob savol bazaga qo'shildi!", show_alert=True)

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        q_count = (await (await db.execute("SELECT COUNT(*) FROM questions")).fetchone())[0]
        u_count = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        w_count = (await (await db.execute("SELECT COUNT(*) FROM queues WHERE status = 'waiting'")).fetchone())[0]
    
    text = (
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"❓ Bazadagi yig'ilgan savollar: <b>{q_count} ta</b>\n"
        f"📚 Faol fanlar: <b>Matematika, Fizika, Adabiyot, Ona tili, Biologiya, Tarix, Huquq</b>\n"
        f"👥 Foydalanuvchilar: <b>{u_count} ta</b>\n"
        f"⏳ Navbatda kutayotganlar: <b>{w_count} ta</b>"
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
    await callback.answer("✅ Barcha foydalanuvchilar uchun savollar tarixi yangilandi!", show_alert=True)

@router.callback_query(F.data == "admin_add_one")
async def admin_add_one(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(GameStates.adding_single_question)
    text = (
        "✍️ <b>Yangi savolni quyidagi formatda yuboring:</b>\n"
        "<i>(1-variantga doim TO'G'RI javobni yozing)</i>\n\n"
        "<code>Savol matni | To'g'ri javob | Xato 1 | Xato 2 | Xato 3</code>"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.message(StateFilter(GameStates.adding_single_question))
async def process_single_question(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) != 5:
        return await message.answer("❌ Format xato! <code>|</code> belgisi bilan ajratilgan 5 ta qism bo'lishi shart.", parse_mode="HTML")
    
    q_text, opt1, opt2, opt3, opt4 = parts
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?, ?, ?, ?, ?, 1)",
            (q_text, opt1, opt2, opt3, opt4)
        )
        await db.commit()
    await state.clear()
    await message.answer(f"✅ <b>Savol bazaga qo'shildi!</b>\n❓ {q_text}", reply_markup=admin_menu_kb(), parse_mode="HTML")

@router.callback_query(F.data == "admin_add_bulk")
async def admin_add_bulk(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(GameStates.adding_bulk_questions)
    text = (
        "📥 <b>Bir nechta savolni har bir qatorda bittadan qilib yuboring:</b>\n\n"
        "<code>Savol | To'g'ri javob | Xato 1 | Xato 2 | Xato 3</code>"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.message(StateFilter(GameStates.adding_bulk_questions))
async def process_bulk_questions(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    lines = message.text.strip().split("\n")
    added = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 5:
                await db.execute(
                    "INSERT OR REPLACE INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?, ?, ?, ?, ?, 1)",
                    (parts[0], parts[1], parts[2], parts[3], parts[4])
                )
                added += 1
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Jami <b>{added} ta</b> yangi savol muvaffaqiyatli qo'shildi!", reply_markup=admin_menu_kb(), parse_mode="HTML")

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Asosiy menyu:", reply_markup=main_menu())
    await callback.answer()

# --- YOSHLAR O'YINI ---
@router.callback_query(GameCB.filter(F.action == "youth_start"))
async def youth_start(callback: CallbackQuery):
    await callback.message.answer("🎯 <b>Kartani tanlang!</b>", reply_markup=get_cards(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(GameCB.filter(F.action == "open_card"))
async def open_card(callback: CallbackQuery, callback_data: GameCB):
    await callback.answer()
    user_id = callback.from_user.id
    
    q = await get_fresh_question([user_id])

    options = [q['opt1'], q['opt2'], q['opt3'], q['opt4']]
    random.shuffle(options)
    correct_text = q[f"opt{q['correct_opt']}"]
    
    builder = InlineKeyboardBuilder()
    for opt in options:
        is_correct = 1 if opt == correct_text else 0
        builder.button(text=opt, callback_data=GameCB(action="youth_answer", val=is_correct).pack())
    builder.adjust(2)
    
    text = f"❓ <b>SAVOL:</b>\n{q['question']}\n\n⏳ Javob berish uchun 15 soniya vaqt:"
    msg = await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    
    if user_id in active_timers:
        active_timers[user_id].cancel()
    active_timers[user_id] = asyncio.create_task(youth_timeout(msg, user_id))

async def youth_timeout(message: Message, user_id: int):
    try:
        await asyncio.sleep(15.0)
        await message.edit_text(
            "⏳ <b>Vaqt tugadi!</b>\n\n🎰 Senga Jokerning xabari bor, o'qib ko'r:\n<i>\"Bu qovoqni ishlat bolakay!\"</i> 🎃",
            reply_markup=main_menu(), parse_mode="HTML"
        )
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

    is_correct = (callback_data.val == 1)
    if is_correct:
        text = (
            "🎉 <b>TABRIKLAYMIZ, SIZ YUTDINGIZ!</b> 🎉\n\n"
            "🎁 Yutug'ingiz: <b>15% CHEGIRMA</b>\n\n"
            "📍 Urgut tumanidagi 3-umumta'lim maktabi ro'parasidagi <b>Super Mini Market</b>dan xarid qiling.\n\n"
            "📸 Chegirmadan foydalanish uchun <b>skrinshot</b> oling!"
        )
        await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
    else:
        await callback.message.edit_text(
            "❌ <b>Xato javob!</b>\n\n🎰 Senga Jokerning xabari bor, o'qib ko'r:\n<i>\"Bu qovoqni ishlat bolakay!\"</i> 🎃",
            reply_markup=main_menu(), parse_mode="HTML"
        )
    await callback.answer()

# --- KATTALAR BELLASHUVI ---
@router.callback_query(GameCB.filter(F.action == "adult_menu"))
async def adult_menu_handler(callback: CallbackQuery):
    await callback.message.answer("👨 <b>Kattalar uchun bellashuv turini tanlang:</b>", reply_markup=adult_menu(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(GameCB.filter(F.action.in_({"pay_2", "pay_4"})))
async def adult_pay(callback: CallbackQuery, callback_data: GameCB, state: FSMContext):
    mode = callback_data.action 
    amount = "12,000" if mode == "pay_2" else "17,000"
    await state.update_data(mode=mode)
    text = (
        f"💳 <b>To'lov ({amount} so'm)</b>\n\n"
        f"To'lovni kartaga o'tkazing:\n<code>{KARTA_RAQAMI}</code>\n<b>{KARTA_EGASI}</b>\n\n"
        f"📸 Chek skrinshotini shu yerga yuboring."
    )
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(GameStates.waiting_for_receipt)
    await callback.answer()

@router.message(F.photo, StateFilter(GameStates.waiting_for_receipt))
async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
    try:
        user_id = message.from_user.id
        data = await state.get_data()
        mode = data.get("mode", "pay_2")
        amount = "12,000" if mode == "pay_2" else "17,000"
        await state.clear()
        
        admin_text = (
            f"🧾 <b>Yangi chek!</b>\n"
            f"👤 {message.from_user.full_name}\n"
            f"🆔 <code>{user_id}</code>\n"
            f"💰 {amount} so'm\n"
            f"🎮 {'2 kishilik' if mode == 'pay_2' else '4 kishilik'}\n\n"
            f"Tasdiqlaysizmi?"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Tasdiqlash", callback_data=f"approve:{mode}:{user_id}")
        builder.button(text="❌ Rad etish", callback_data=f"reject:{user_id}")
        
        await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await message.answer("⏳ Chek adminga yuborildi. Tasdiqlanishini kuting...")
    except Exception as e:
        print(f"Rasm yuborishda xato: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

# UNIVERSAL TASDIQLASH HANDLERI (Eski '_' va yangi ':' formatlarini ham xatosiz o'qiydi)
@router.callback_query(F.data.startswith("approve"))
async def approve_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Siz admin emassiz!", show_alert=True)
    
    data_str = callback.data
    try:
        if ":" in data_str:
            # Yangi format: approve:pay_2:12345678
            _, mode, user_id_str = data_str.split(":")
            user_id = int(user_id_str)
        else:
            # Eski format: approve_pay_2_12345678
            # rsplit('_', 1) eng oxirgi '_' belgisidan bo'ladi va ID ni aniq ajratib oladi
            prefix_and_mode, user_id_str = data_str.rsplit("_", 1)
            mode = prefix_and_mode.replace("approve_", "")
            user_id = int(user_id_str)
    except Exception as e:
        print(f"Approve parse error: {e} | data: {data_str}")
        return await callback.answer(f"Xato ma'lumot: {data_str}", show_alert=True)

    await callback.answer("✅ To'lov tasdiqlandi!")
    
    # Xabardagi tugmalarni olib tashlab, TASDIQLANDI deb yozib qo'yamiz
    try:
        old_caption = callback.message.caption or "🧾 Chek"
        await callback.message.edit_caption(caption=old_caption + "\n\n✅ <b>TASDIQLANDI</b>", parse_mode="HTML", reply_markup=None)
    except Exception as e:
        print(f"Caption edit error: {e}")

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Agar eski bazada duel_id ustuni yo'q bo'lsa ham xato bermasligi uchun tekshiramiz
            try:
                await db.execute("ALTER TABLE queues ADD COLUMN duel_id INTEGER DEFAULT 0")
            except Exception:
                pass
            await db.execute("INSERT OR REPLACE INTO queues (user_id, mode, status, duel_id) VALUES (?, ?, 'waiting', 0)", (user_id, mode))
            await db.commit()
            cursor = await db.execute("SELECT user_id FROM queues WHERE mode = ? AND status = 'waiting' LIMIT 4", (mode,))
            waiting_users = [row[0] for row in await cursor.fetchall()]

        required_count = 2 if mode == "pay_2" else 4
        
        if len(waiting_users) < required_count:
            try: 
                await bot.send_message(user_id, f"✅ To'lov tasdiqlandi! Navbatga qo'shildingiz ({len(waiting_users)}/{required_count}). Raqiblaringizni kuting...")
            except Exception:
                pass
        else:
            players = waiting_users[:required_count]
            duel_id = random.randint(1000, 9999)
            async with aiosqlite.connect(DB_PATH) as db:
                for p in players:
                    await db.execute("UPDATE queues SET status = 'playing', duel_id = ? WHERE user_id = ?", (duel_id, p))
                await db.commit()
                
            prize = 18000 if mode == "pay_2" else 25500 
            
            for p in players:
                try:
                    await bot.send_message(p, "⚔️ Barcha yig'ildi! O'yin boshlanmoqda...")
                except Exception:
                    pass
                    
            await start_duel(bot, players, "2 kishilik" if mode == "pay_2" else "4 kishilik", prize, duel_id)
    except Exception as e:
        print(f"Database/Duel error in approve: {e}")
        await bot.send_message(ADMIN_ID, f"⚠️ Bazada xatolik yuz berdi: {e}")

# UNIVERSAL RAD ETISH HANDLERI (Eski '_' va yangi ':' formatlari uchun)
@router.callback_query(F.data.startswith("reject"))
async def reject_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Siz admin emassiz!", show_alert=True)
    
    data_str = callback.data
    try:
        if ":" in data_str:
            rejected_user_id = int(data_str.split(":")[1])
        else:
            rejected_user_id = int(data_str.rsplit("_", 1)[1])
    except Exception as e:
        return await callback.answer(f"Xato: {e}", show_alert=True)
    
    await callback.answer("❌ Rad etildi!")
    try:
        old_caption = callback.message.caption or "🧾 Chek"
        await callback.message.edit_caption(caption=old_caption + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML", reply_markup=None)
    except Exception:
        pass
    
    try:
        await bot.send_message(
            rejected_user_id,
            "❌ <b>Afsuski, chekingiz rad etildi.</b>\n\nIltimos, to'lovni qaytadan amalga oshirib, chekni botga qayta yuboring.",
            parse_mode="HTML"
        )
    except Exception:
        pass

async def start_duel(bot: Bot, players: list, duel_type: str, prize: int, duel_id: int):
    q = await get_fresh_question(players)

    options = [q['opt1'], q['opt2'], q['opt3'], q['opt4']]
    random.shuffle(options)
    correct_text = q[f"opt{q['correct_opt']}"]
    
    builder = InlineKeyboardBuilder()
    for opt in options:
        is_correct = "1" if opt == correct_text else "0"
        builder.button(text=opt, callback_data=GameCB(action="duel_answer", val=int(f"{duel_id}{is_correct}")).pack())
    builder.adjust(2)
    
    text = f"⚔️ <b>BELLASHUV BOSHLANDI!</b> ⚔️\n({duel_type})\n\nKim birinchi to'g'ri topsa, <b>{prize:,} so'm</b> yutadi!\n\n❓ <b>SAVOL:</b>\n{q['question']}"
    
    for player in players:
        try:
            await bot.send_message(player, text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass

@router.callback_query(GameCB.filter(F.action == "duel_answer"))
async def duel_answer(callback: CallbackQuery, callback_data: GameCB, bot: Bot, state: FSMContext):
    ans_data = str(callback_data.val)
    duel_id = int(ans_data[:-1])
    is_correct = ans_data[-1] == "1"
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT mode FROM queues WHERE user_id = ? AND status = 'playing' AND duel_id = ?", (user_id, duel_id))
        row = await cursor.fetchone()
        
    if not row:
        await callback.answer("⚠️ Bu bellashuv allaqachon yakunlangan yoki siz o'yindan chiqqansiz!", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    mode = row[0]
    prize = 18000 if mode == "pay_2" else 25500
    await callback.answer()
    
    aqlli_gap = (
        "🚨🚨🚨 <b>DIQQAT!</b> 🚨🚨🚨\n\n"
        "💥💥💥 <b>S  E  N</b> 💥💥💥\n"
        "🔥🔥🔥 <b>A  X  M  O  Q  S  A  N !</b> 🔥🔥🔥\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "❌ <b>YUTQAZDINGIZ!</b> ❌\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Raqibingiz sizdan ancha tezroq va aqlliroq bo'lib chiqdi.\n"
        "Miyangizni ishlatib ko'ring! 🧠🤡"
    )

    if is_correct:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id FROM queues WHERE duel_id = ? AND status = 'playing'", (duel_id,))
            all_players = [r[0] for r in await cursor.fetchall()]
            await db.execute("DELETE FROM queues WHERE duel_id = ?", (duel_id,))
            await db.commit()
        
        await state.update_data(prize=prize)
        await state.set_state(GameStates.waiting_for_card)
        
        try:
            await callback.message.edit_text(
                f"🎉 <b>TABRIKLAYMIZ, SIZ YUTDINGIZ!</b> 🎉\n\n"
                f"Siz <b>{prize:,} so'mni</b> qo'lga kiritdingiz!\n\n"
                f"💳 Admin pul o'tkazishi uchun <b>karta raqamingiz va ism-sharifingizni</b> yozib yuboring:",
                parse_mode="HTML"
            )
            await bot.send_message(
                ADMIN_ID,
                f"⚔️ <b>Bellashuv yakunlandi!</b>\n"
                f"🏆 G'olib: {callback.from_user.full_name} (ID: <code>{user_id}</code>)\n"
                f"💰 Yutuq: {prize:,} so'm\n\n"
                f"⏳ G'olib karta raqamini yuborishi kutilmoqda...",
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        for p in all_players:
            if p != user_id:
                try:
                    await bot.send_message(p, aqlli_gap, reply_markup=main_menu(), parse_mode="HTML")
                except Exception:
                    pass
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM queues WHERE user_id = ? AND duel_id = ?", (user_id, duel_id))
            await db.commit()
            
        try:
            await callback.message.edit_text(aqlli_gap, reply_markup=main_menu(), parse_mode="HTML")
        except Exception:
            pass

@router.message(StateFilter(GameStates.waiting_for_card))
async def receive_winner_card(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    prize = data.get("prize", 18000)
    await state.clear()
    
    await bot.send_message(
        ADMIN_ID,
        f"💳 <b>G'olib karta ma'lumotlarini yubordi!</b>\n\n"
        f"👤 Ism: {message.from_user.full_name}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"💰 To'lanadigan yutuq: <b>{prize:,} so'm</b>\n"
        f"📝 Karta ma'lumoti: <code>{message.text}</code>",
        parse_mode="HTML"
    )
    await message.answer(
        "✅ Karta raqamingiz adminga yuborildi! Tez orada yutuq tashlab beriladi.",
        reply_markup=main_menu()
    )

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
    print("🤖 Tizim ishga tushdi. To'lov tasdiqlash tizimi va 7 ta fan generatori faol!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
