from aiogram.types import Message
from config import settings
import logging

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.tiff', '.heic'}


async def get_photo_url_from_message(message: Message) -> str:
    if message.photo:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        photo_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
        logger.info(f"Photo received: {photo_url}")
        return photo_url
    
    if message.document:
        doc = message.document
        

        if not doc.mime_type or not doc.mime_type.startswith('image/'):
            raise ValueError("❌ Faqat rasm fayllari qabul qilinadi.")
        
        file_name = doc.file_name or ""
        if '.' in file_name:
            file_ext = '.' + file_name.lower().split('.')[-1]
            if file_ext not in SUPPORTED_IMAGE_FORMATS:
                logger.warning(f"Noma'lum rasm format: {file_ext}")
        
        file = await message.bot.get_file(doc.file_id)
        photo_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
        logger.info(f"Document (image) received: {photo_url} (mime: {doc.mime_type})")
        return photo_url
    
    raise ValueError("❌ Iltimos, rasm yuboring (foto yoki fayl sifatida).")