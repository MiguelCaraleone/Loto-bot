import asyncio
import logging
import aiosqlite
import random
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

# --- SOZLAMALAR ---
TOKEN = "9237388648:AAHNnfVKjUc5wWH3-UnKodCPJ31UMbI092M" 
ADMIN_ID = 1302845749
DB_PATH = "loto_game.db"
KARTA_RAQAMI = "9860 3501 4780 2176"
KARTA_EGASI = "Mamatkulov Izzatillo"

# --- BAZA VA SAVOLLAR ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS questions 
            (id INTEGER PRIMARY KEY, question TEXT, opt1 TEXT, opt2 TEXT, opt3 TEXT, opt4 TEXT, correct_opt INTEGER)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS users 
            (user_id INTEGER PRIMARY KEY, role TEXT, status TEXT)""")
        await db.commit()

        cursor = await db.execute("SELECT COUNT(*) FROM questions")
        count = (await cursor.fetchone())[0]

        if count < 100:
            savollar = [
                # 1-10
                ("O'zbekistonning eng uzun daryosi qaysi?", "Sirdaryo", "Amudaryo", "Zarafshon", "Qashqadaryo", 2),
                ("Eng katta sayyora qaysi?", "Yupiter", "Saturn", "Neptun", "Yer", 1),
                ("O'zbekiston bayrog'ida nechta yulduz bor?", "12", "11", "10", "9", 1),
                ("Inson tanasidagi eng katta organ qaysi?", "Teri", "Jigar", "O'pka", "Yurak", 1),
                ("Qaysi metall suvda cho'kadi?", "Temir", "Yog'och", "Plastik", "Muz", 1),
                ("Dunyodagi eng baland tog' qaysi?", "Everest", "Elbrus", "Kilimanjaro", "Montblan", 1),
                ("1 yilda nechta hafta bor?", "52", "48", "50", "54", 1),
                ("Qonning rangi qanday rangda bo'ladi?", "Qizil", "Ko'k", "Yashil", "Sariq", 1),
                ("Eng kichik qit'a qaysi?", "Avstraliya", "Yevropa", "Antarktida", "Janubiy Amerika", 1),
                ("Qaysi hayvon sut emizuvchi?", "Kit", "Akula", "Krokodil", "Toshbaqa", 1),
                # 11-20
                ("Kompyuterning miyasi nima deyiladi?", "Protsessor", "Monitor", "Klaviatura", "Sichqoncha", 1),
                ("O'zbekiston poytaxti qaysi shahar?", "Toshkent", "Samarqand", "Buxoro", "Andijon", 1),
                ("Quyosh sistemamizdagi eng issiq sayyora qaysi?", "Venera", "Mars", "Merkuriy", "Yupiter", 1),
                ("Inson umurtqa pog'onasi nechta umurtqadan iborat?", "33", "30", "28", "35", 1),
                ("Telegram kim tomonidan yaratilgan?", "Pavel Durov", "Mark Zuckerberg", "Bill Gates", "Steve Jobs", 1),
                ("Eng katta okean qaysi?", "Tinch okeani", "Atlantika", "Hind okeani", "Shimoliy Muz", 1),
                ("O'zbekiston qachon mustaqil bo'lgan?", "1991", "1989", "1992", "1990", 1),
                ("Eng qattiq tabiiy modda qaysi?", "Olmos", "Temir", "Granit", "Oltin", 1),
                ("Qaysi gaz o'simliklar uchun zarur?", "Karbonat angidrid", "Kislorod", "Azot", "Vodorod", 1),
                ("Dunyo bo'yicha eng ko'p so'zlashadigan til qaysi?", "Xitoy tili", "Ingliz tili", "Ispan tili", "Hind tili", 1),
                # 21-30
                ("O'zbekistonda nechta viloyat bor?", "12", "13", "11", "14", 1),
                ("Bir litr suvning og'irligi qancha?", "1 kg", "500 g", "2 kg", "1.5 kg", 1),
                ("Yorug'lik tezligi qancha?", "300 000 km/s", "150 000 km/s", "400 000 km/s", "200 000 km/s", 1),
                ("Eng ko'p aholisi bo'lgan davlat qaysi?", "Hindiston", "Xitoy", "AQSH", "Indoneziya", 1),
                ("Inson yuragi nechta kamera (bo'lmacha)dan iborat?", "4", "2", "3", "5", 1),
                ("Muzning kimyoviy formulasi qanday?", "H2O", "CO2", "O2", "H2O2", 1),
                ("Qaysi hayvon eng uzoq umr ko'radi?", "Toshbaqa", "Fil", "Kit", "Akula", 1),
                ("Eng katta cho'l qaysi?", "Sahroi Kabir", "Gobi", "Karakum", "Atakama", 1),
                ("Qadimgi Misrda qanday yozuv ishlatilgan?", "Iyeroglif", "Lotin", "Kirill", "Arab", 1),
                ("Birinchi jahon urushi qachon boshlangan?", "1914", "1918", "1939", "1945", 1),
                # 31-40
                ("O'zbek tili qaysi til oilasiga kiradi?", "Turkiy tillar", "Hind-yevropa", "Semit", "Ural", 1),
                ("Eng qimmatbaho metall qaysi?", "Ruteniy", "Oltin", "Platina", "Kumush", 1),
                ("Inson tanasida nechta suyak bor (kattalarda)?", "206", "200", "210", "220", 1),
                ("Quyoshdan Yergacha masofa qancha?", "150 mln km", "100 mln km", "200 mln km", "50 mln km", 1),
                ("Eng katta hayvon qaysi?", "Ko'k kit", "Fil", "Jirafa", "Karkidon", 1),
                ("Qaysi davlatda eng ko'p vaqt zonalari bor?", "Fransiya", "Rossiya", "Xitoy", "AQSH", 1),
                ("Suv necha darajada muzlaydi?", "0°C", "-10°C", "10°C", "-5°C", 1),
                ("Qaysi vitamin quyosh nuridan olinadi?", "D vitamini", "C vitamini", "A vitamini", "B vitamini", 1),
                ("Eng tez uchuvchi qush qaysi?", "Sapsan", "Burgut", "Kabutar", "Lochin", 1),
                ("O'zbekistonning eng katta shahri qaysi?", "Toshkent", "Samarqand", "Namangan", "Farg'ona", 1),
                # 41-50
                ("Fotosintez qayerda sodir bo'ladi?", "Xloroplast", "Mitoxondriya", "Yadro", "Sitoplazma", 1),
                ("Eng katta o'rmon qayerda?", "Amazonka", "Sibir", "Afrika", "Kanada", 1),
                ("Qaysi hayvon eng zaharli?", "Kubomeduza", "Ilon", "Chayon", "O'rgimchak", 1),
                ("Dunyodagi eng chuqur joy qaysi?", "Mariana cho'kmasi", "Temza", "Hind okeani", "Atlantika", 1),
                ("Eng ko'p ishlatiladigan dasturlash tili (2023)?", "Python", "Java", "C++", "JavaScript", 1),
                ("O'zbekistonning eng baland nuqtasi?", "Hazrat Sulton", "Beshtor", "Chimyon", "Tyan-Shan", 1),
                ("Qaysi yilda internet ixtiro qilindi?", "1969", "1980", "1995", "2000", 1),
                ("Dunyoda eng ko'p sotilgan kitob qaysi?", "Bibliya", "Qur'on", "Ginnes", "Don Kixot", 1),
                ("Qaysi sayyora Quyoshga eng yaqin?", "Merkuriy", "Venera", "Yer", "Mars", 1),
                ("Inson qon guruhi nechta asosiy turga bo'linadi?", "4", "3", "5", "6", 1),
                # 51-60
                ("Eng qadimgi tsivilizatsiya qaysi?", "Misr", "Rim", "Yunon", "Xitoy", 1),
                ("Eng katta qit'a qaysi?", "Osiyo", "Afrika", "Yevropa", "Shimoliy Amerika", 1),
                ("Yozda vaqt qanday o'zgaradi?", "Bir soat oldinga", "Bir soat orqaga", "O'zgarmaydi", "Ikki soat", 1),
                ("Qaysi hayvon eng baland sakraydi?", "Kenguru", "Sher", "Yo'lbars", "Gepard", 1),
                ("Eng ko'p aholisi bo'lgan shahar qaysi?", "Tokio", "Pekin", "Dehli", "Nyu-York", 1),
                ("Suvning qaynash harorati qancha?", "100°C", "90°C", "110°C", "80°C", 1),
                ("Eng katta ko'l qaysi?", "Kaspiy", "Baykal", "Viktoriya", "Orol", 1),
                ("Qaysi yilda Telegram ishga tushdi?", "2013", "2010", "2015", "2018", 1),
                ("Eng ko'p o'ynaladigan sport o'yini qaysi?", "Futbol", "Kriket", "Basketbol", "Tennis", 1),
                ("Qaysi hayvon eng katta tuxum qo'yadi?", "Tuyaqush", "Krokodil", "Akula", "Ilon", 1),
                # 61-70
                ("Eng ko'p gapiriladigan til (ona tili)?", "Xitoy", "Ingliz", "Ispan", "Hind", 1),
                ("Qaysi qit'ada eng ko'p davlat bor?", "Afrika", "Osiyo", "Yevropa", "Amerika", 1),
                ("Odam tanasidagi eng kichik suyak qaysi?", "Uzengi", "Burun", "Barmoq", "Quloq", 1),
                ("Eng katta sut emizuvchi qaysi?", "Ko'k kit", "Fil", "Jirafa", "Karkidon", 1),
                ("Eng qadimgi poytaxt qaysi?", "Damashq", "Rim", "Afina", "Qohira", 1),
                ("Yer necha kunda Quyosh atrofida aylanadi?", "365", "360", "370", "380", 1),
                ("Qaysi element eng yengil?", "Vodorod", "Geliy", "Kislorod", "Azot", 1),
                ("Eng ko'p ishlatiladigan ijtimoiy tarmoq?", "Facebook", "Instagram", "TikTok", "Twitter", 1),
                ("Eng katta orol qaysi?", "Grenlandiya", "Madagaskar", "Borneo", "Yangi Gvineya", 1),
                ("Qaysi oy eng qisqa?", "Fevral", "Yanvar", "Mart", "Aprel", 1),
                # 71-80
                ("Eng uzun daryo qaysi?", "Nil", "Amazonka", "Yanszi", "Missisipi", 1),
                ("Inson tanasidagi eng qattiq qism?", "Tish emali", "Suyak", "Tirnoq", "Teri", 1),
                ("Eng ko'p tilli davlat qaysi?", "Papua-Yangi Gvineya", "Hindiston", "Xitoy", "Rossiya", 1),
                ("Eng katta havo kemasi qaysi?", "An-225", "Boeing 747", "Airbus A380", "C-5 Galaxy", 1),
                ("Birinchi sun'iy yo'ldosh qaysi?", "Sputnik-1", "Apollo", "Vostok", "Gemini", 1),
                ("Eng ko'p aholisi bo'lgan qit'a qaysi?", "Osiyo", "Afrika", "Yevropa", "Amerika", 1),
                ("Eng chuqur ko'l qaysi?", "Baykal", "Kaspiy", "Viktoriya", "Orol", 1),
                ("O'zbekistonning eng qadimgi shahri?", "Samarqand", "Buxoro", "Toshkent", "Xiva", 1),
                ("Eng kichik davlat qaysi?", "Vatikan", "Monako", "San-Marino", "Malta", 1),
                ("Eng ko'p eksport qilinadigan oziq-ovqat?", "Bug'doy", "Guruch", "Makkajo'xori", "Kartoshka", 1),
                # 81-90
                ("Eng qadimgi til qaysi?", "Sanskrit", "Lotin", "Yunon", "Xitoy", 1),
                ("Yer yuzida nechta okean bor?", "5", "4", "3", "6", 1),
                ("Eng katta hayvonlar qayerda yashaydi?", "Okeanda", "O'rmonda", "Cho'lda", "Tog'da", 1),
                ("Eng ko'p sotiladigan meva qaysi?", "Banan", "Olma", "Apelsin", "Uzum", 1),
                ("Inson miyasi qancha vatt quvvat ishlatadi?", "20", "10", "50", "100", 1),
                ("Eng katta qush qaysi?", "Tuyaqush", "Burgut", "Kondor", "To'ti", 1),
                ("Eng qadimgi piramida qaysi davlatda?", "Misr", "Meksika", "Peru", "Sudan", 1),
                ("Eng ko'p o'qiladigan gazeta qaysi?", "Yomiuri Shimbun", "The Times", "New York Times", "The Guardian", 1),
                ("Qaysi sport turi eng qadimiy?", "Yugurish", "Kurash", "Suzish", "Ot sporti", 1),
                ("Eng ko'p ishlatiladigan transport vositasi?", "Velosiped", "Mashina", "Poyezd", "Samolyot", 1),
                # 91-100
                ("Eng katta elektr stansiyasi qaysi?", "Uch qaraqchi", "Chernobil", "Fukusima", "Grand-Kuli", 1),
                ("Qaysi yilda O'zbekiston BMTga a'zo bo'ldi?", "1992", "1991", "1993", "1990", 1),
                ("Eng qimmatbaho tosh qaysi?", "Olmos", "Yoqut", "Zumrad", "Sapfir", 1),
                ("Eng ko'p o'ynaladigan o'yin (video)?", "Minecraft", "Fortnite", "GTA V", "PUBG", 1),
                ("Qaysi hayvon eng aqlli?", "Delfin", "It", "Maymun", "Fil", 1),
                ("Eng tez avtomobil qaysi?", "Bugatti", "Ferrari", "Lamborghini", "Porsche", 1),
                ("Dunyodagi eng baland bino qaysi?", "Burj Khalifa", "Shanghai Tower", "Abraj Al Bait", "Ping An", 1),
                ("Eng ko'p daromadli kompaniya qaysi?", "Apple", "Microsoft", "Amazon", "Google", 1),
                ("Eng ko'p foydalanuvchisi bo'lgan ilova?", "YouTube", "Facebook", "WhatsApp", "Instagram", 1),
                ("Eng qadimgi universitet qayerda?", "Bolonya", "Oksford", "Kembrij", "Sorbonna", 1)
            ]
            for q in savollar:
                await db.execute("INSERT INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,?)", q)
            await db.commit()
            print(f"✅ {len(savollar)} ta savol bazaga muvaffaqiyatli qo'shildi!")

# --- KLAVIATURALAR ---
class GameCB(CallbackData, prefix="gm"):
    action: str
    val: int = 0

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="👦 Yoshlar uchun (Bepul)", callback_data=GameCB(action="youth_start").pack())
    builder.button(text="👨 Kattalar uchun (10,000 so'm)", callback_data=GameCB(action="adult_pay").pack())
    builder.adjust(1)
    return builder.as_markup()

def get_cards():
    builder = InlineKeyboardBuilder()
    for i in range(1, 51):
        emoji = random.choice(["🎁", "🎈", "🌟", "🍎", "🚗", "🐶", "🎸", "💎", "🍕", "🏀", "🍇", "🚀", "⚽", "🎲", "🔔"])
        builder.button(text=emoji, callback_data=GameCB(action="open_card", val=i).pack())
    builder.adjust(10)
    return builder.as_markup()

# --- HANDLERLAR ---
router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, role, status) VALUES (?, 'user', 'none')", (message.from_user.id,))
        await db.commit()
        
    text = (
        f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n"
        f"🎰 <b>Super Mini Market Loto</b> botiga xush kelibsiz!\n\n"
        f"👇 O'yin turini tanlang:"
    )
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

# --- YOSHLAR O'YINI ---
@router.callback_query(GameCB.filter(F.action == "youth_start"))
async def youth_start(callback: CallbackQuery):
    await callback.message.edit_text("🎯 <b>Kartani tanlang!</b>\n\n50 ta kartadan bittasini tanlang.", reply_markup=get_cards(), parse_mode="HTML")
    await callback.answer()

# --- KATTALAR TO'LOVI ---
@router.callback_query(GameCB.filter(F.action == "adult_pay"))
async def adult_pay(callback: CallbackQuery, state: FSMContext):
    text = (
        f"💳 <b>Kattalar uchun qatnashish (Pullik)</b>\n\n"
        f"Qatnashish narxi: <b>10 000 so'm</b>\n\n"
        f"To'lovni quyidagi kartaga o'tkazing:\n"
        f"<code>{KARTA_RAQAMI}</code>\n"
        f"<b>{KARTA_EGASI}</b>\n\n"
        f"📸 To'lovni amalga oshirgach, <b>chekning skrinshotini (rasmini)</b> shu yerga yuboring."
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await state.set_state("waiting_for_receipt")
    await callback.answer()

@router.message(F.photo, StateFilter("waiting_for_receipt"))
async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    await state.clear()
    
    admin_text = (
        f"🧾 <b>Yangi to'lov cheki!</b>\n\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"To'lovni tasdiqlaysizmi?"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=GameCB(action="approve_pay", val=user_id).pack())
    builder.button(text="❌ Rad etish", callback_data="reject")
    
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await message.answer("⏳ Chek adminga yuborildi. Tasdiqlanishini kuting...")

@router.callback_query(GameCB.filter(F.action == "approve_pay"))
async def approve_payment(callback: CallbackQuery, callback_data: GameCB, bot: Bot):
    if callback.from_user.id != ADMIN_ID: return
    
    user_id = callback_data.val
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET role = 'adult', status = 'active' WHERE user_id = ?", (user_id,))
        await db.commit()
        
    await callback.message.edit_caption(caption="✅ To'lov tasdiqlandi! O'yin boshlandi.")
    await bot.send_message(user_id, "✅ To'lov tasdiqlandi! Omad tilaymiz.\n\n🎯 Kartani tanlang:", reply_markup=get_cards())
    await callback.answer("Tasdiqlandi!")

@router.callback_query(F.data == "reject")
async def reject_payment(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_caption(caption="❌ To'lov rad etildi.")
    await callback.answer("Rad etildi!")

# --- SAVOL VA JAVOB JARAYONI ---
@router.callback_query(GameCB.filter(F.action == "open_card"))
async def open_card(callback: CallbackQuery, callback_data: GameCB, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
        q = await cursor.fetchone()
        
        if not q:
            return await callback.answer("Hozircha savollar yo'q.", show_alert=True)

    options = [q['opt1'], q['opt2'], q['opt3'], q['opt4']]
    random.shuffle(options)
    correct_text = q[f"opt{q['correct_opt']}"]
    
    builder = InlineKeyboardBuilder()
    for opt in options:
        is_correct = "1" if opt == correct_text else "0"
        builder.button(text=opt, callback_data=GameCB(action="answer", val=int(f"{is_correct}")).pack())
    builder.adjust(2)
    
    await state.update_data(q_correct=correct_text, start_time=asyncio.get_event_loop().time(), user_id=callback.from_user.id, msg_id=callback.message.message_id)
    
    text = f"❓ <b>SAVOL:</b> {q['question']}\n\n⏳ Javob berish uchun 15 soniya vaqt:"
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    
    asyncio.create_task(timeout_check(callback.message, state, callback.from_user.id))

async def timeout_check(message: Message, state: FSMContext, user_id: int):
    await asyncio.sleep(15.0)
    data = await state.get_data()
    if data.get("start_time"):
        await state.clear()
        try:
            await message.edit_text(
                f"⏳ <b>Vaqt tugadi!</b>\n\n"
                f"🎰 Senga Jokerning xabari bor, o'qib ko'r:\n"
                f"<i>\"Bu qovoqni ishlat bolakay!\"</i> 🎃",
                reply_markup=main_menu(), parse_mode="HTML"
            )
        except:
            pass

@router.callback_query(GameCB.filter(F.action == "answer"))
async def check_answer(callback: CallbackQuery, callback_data: GameCB, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if not data.get("start_time") or data.get("user_id") != callback.from_user.id:
        return await callback.answer("Bu savol eskirgan yoki sizga tegishli emas!", show_alert=True)
    
    elapsed = asyncio.get_event_loop().time() - data['start_time']
    if elapsed > 15.5:
        await state.clear()
        return await callback.answer("Vaqt tugadi!", show_alert=True)
        
    await state.clear()
    is_correct = str(callback_data.val)[-1] == "1"
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
        role_data = await cursor.fetchone()
        role = role_data[0] if role_data else 'user'

    if is_correct:
        if role == 'adult':
            await bot.send_message(ADMIN_ID, f"💰 <b>Kattalar o'yinida yutuq!</b>\n\n👤 Foydalanuvchi: {callback.from_user.full_name} (@{callback.from_user.username})\n💵 Yutuq: 15,000 so'm\n\nKarta raqamini so'rang!")
            await callback.message.edit_text("🎉 <b>To'g'ri javob!</b>\n\nSiz 15,000 so'm yutdingiz! Pul o'tkazish uchun karta raqamingizni yuboring:", reply_markup=main_menu())
            await state.set_state("waiting_for_card")
        else:
            text = (
                f"🎉 <b>TABRIKLAYMIZ, SIZ YUTDINGIZ!</b> 🎉\n\n"
                f"🎁 Yutug'ingiz: <b>15% CHEGIRMA</b>\n\n"
                f"📍 Urgut tumanidagi 3-umumta'lim maktabi ro'parasidagi <b>Super Mini Market</b>dan xarid qiling.\n\n"
                f"📸 Chegirmadan foydalanish uchun <b>skrinshot</b> oling!"
            )
            await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
    else:
        await callback.message.edit_text(
            f"❌ <b>Xato javob!</b>\n\n"
            f"🎰 Senga Jokerning xabari bor, o'qib ko'r:\n"
            f"<i>\"Bu qovoqni ishlat bolakay!\"</i> 🎃",
            reply_markup=main_menu(), parse_mode="HTML"
        )
    await callback.answer()

@router.message(StateFilter("waiting_for_card"))
async def get_card_number(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    card_num = message.text
    await bot.send_message(ADMIN_ID, f"💳 <b>Karta raqami keldi!</b>\n\n👤 Foydalanuvchi: {message.from_user.full_name}\n💳 Karta: <code>{card_num}</code>")
    await message.answer("✅ Karta raqamingiz adminga yuborildi. Pul tez orada o'tkaziladi!", reply_markup=main_menu())

# --- ADMIN: YANGI SAVOL QO'SHISH ---
class AddQuestion(StatesGroup):
    q = State(); o1 = State(); o2 = State(); o3 = State(); o4 = State(); c = State()

@router.message(Command("add"))
async def admin_add(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("1️⃣ Savolni kiriting:")
    await state.set_state(AddQuestion.q)

@router.message(AddQuestion.q)
async def a1(message: Message, state: FSMContext):
    await state.update_data(q=message.text)
    await message.answer("2️⃣ 1-variantni kiriting:")
    await state.set_state(AddQuestion.o1)
    
@router.message(AddQuestion.o1)
async def a2(message: Message, state: FSMContext):
    await state.update_data(o1=message.text)
    await message.answer("3️⃣ 2-variantni kiriting:")
    await state.set_state(AddQuestion.o2)

@router.message(AddQuestion.o2)
async def a3(message: Message, state: FSMContext):
    await state.update_data(o2=message.text)
    await message.answer("4️⃣ 3-variantni kiriting:")
    await state.set_state(AddQuestion.o3)

@router.message(AddQuestion.o3)
async def a4(message: Message, state: FSMContext):
    await state.update_data(o3=message.text)
    await message.answer("5️⃣ 4-variantni kiriting:")
    await state.set_state(AddQuestion.o4)

@router.message(AddQuestion.o4)
async def a5(message: Message, state: FSMContext):
    await state.update_data(o4=message.text)
    await message.answer("6️⃣ To'g'ri javob raqamini kiriting (1, 2, 3, yoki 4):")
    await state.set_state(AddQuestion.c)

@router.message(AddQuestion.c)
async def a6(message: Message, state: FSMContext):
    if message.text not in ["1", "2", "3", "4"]:
        return await message.answer("Faqat 1, 2, 3 yoki 4 raqamini kiriting:")
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,?)", 
                         (data['q'], data['o1'], data['o2'], data['o3'], data['o4'], int(message.text)))
        await db.commit()
    await state.clear()
    await message.answer("✅ Savol bazaga qo'shildi!")

# --- ISHGA TUSHIRISH ---
async def main():
    # Eski bazani tozalash (agar xohlasangiz, bu qatorni o'chirib qo'ying)
    import os
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    await init_db() 
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    print("🤖 Loto boti ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())