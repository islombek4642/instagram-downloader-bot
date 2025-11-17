from telegram import Update
from telegram.ext import CommandHandler, ContextTypes


HELP_TEXT = (
    "ℹ️ *Social Media Downloader yo'riqnomasi*\n\n"
    "Men Instagram, YouTube, TikTok va boshqa ijtimoiy tarmoqlardan media yuklab beraman.\n\n"
    "✅ *Qanday ishlaydi?*\n"
    "1️⃣ /start buyrug'ini yuboring.\n"
    "2️⃣ Ijtimoiy tarmoqdagi post/reels/video linkini yuboring.\n"
    "3️⃣ Men media fayl(lar)ni sizga qaytaraman.\n\n"
    "📌 *Cheklov:* Telegram botlari odatda ~50MB gacha fayllarni qabul qiladi. Katta fayllar uchun to'g'ridan-to'g'ri yuklab olish linkini yuboraman."
)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode='Markdown')


def get_help_handler() -> CommandHandler:
    return CommandHandler("help", help_command)
