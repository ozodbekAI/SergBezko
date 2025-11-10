from deep_translator import GoogleTranslator
import logging

logger = logging.getLogger(__name__)


class TranslatorService:
    def __init__(self):
        self.translator = GoogleTranslator(source='ru', target='en')
    
    async def translate_ru_to_en(self, text: str) -> str:
        try:
            if not text:
                return text
            if text.isascii() and all(ord(c) < 128 for c in text):
                return text
            translated = self.translator.translate(text)
            logger.info(f"Translated: '{text}' -> '{translated}'")
            return translated
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text


translator_service = TranslatorService()