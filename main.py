import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import settings
from database import engine
from database.models import Base
from handlers import admin_poses, admin_scene, admin_video_scenarios, start, product_card, normalize, video, photo, cabinet , common, admin, repeat_handler, admin_model_type, admin_normalize, admin_packege
from middlewares.middlewares import BanCheckMiddleware 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def main():
    await create_tables()
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML 
        )
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.message.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())

    dp.include_router(repeat_handler.router)
    dp.include_router(normalize.router)
    dp.include_router(photo.router)
    dp.include_router(product_card.router)
    dp.include_router(video.router)
    dp.include_router(common.router)
    dp.include_router(start.router)
    dp.include_router(cabinet.router)
    dp.include_router(admin.router)
    dp.include_router(admin_poses.router)
    dp.include_router(admin_scene.router)
    dp.include_router(admin_model_type.router)
    dp.include_router(admin_video_scenarios.router)
    dp.include_router(admin_normalize.router)
    dp.include_router(admin_packege.router)
    logger.info("Bot started")
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())