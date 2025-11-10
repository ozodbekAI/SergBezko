import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from database import engine
from database.models import Base
from handlers import start, product_card, normalize, video, photo, cabinet , common, admin 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def main():
    await create_tables()
    bot = Bot(token=settings.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(common.router)
    dp.include_router(start.router)
    dp.include_router(product_card.router)
    dp.include_router(normalize.router)
    dp.include_router(video.router)
    dp.include_router(photo.router)
    dp.include_router(cabinet.router)
    dp.include_router(admin.router)
    logger.info("Bot started")
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())