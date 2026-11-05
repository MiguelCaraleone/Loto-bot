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
TOKEN = "9237388648:AAHNnfVKjUc5wWH3-UnKodCPJ31UMbI092M" 
ADMIN_ID = 1302845749
DB_PATH = "loto_game.db"
KARTA_RAQAMI = "9860 3501 4780 2176"
KARTA_EGASI = "Mamatkulov Izzatillo"

# --- XOTIRADAGI NAVBATLAR ---
queue_2 = [] 
queue_4 = []
active_duels = {} # {duel_id: {'players': [], 'answers': {}, 'winner': None}}

# --- 1. AVTOMATIK SAVOLLAR VA BAZA ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS questions 
            (id INTEGER PRIMARY KEY, question TEXT, opt1 TEXT, opt2 TEXT, opt3 TEXT, opt4 TEXT, correct_opt INTEGER)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS users 
            (user_id INTEGER PRIMARY KEY, role TEXT, status TEXT)""")
        await db.commit()

        cursor = await db.execute("SELECT COUNT(*) FROM questions")
        count = (await cursor.fetchone())[0]

        if count < 1000:
            print("⏳ 1000 ta savol avtomatik tayyorlanmoqda, iltimos kuting...")
            
            # Matematik savollar (200 ta)
            for _ in range(200):
                a, b = random.randint(10, 100), random.randint(10, 100)
                op = random.choice(['+', '-', '*'])
                if op == '+': ans = a + b
                elif op == '-': ans = a - b
                else: ans = a * b
                wrong1, wrong2, wrong3 = ans + random.randint(1, 10), ans - random.randint(1, 10), ans + random.randint(11, 20)
                opts = [ans, wrong1, wrong2, wrong3]
                random.shuffle(opts)
                correct = opts.index(ans) + 1
                await db.execute("INSERT INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,?)",
                                 (f"{a} {op} {b} nechaga teng?", str(opts[0]), str(opts[1]), str(opts[2]), str(opts[3]), correct))

            # Geografiya (10 ta)
            geo = [
                ("O'zbekiston poytaxti qaysi shahar?", "Toshkent", "Samarqand", "Buxoro", "Andijon", 1),
                ("Eng katta okean qaysi?", "Tinch okeani", "Atlantika", "Hind okeani", "Shimoliy Muz", 1),
                ("Dunyodagi eng baland tog' qaysi?", "Everest", "Elbrus", "Kilimanjaro", "Montblan", 1),
                ("Eng uzun daryo qaysi?", "Nil", "Amazonka", "Yanszi", "Missisipi", 1),
                ("Eng katta qit'a qaysi?", "Osiyo", "Afrika", "Yevropa", "Shimoliy Amerika", 1),
                ("Eng katta ko'l qaysi?", "Kaspiy", "Baykal", "Viktoriya", "Orol", 1),
                ("Fransiya poytaxti qaysi?", "Parij", "London", "Berlin", "Rim", 1),
                ("Misr poytaxti qaysi?", "Qohira", "Damashq", "Bag'dod", "Ar-Riyod", 1),
                ("Yaponiyaning eng katta shahri?", "Tokio", "Kioto", "Osaka", "Xirosima", 1),
                ("AQSH poytaxti qaysi?", "Vashington", "Nyu-York", "Los-Anjeles", "Chikago", 1),
            ]
            for q in geo:
                await db.execute("INSERT INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,?)", q)

            # Tarix (10 ta)
            hist = [
                ("O'zbekiston qachon mustaqil bo'lgan?", "1991", "1989", "1992", "1990", 1),
                ("Birinchi jahon urushi qachon boshlangan?", "1914", "1918", "1939", "1945", 1),
                ("Ikkinchi jahon urushi qachon boshlangan?", "1939", "1941", "1945", "1914", 1),
                ("Buyuk ipak yo'li qayerdan o'tgan?", "O'zbekiston", "Misr", "Xitoy", "Hindiston", 1),
                ("Amir Temur qachon tug'ilgan?", "1336", "1405", "1200", "1300", 1),
                ("Bobur qachon tug'ilgan?", "1483", "1526", "1500", "1400", 1),
                ("O'zbekiston Mustaqillik kuni qachon?", "1-sentabr", "8-dekabr", "31-avgust", "1-yanvar", 1),
                ("Telegram qachon yaratilgan?", "2013", "2010", "2015", "2018", 1),
                ("Internet qachon ixtiro qilingan?", "1969", "1980", "1995", "2000", 1),
                ("Birinchi sun'iy yo'ldosh qachon uchirilgan?", "1957", "1961", "1969", "1970", 1),
            ]
            for q in hist:
                await db.execute("INSERT INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,?)", q)

            # Biologiya (10 ta)
            bio = [
                ("Eng katta hayvon qaysi?", "Ko'k kit", "Fil", "Jirafa", "Karkidon", 1),
                ("Eng tez yuguradigan hayvon qaysi?", "Gepard", "Sher", "Yo'lbars", "Ot", 1),
                ("Eng zaharli hayvon qaysi?", "Kubomeduza", "Ilon", "Chayon", "O'rgimchak", 1),
                ("Inson tanasidagi eng katta organ qaysi?", "Teri", "Jigar", "O'pka", "Yurak", 1),
                ("Qonning rangi qanday?", "Qizil", "Ko'k", "Yashil", "Sariq", 1),
                ("Fotosintez qayerda sodir bo'ladi?", "Xloroplast", "Mitoxondriya", "Yadro", "Sitoplazma", 1),
                ("Eng katta qush qaysi?", "Tuyaqush", "Burgut", "Kondor", "To'ti", 1),
                ("Eng baland sakraydigan hayvon?", "Kenguru", "Sher", "Yo'lbars", "Gepard", 1),
                ("Qaysi hayvon sut emizuvchi?", "Kit", "Akula", "Krokodil", "Toshbaqa", 1),
                ("Eng uzoq umr ko'radigan hayvon?", "Toshbaqa", "Fil", "Kit", "Akula", 1),
            ]
            for q in bio:
                await db.execute("INSERT INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,?)", q)

            # Adabiyot (10 ta)
            lit = [
                ("Alpomish dostoni qahramoni kim?", "Alpomish", "Go'ro'g'li", "Manas", "Kor o'g'li", 1),
                ("Navoiyning taxallusi nima?", "Alisher", "Lutfiy", "Foniy", "Bobur", 1),
                ("Boburnoma muallifi kim?", "Bobur", "Navoiy", "Lutfiy", "Mashrab", 1),
                ("O'tkan kunlar muallifi kim?", "Abdulla Qodiriy", "Cho'lpon", "Fitrat", "Oybek", 1),
                ("Shekspirning mashhur asari qaysi?", "Romeo va Julyetta", "Alpomish", "O'tkan kunlar", "Kecha va kunduz", 1),
                ("Dunyo bo'yicha eng ko'p sotilgan kitob qaysi?", "Bibliya", "Qur'on", "Ginnes", "Don Kixot", 1),
                ("O'zbek tilining asoschisi kim?", "Alisher Navoiy", "Bobur", "Lutfiy", "Mashrab", 1),
                ("Alisher Navoiy qayerda tug'ilgan?", "Hirot", "Buxoro", "Samarqand", "Toshkent", 1),
                ("Zulfiya kim?", "Shoira", "Yozuvchi", "Rassom", "Xonanda", 1),
                ("O'zbek xalq ertaklari qahramoni kim?", "Eshmat", "Toshmat", "Alpomish", "Go'ro'g'li", 1),
            ]
            for q in lit:
                await db.execute("INSERT INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,?)", q)

            # Qolgan 740 ta savol (jami 1000 ta bo'lguncha avtomatik generatsiya)
            mavzular = ["Fan", "Sport", "San'at", "Musiqa", "Texnologiya", "Geografiya", "Tarix"]
            while True:
                cursor = await db.execute("SELECT COUNT(*) FROM questions")
                current_count = (await cursor.fetchone())[0]
                if current_count >= 1000: break
                
                m = random.choice(mavzular)
                savol = f"{m} bo'yicha bilimingizni sinang #{current_count+1}?"
                togri = "To'g'ri javob"
                opts = [togri, "Xato 1", "Xato 2", "Xato 3"]
                random.shuffle(opts)
                correct = opts.index(togri) + 1
                
                await db.execute("INSERT INTO questions (question, opt1, opt2, opt3, opt4, correct_opt) VALUES (?,?,?,?,?,?)",
                                 (savol, opts[0], opts[1], opts[2], opts[3], correct))

            await db.commit()
            print("✅ 1000 ta savol muvaffaqiyatli tayyorlandi!")

# --- 2. KLAVIATURALAR ---
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

# --- 3. HANDLERLAR ---
router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, role, status) VALUES (?, 'user', 'none')", (message.from_user.id,))
        await db.commit()
        
    text = f"👋 Salom, <b>{message.from_user.first_name}</b>!\n\n🎰 <b>Super Mini Market Loto</b> botiga xush kelibsiz!\n\n👇 O'yin turini tanlang:"
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("Asosiy menyu:", reply_markup=main_menu())
    await callback.answer()

# --- YOSHLAR O'YINI ---
@router.callback_query(GameCB.filter(F.action == "youth_start"))
async def youth_start(callback: CallbackQuery):
    await callback.message.edit_text("🎯 <b>Kartani tanlang!</b>", reply_markup=get_cards(), parse_mode="HTML")
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
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    
    asyncio.create_task(youth_timeout(callback.message, callback.from_user.id))

async def youth_timeout(message: Message, user_id: int):
    await asyncio.sleep(15.0)
    try:
        await message.edit_text(
            f"⏳ <b>Vaqt tugadi!</b>\n\n"
            f"🎰 Senga Jokerning xabari bor, o'qib ko'r:\n"
            f"<i>\"Bu qovoqni ishlat bolakay!\"</i> 🎃",
            reply_markup=main_menu(), parse_mode="HTML"
        )
    except:
        pass

@router.callback_query(GameCB.filter(F.action == "youth_answer"))
async def youth_check_answer(callback: CallbackQuery, callback_data: GameCB):
    is_correct = str(callback_data.val)[-1] == "1"
    
    if is_correct:
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

# --- 4. KATTALAR BELLASHUVI (PvP) ---
@router.callback_query(GameCB.filter(F.action == "adult_menu"))
async def adult_menu_handler(callback: CallbackQuery):
    await callback.message.edit_text("👨 <b>Kattalar uchun bellashuv turini tanlang:</b>", reply_markup=adult_menu(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(GameCB.filter(F.action.in_({"pay_2", "pay_4"})))
async def adult_pay(callback: CallbackQuery, callback_data: GameCB, state: FSMContext):
    mode = callback_data.action 
    amount = "12,000" if mode == "pay_2" else "17,000"
    await state.update_data(mode=mode)
    
    text = (
        f"💳 <b>To'lov ({amount} so'm)</b>\n\n"
        f"To'lovni quyidagi kartaga o'tkazing:\n"
        f"<code>{KARTA_RAQAMI}</code>\n<b>{KARTA_EGASI}</b>\n\n"
        f"📸 Chek skrinshotini shu yerga yuboring."
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await state.set_state("waiting_for_receipt")
    await callback.answer()

@router.message(F.photo, StateFilter("waiting_for_receipt"))
async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    data = await state.get_data()
    mode = data.get("mode", "pay_2")
    amount = "12,000" if mode == "pay_2" else "17,000"
    await state.clear()
    
    admin_text = f"🧾 <b>Yangi to'lov cheki!</b>\n\n👤 {message.from_user.full_name}\n🆔 <code>{user_id}</code>\n💰 Summa: {amount}\n🎮 Tur: {'2 kishilik' if mode == 'pay_2' else '4 kishilik'}\n\nTasdiqlaysizmi?"
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"approve_{mode}_{user_id}")
    builder.button(text="❌ Rad etish", callback_data="reject")
    
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await message.answer("⏳ Chek adminga yuborildi. Tasdiqlanishini kuting...")

@router.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != ADMIN_ID: return
    
    try:
        _, mode, user_id = callback.data.split("_")
        user_id = int(user_id)
    except:
        return await callback.answer("Xato ma'lumot!", show_alert=True)

    try:
        await callback.message.edit_caption(caption="✅ To'lov tasdiqlandi! O'yinchi navbatga qo'shildi.")
    except: pass
    
    await callback.answer("Tasdiqlandi!")

    if mode == "pay_2":
        if user_id not in queue_2: queue_2.append(user_id)
        try: await bot.send_message(user_id, "✅ To'lov tasdiqlandi! (2 kishilik). Navbatga qo'shildingiz, raqibingizni kuting...")
        except: pass
            
        if len(queue_2) >= 2:
            p1, p2 = queue_2.pop(0), queue_2.pop(0)
            await start_duel(bot, [p1, p2], "2 kishilik", 20000)
            
    elif mode == "pay_4":
        if user_id not in queue_4: queue_4.append(user_id)
        try: await bot.send_message(user_id, "✅ To'lov tasdiqlandi! (4 kishilik). Navbatga qo'shildingiz, raqiblaringizni kuting...")
        except: pass
            
        if len(queue_4) >= 4:
            p1, p2, p3, p4 = queue_4.pop(0), queue_4.pop(0), queue_4.pop(0), queue_4.pop(0)
            await start_duel(bot, [p1, p2, p3, p4], "4 kishilik", 32000)

@router.callback_query(F.data == "reject")
async def reject_payment(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    try: await callback.message.edit_caption(caption="❌ To'lov rad etildi.")
    except: pass
    await callback.answer("Rad etildi!")

async def start_duel(bot: Bot, players: list, duel_type: str, prize: int):
    duel_id = random.randint(1000, 9999)
    active_duels[duel_id] = {'players': players, 'answers': {}, 'winner': None}
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
        q = await cursor.fetchone()

    if not q: return

    options = [q['opt1'], q['opt2'], q['opt3'], q['opt4']]
    random.shuffle(options)
    correct_text = q[f"opt{q['correct_opt']}"]
    
    builder = InlineKeyboardBuilder()
    for opt in options:
        is_correct = "1" if opt == correct_text else "0"
        builder.button(text=opt, callback_data=GameCB(action="duel_answer", val=int(f"{duel_id}{is_correct}")).pack())
    builder.adjust(2)
    
    text = (
        f"⚔️ <b>BELLASHUV BOSHLANDI!</b> ⚔️\n"
        f"({duel_type} o'yini)\n\n"
        f"Kim birinchi bo'lib to'g'ri javobni bosadi, o'sha <b>{prize:,} so'm</b> yutadi!\n\n"
        f"❓ <b>SAVOL:</b> {q['question']}"
    )
    
    for player in players:
        try:
            await bot.send_message(player, text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception as e:
            print(f"Xato: {e}")

@router.callback_query(GameCB.filter(F.action == "duel_answer"))
async def duel_answer(callback: CallbackQuery, callback_data: GameCB, bot: Bot):
    ans_data = str(callback_data.val)
    duel_id = int(ans_data[:-1])
    is_correct = ans_data[-1] == "1"
    
    if duel_id not in active_duels:
        return await callback.answer("Bu bellashuv allaqachon tugagan!", show_alert=True)
        
    duel = active_duels[duel_id]
    user_id = callback.from_user.id
    
    if duel['winner']:
        return await callback.answer("Afsuski, raqibingiz sizdan tezroq yutdi. Keyingi safar omad!", show_alert=True)
        
    if user_id not in duel['players']:
        return await callback.answer("Siz bu bellashuvda qatnashmayapsiz!", show_alert=True)
        
    if user_id in duel['answers']:
        return await callback.answer("Siz allaqachon javob berdingiz! Kutib turing.", show_alert=True)
        
    duel['answers'][user_id] = is_correct
    
    if is_correct:
        duel['winner'] = user_id
        prize = 20000 if len(duel['players']) == 2 else 32000
        
        try:
            await bot.send_message(user_id, f"🎉 <b>TABRIKLAYMIZ, SIZ YUTDINGIZ!</b> 🎉\n\nSiz raqiblaringizni tezroq yutdingiz va <b>{prize:,} so'mni</b> qo'lga kiritdingiz!\n\nAdmin pulni o'tkazishi uchun karta raqamingizni yuboring:")
            await bot.send_message(ADMIN_ID, f"⚔️ <b>Bellashuv yakunlandi!</b>\n🏆 G'olib ID: <code>{user_id}</code>\n💰 Yutuq: {prize:,} so'm\n\nG'olibdan karta raqamini so'rang!")
        except: pass
        
        for p in duel['players']:
            if p != user_id:
                try:
                    await bot.send_message(p, f"❌ <b>Afsuski, siz yutqazdingiz.</b>\n\nRaqibingiz sizdan tezroq to'g'ri javob berdi. Omad keyingi safar!")
                except: pass
                    
        try: await callback.message.edit_text("✅ Siz to'g'ri javob berdingiz va yutdingiz! Admin bilan bog'lanasiz.", reply_markup=main_menu())
        except: pass
        
    else:
        try: await callback.message.edit_text("❌ Xato javob! Qolgan o'yinchilar yutishi mumkin. Kuting...", reply_markup=main_menu())
        except: pass
        
        if len(duel['answers']) == len(duel['players']):
            try: await bot.send_message(ADMIN_ID, f"⚠️ Bellashuvda hamma xato qildi! (Duel ID: {duel_id}). Hech kim yutmadi.")
            except: pass
            del active_duels[duel_id]

# --- 5. ISHGA TUSHIRISH ---
async def main():
    await init_db()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    print("🤖 Tizim ishga tushdi. Bot to'liq tayyor!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())