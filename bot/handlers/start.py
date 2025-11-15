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
        "Men Instagram'dan video va rasmlarni yuklab beradigan botman.\n\n"
        "📝 Foydalanish:\n"
        "1️⃣ Instagram post yoki reels linkini yuboring.\n"
        "2️⃣ Men media fayl(lar)ni sizga qaytaraman.\n\n"
        "Misol link:\n"
        "https://www.instagram.com/p/XXXXXXXXXXX/\n\n"
        "ℹ️ Qo'shimcha ma'lumot uchun /help buyrug'ini yuboring."
    )

    await update.message.reply_text(text, reply_markup=get_main_menu_keyboard())


def get_start_handler() -> CommandHandler:
    return CommandHandler("start", start)
