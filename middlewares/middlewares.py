from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
from database import async_session_maker
from database.repositories import UserRepository
import logging

logger = logging.getLogger(__name__)


class BanCheckMiddleware(BaseMiddleware):
    """Foydalanuvchi ban ekanligini tekshiruvchi middleware"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)
        
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        if not user_id:
            return await handler(event, data)
        
        async with async_session_maker() as session:
            user_repo = UserRepository(session)
            is_banned = await user_repo.is_banned(user_id)
        
        if is_banned:
            ban_message = (
                "🚫 <b>Ваш аккаунт заблокирован</b>\n\n"
                "Вы не можете использовать бота.\n"
                "Для разблокировки обратитесь в поддержку."
            )
            
            if isinstance(event, Message):
                await event.answer(ban_message, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "🚫 Ваш аккаунт заблокирован",
                    show_alert=True
                )
                try:
                    await event.message.answer(ban_message, parse_mode="HTML")
                except:
                    pass
            
            logger.info(f"Banned user {user_id} tried to use bot")
            return 
        
        return await handler(event, data)