from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from ..db.database import upsert_user
from ..keyboards.common import get_main_menu_keyboard


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    user = update.effective_user
    if user is not None:
        upsert_user(
            chat_id=update.effective_chat.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
        )

    text = (
        "👋 Assalomu alaykum!\n\n"
        "Men ijtimoiy tarmoqlardan (Instagram, YouTube, TikTok va boshqalar) media yuklab beradigan botman.\n\n"
        "📝 Foydalanish:\n"
        "1️⃣ Ijtimoiy tarmoqdagi post/reels/video linkini yuboring.\n"
        "2️⃣ Men media fayl(lar)ni sizga qaytaraman.\n\n"
        "Misollar:\n"
        "• https://www.instagram.com/p/XXXXXXXXXXX/\n"
        "• https://youtu.be/XXXXXXXXXXX\n\n"
        "ℹ️ Eslatma: Telegram botlari odatda ~50MB gacha fayllarni qabul qiladi. Katta fayllar uchun bevosita yuklab olish linkini yuboraman.\n"
        "Qo'shimcha ma'lumot uchun /help buyrug'ini yuboring."
    )

    await update.message.reply_text(text, reply_markup=get_main_menu_keyboard())


def get_start_handler() -> CommandHandler:
    return CommandHandler("start", start)
