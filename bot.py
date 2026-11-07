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

# --- BAZA VA SAVOLLAR ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS questions 
            (id INTEGER PRIMARY KEY, question TEXT, opt1 TEXT, opt2 TEXT, opt3 TEXT, opt4 TEXT, correct_opt INTEGER)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS users 
            (user_id INTEGER PRIMARY KEY, role TEXT, status TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS queues 
            (user_id INTEGER PRIMARY KEY, mode TEXT, status TEXT DEFAULT 'waiting')""")
        await db.commit()

        cursor = await db.execute("SELECT COUNT(*) FROM questions")
        count = (await cursor.fetchone())[0]

        if count == 0:
            print("⏳ 50 ta tayyor savol bazaga yozilmoqda...")
            savollar = [
                ("O'zbekistonning poytaxti qaysi shahar?", "Toshkent", "Samarqand", "Buxoro", "Namangan", 1),
                ("Dunyodagi eng baland tog' qaysi?", "Everest", "Elbrus", "Kilimanjaro", "Montblan", 1),
                ("Eng katta okean qaysi?", "Tinch okeani", "Atlantika", "Hind okeani", "Shimoliy Muz", 1),
                ("2 + 2 * 2 nechaga teng?", "6", "8", "4", "10", 1),
                ("Quyosh qaysi tomondan chiqadi?", "Sharqdan", "G'arbdan", "Shimoldan", "Janubdan", 1),
                ("Telegram kim tomonidan yaratilgan?", "Pavel Durov", "Mark Zuckerberg", "Bill Gates", "Steve Jobs", 1),
                ("O'zbekiston qachon mustaqil bo'lgan?", "1991", "1989", "1992", "1990", 1),
                ("Eng katta qit'a qaysi?", "Osiyo", "Afrika", "Yevropa", "Amerika", 1),
                ("Suv qanday haroratda qaynaydi?", "100°C", "90°C", "110°C", "80°C", 1),
                ("1 kilogramm necha gramm?", "1000", "100", "500", "10000", 1),
                ("Qaysi hayvon eng tez yuguradi?", "Gepard", "Sher", "Yo'lbars", "Ot", 1),
                ("Inson tanasidagi eng katta organ qaysi?", "Teri", "Jigar", "O'pka", "Yurak", 1),
                ("Qaysi metall suvda cho'kadi?", "Temir", "Yog'och", "Plastik", "Muz", 1),
                ("1 yilda nechta hafta bor?", "52", "48", "50", "54", 1),
                ("Qonning rangi qanday rangda bo'ladi?", "Qizil", "Ko'k", "Yashil", "Sariq", 1),
                ("Eng kichik qit'a qaysi?", "Avstraliya", "Yevropa", "Antarktida", "Janubiy Amerika", 1),
                ("Qaysi hayvon sut emizuvchi?", "Kit", "Akula", "Krokodil", "Toshbaqa", 1),
                ("Kompyuterning miyasi nima deyiladi?", "Protsessor", "Monitor", "Klaviatura", "Sichqoncha", 1),
                ("Quyosh sistemamizdagi eng issiq sayyora qaysi?", "Venera", "Mars", "Merkuriy", "Yupiter", 1),
                ("Inson umurtqa pog'onasi nechta umurtqadan iborat?", "33", "30", "28", "35", 1),
                ("Eng qattiq tabiiy modda qaysi?", "Olmos", "Temir", "Granit", "Oltin", 1),
                ("Qaysi gaz o'simliklar uchun zarur?", "Karbonat angidrid", "Kislorod", "Azot", "Vodorod", 1),
                ("Eng ko'p aholisi bo'lgan davlat qaysi?", "Hindiston", "Xitoy", "AQSH", "Indoneziya", 1),
                ("Muzning kimyoviy formulasi qanday?", "H2O", "CO2", "O2", "H2O2", 1),
                ("Qaysi hayvon eng uzoq umr ko'radi?", "Toshbaqa", "Fil", "Kit", "Akula", 1),
                ("Eng katta cho'l qaysi?", "Sahroi Kabir", "Gobi", "Karakum", "Atakama", 1),
                ("Qadimgi Misrda qanday yozuv ishlatilgan?", "Iyeroglif", "Lotin", "Kirill", "Arab", 1),
                ("Birinchi jahon urushi qachon boshlangan?", "1914", "1918", "1939", "1945", 1),
                ("Inson tanasida nechta suyak bor (kattalarda)?", "206", "200", "210", "220", 1),
                ("Quyoshdan Yergacha masofa qancha?", "150 mln km", "100 mln km", "200 mln km", "50 mln km", 1),
                ("Eng katta hayvon qaysi?", "Ko'k kit", "Fil", "Jirafa", "Karkidon", 1),
                ("Qaysi davlatda eng ko'p vaqt zonalari bor?", "Fransiya", "Rossiya", "Xitoy", "AQSH", 1),
                ("Suv necha darajada muzlaydi?", "0°C", "-10°C", "10°C", "-5°C", 1),
                ("Qaysi vitamin quyosh nuridan olinadi?", "D vitamini", "C vitamini", "A vitamini", "B vitamini", 1),
                ("Fotosintez qayerda sodir bo'ladi?", "Xloroplast", "Mitoxondriya", "Yadro", "Sitoplazma", 1),
                ("Eng katta o'rmon qayerda?", "Amazonka", "Sibir", "Afrika", "Kanada", 1),
                ("Qaysi hayvon eng zaharli?", "Kubomeduza", "Ilon", "Chayon", "O'rgimchak", 1),
                ("Dunyodagi eng chuqur joy qaysi?", "Mariana cho'kmasi", "Temza", "Hind okeani", "Atlantika", 1),
                ("Eng ko'p ishlatiladigan dasturlash tili (2023)?", "Python", "Java", "C++", "JavaScript", 1),
                ("O'zbekistonning eng baland nuqtasi?", "Hazrat Sulton", "Beshtor", "Chimyon", "Tyan-Shan", 1),
                ("Eng katta sayyora qaysi?", "Yupiter", "Saturn", "Neptun", "Yer", 1),
                ("O'zbekiston bayrog'ida nechta yulduz bor?", "12", "11", "10", "9", 1),
                ("Eng qadimgi tsivilizatsiya qaysi?", "Misr", "Rim", "Yunon", "Xitoy", 1),
                ("Qaysi yilda internet ixtiro qilindi?", "1969", "1980", "1995", "2000", 1),
                ("Dunyoda eng ko'p sotilgan kitob qaysi?", "Bibliya", "Qur'on", "Ginnes", "Don Kixot", 1),
                ("Qaysi sayyora Quyoshga eng yaqin?", "Merkuriy", "Venera", "Yer", "Mars", 1),
                ("Inson qon guruhi nechta asosiy turga bo'linadi?", "4", "3", "5", "6", 1),
                ("Eng qadimgi universitet qayerda?", "Bolonya", "Oksford", "Kembrij", "Sorbonna", 1),
                ("Eng katta orol qaysi?", "Grenlandiya", "Madagaskar", "Borneo", "Yangi Gvineya", 1)
            ]
            for q in savollar:
                await db.execute("INSERT INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,?)", q)
            await db.commit()
            print("✅ Savollar yozildi!")

# --- KLAVIATURALAR ---
class GameCB(CallbackData, prefix="gm"):
    action: str
    val: int = 0

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
async def cmd_start(message: Message):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, role, status) VALUES (?, 'user', 'none')", (message.from_user.id,))
        await db.commit()
        
    text = (
        f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n"
        f"🃏 Men Joker! Sizni o'z o'yinimga taklif etaman.\n"
        f"🎁 Omadingizni sinab ko'ring va yutuqlarni qo'lga kiriting!\n\n"
        f"👇 O'yin turini tanlang:"
    )
    try:
        await message.answer_photo(photo=JOKER_IMG_URL, caption=text, reply_markup=main_menu(), parse_mode="HTML")
    except:
        await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.answer("Asosiy menyu:", reply_markup=main_menu())
    await callback.answer()

# --- YOSHLAR O'YINI ---
@router.callback_query(GameCB.filter(F.action == "youth_start"))
async def youth_start(callback: CallbackQuery):
    await callback.message.answer("🎯 <b>Kartani tanlang!</b>", reply_markup=get_cards(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(GameCB.filter(F.action == "open_card"))
async def open_card(callback: CallbackQuery, callback_data: GameCB):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
        q = await cursor.fetchone()

    options = [q['opt1'], q['opt2'], q['opt3'], q['opt4']]
    random.shuffle(options)
    correct_text = q[f"opt{q['correct_opt']}"]
    
    builder = InlineKeyboardBuilder()
    for opt in options:
        is_correct = "1" if opt == correct_text else "0"
        builder.button(text=opt, callback_data=GameCB(action="youth_answer", val=int(f"{is_correct}")).pack())
    builder.adjust(2)
    
    text = f"❓ <b>SAVOL:</b> {q['question']}\n\n⏳ Javob berish uchun 15 soniya vaqt:"
    msg = await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    
    asyncio.create_task(youth_timeout(msg, callback.from_user.id))

async def youth_timeout(message: Message, user_id: int):
    await asyncio.sleep(15.0)
    try:
        await message.edit_text(
            f"⏳ <b>Vaqt tugadi!</b>\n\n🎰 Senga Jokerning xabari bor, o'qib ko'r:\n<i>\"Bu qovoqni ishlat bolakay!\"</i> 🎃",
            reply_markup=main_menu(), parse_mode="HTML"
        )
    except: pass

@router.callback_query(GameCB.filter(F.action == "youth_answer"))
async def youth_check_answer(callback: CallbackQuery, callback_data: GameCB):
    is_correct = str(callback_data.val)[-1] == "1"
    if is_correct:
        text = f"🎉 <b>TABRIKLAYMIZ, SIZ YUTDINGIZ!</b> 🎉\n\n🎁 Yutug'ingiz: <b>15% CHEGIRMA</b>\n\n📍 Urgut tumanidagi 3-umumta'lim maktabi ro'parasidagi <b>Super Mini Market</b>dan xarid qiling.\n\n📸 Chegirmadan foydalanish uchun <b>skrinshot</b> oling!"
        await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
    else:
        await callback.message.edit_text(f"❌ <b>Xato javob!</b>\n\n🎰 Senga Jokerning xabari bor, o'qib ko'r:\n<i>\"Bu qovoqni ishlat bolakay!\"</i> 🎃", reply_markup=main_menu(), parse_mode="HTML")
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
    text = f"💳 <b>To'lov ({amount} so'm)</b>\n\nTo'lovni kartaga o'tkazing:\n<code>{KARTA_RAQAMI}</code>\n<b>{KARTA_EGASI}</b>\n\n📸 Chek skrinshotini shu yerga yuboring."
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state("waiting_for_receipt")
    await callback.answer()

@router.message(F.photo, StateFilter("waiting_for_receipt"))
async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    data = await state.get_data()
    mode = data.get("mode", "pay_2")
    amount = "12,000" if mode == "pay_2" else "17,000"
    await state.clear()
    admin_text = f"🧾 <b>Yangi chek!</b>\n👤 {message.from_user.full_name}\n🆔 <code>{user_id}</code>\n💰 {amount}\n🎮 {'2 kishilik' if mode == 'pay_2' else '4 kishilik'}\n\nTasdiqlaysizmi?"
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"approve_{mode}_{user_id}")
    builder.button(text="❌ Rad etish", callback_data=f"reject_{user_id}")
    try: 
        await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except: 
        pass
    await message.answer("⏳ Chek adminga yuborildi. Tasdiqlanishini kuting...")

@router.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID: return
    
    try:
        _, mode, user_id = callback.data.split("_")
        user_id = int(user_id)
    except:
        return await callback.answer("Xato ma'lumot!", show_alert=True)

    await callback.answer("Bajarilmoqda...", show_alert=False)

    try:
        await bot.send_message(ADMIN_ID, f"✅ <b>To'lov tasdiqlandi!</b>\nID: <code>{user_id}</code>", parse_mode="HTML")
    except: pass

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO queues (user_id, mode, status) VALUES (?, ?, 'waiting')", (user_id, mode))
        await db.commit()
        
        cursor = await db.execute("SELECT user_id FROM queues WHERE mode = ? AND status = 'waiting' LIMIT 4", (mode,))
        waiting_users = [row[0] for row in await cursor.fetchall()]

    required_count = 2 if mode == "pay_2" else 4
    
    if len(waiting_users) < required_count:
        try: 
            await bot.send_message(user_id, "✅ To'lov tasdiqlandi! Navbatga qo'shildingiz. Raqiblaringizni kuting...")
        except: pass
    else:
        players = waiting_users[:required_count]
        async with aiosqlite.connect(DB_PATH) as db:
            for p in players:
                await db.execute("UPDATE queues SET status = 'playing' WHERE user_id = ?", (p,))
            await db.commit()
            
        prize = 18000 if mode == "pay_2" else 25500 
        
        for p in players:
            try:
                await bot.send_message(p, "⚔️ Barcha ishtirokchilar yig'ildi! O'yin boshlanmoqda...")
            except: pass
                
        await start_duel(bot, players, "2 kishilik" if mode == "pay_2" else "4 kishilik", prize)

@router.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID: return
    
    try:
        rejected_user_id = int(callback.data.split("_")[1])
    except:
        return await callback.answer("Xato ma'lumot!", show_alert=True)
    
    await callback.answer("Bekor qilindi", show_alert=False)
    
    try:
        await bot.send_message(ADMIN_ID, f"❌ To'lov rad etildi. (ID: {rejected_user_id})")
    except: pass
    
    try:
        await bot.send_message(
            rejected_user_id, 
            "❌ <b>Afsuski, to'lovingiz admin tomonidan rad etildi yoki chek noto'g'ri yuborilgan.</b>\n\n"
            "Iltimos, to'lovni qaytadan amalga oshirib, chekni botga qayta yuboring.", 
            parse_mode="HTML"
        )
    except: pass

async def start_duel(bot: Bot, players: list, duel_type: str, prize: int):
    duel_id = random.randint(1000, 9999)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
        q = await cursor.fetchone()

    options = [q['opt1'], q['opt2'], q['opt3'], q['opt4']]
    random.shuffle(options)
    correct_text = q[f"opt{q['correct_opt']}"]
    
    builder = InlineKeyboardBuilder()
    for opt in options:
        is_correct = "1" if opt == correct_text else "0"
        builder.button(text=opt, callback_data=GameCB(action="duel_answer", val=int(f"{duel_id}{is_correct}")).pack())
    builder.adjust(2)
    
    text = f"⚔️ <b>BELLASHUV BOSHLANDI!</b> ⚔️\n({duel_type} o'yini)\n\nKim birinchi bo'lib to'g'ri javobni bosadi, o'sha <b>{prize:,} so'm</b> yutadi!\n\n❓ <b>SAVOL:</b> {q['question']}"
    
    for player in players:
        try: 
            await bot.send_message(player, text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except: 
            pass

@router.callback_query(GameCB.filter(F.action == "duel_answer"))
async def duel_answer(callback: CallbackQuery, callback_data: GameCB, bot: Bot):
    ans_data = str(callback_data.val)
    duel_id = int(ans_data[:-1])
    is_correct = ans_data[-1] == "1"
    user_id = callback.from_user.id
    
    await callback.answer()
    
    if is_correct:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT mode FROM queues WHERE user_id = ? AND status = 'playing'", (user_id,))
            row = await cursor.fetchone()
            if row:
                mode = row[0]
                await db.execute("DELETE FROM queues WHERE mode = ? AND status = 'playing'", (mode,))
                await db.commit()
                prize = 18000 if mode == "pay_2" else 25500
            else:
                prize = 18000
        
        try:
            await bot.send_message(user_id, f"🎉 <b>TABRIKLAYMIZ, SIZ YUTDINGIZ!</b> 🎉\n\nSiz raqiblaringizni tezroq yutdingiz va <b>{prize:,} so'mni</b> qo'lga kiritdingiz!\n\nAdmin pulni o'tkazishi uchun karta raqamingizni yuboring:")
            await bot.send_message(ADMIN_ID, f"⚔️ <b>Bellashuv yakunlandi!</b>\n🏆 G'olib ID: <code>{user_id}</code>\n💰 Yutuq: {prize:,} so'm\n\nG'olibdan karta raqamini so'rang!")
        except: pass
        
        try: 
            await callback.message.edit_text("✅ Siz to'g'ri javob berdingiz va yutdingiz! Admin bilan bog'lanasiz.", reply_markup=main_menu())
        except: pass
    else:
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
        try: 
            await callback.message.edit_text(aqlli_gap, reply_markup=main_menu(), parse_mode="HTML")
        except: pass
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id FROM queues WHERE status = 'playing'")
            playing_users = [r[0] for r in await cursor.fetchall()]
            for p in playing_users:
                if p != user_id:
                    try: await bot.send_message(p, aqlli_gap, parse_mode="HTML")
                    except: pass

# --- ISHGA TUSHIRISH ---
async def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    await init_db()
    bot = Bot(token=TOKEN)
    try: await bot.delete_webhook(drop_pending_updates=True)
    except: pass
    dp = Dispatcher()
    dp.include_router(router)
    print("🤖 Tizim ishga tushdi. Bot to'liq tayyor!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())