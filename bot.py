import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

TOKEN = "YANGI_TOKENNI_SHU_YERGA_QOYING"

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    @dp.message(F.text)
    async def echo_handler(message: Message):
        await message.answer(f"Siz yozdingiz: {message.text}\n\nTest muvaffaqiyatli o'tdi!")

    print("Test bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())