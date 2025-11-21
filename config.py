from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    BOT_TOKEN: str
    BOT_USERNAME: str
    
    DATABASE_URL: str
    
    KIE_API_KEY: str
    KIE_API_URL: str = "https://api.kie.ai/v1"
    
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    SUCCESS_REDIRECT_URL: str = ""
    
    RETENTION_HOURS: int = 24
    ADMIN_IDS: str = ""

    TELEGRAM_API_SERVER: str = ""
    
    @property
    def admin_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(',') if x.strip()]


settings = Settings()