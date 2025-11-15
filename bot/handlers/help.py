from telegram import Update
from telegram.ext import CommandHandler, ContextTypes


HELP_TEXT = (
    "ℹ️ *Instagram Downloader bot yo'riqnomasi*\n\n"
    "Men Instagram'dan video va rasmlarni yuklab beradigan botman.\n\n"
    "✅ *Qanday ishlaydi?*\n"
    "1️⃣ /start buyrug'ini yuboring.\n"
    "2️⃣ Instagram'dagi post/reels/story linkini yuboring.\n"
    "3️⃣ Men media fayl(lar)ni sizga qaytaraman.\n\n"
    "📌 *Eslatma:* faqat ochiq (public) profillardan olingan postlar bilan yaxshiroq ishlaydi."
)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode='Markdown')


def get_help_handler() -> CommandHandler:
    return CommandHandler("help", help_command)
