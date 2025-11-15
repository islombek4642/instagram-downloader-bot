from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass
class Settings:
    bot_token: str
    rapidapi_key: str
    rapidapi_host: str
    rapidapi_url: str
    admin_chat_id: int | None = None


def get_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    rapidapi_host = os.getenv("RAPIDAPI_HOST")
    rapidapi_url = os.getenv("RAPIDAPI_URL")
    admin_chat_id_raw = os.getenv("ADMIN_CHAT_ID")

    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in environment")
    if not rapidapi_key:
        raise RuntimeError("RAPIDAPI_KEY is not set in environment")
    if not rapidapi_host:
        raise RuntimeError("RAPIDAPI_HOST is not set in environment")
    if not rapidapi_url:
        raise RuntimeError("RAPIDAPI_URL is not set in environment")

    admin_chat_id: int | None = None
    if admin_chat_id_raw:
        try:
            admin_chat_id = int(admin_chat_id_raw)
            # Telegram chat ID lar odatda manfiy yoki musbat katta raqamlar
            if admin_chat_id == 0 or abs(admin_chat_id) < 100:
                raise ValueError("Invalid chat ID range")
        except (ValueError, TypeError) as exc:
            print(f"Warning: Invalid ADMIN_CHAT_ID format '{admin_chat_id_raw}': {exc}")
            admin_chat_id = None

    return Settings(
        bot_token=bot_token,
        rapidapi_key=rapidapi_key,
        rapidapi_host=rapidapi_host,
        rapidapi_url=rapidapi_url,
        admin_chat_id=admin_chat_id,
    )
