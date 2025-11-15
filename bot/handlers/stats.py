import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from ..config import get_settings
from ..db.database import get_connection, get_detailed_stats

logger = logging.getLogger(__name__)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    chat_id = update.effective_chat.id

    if settings.admin_chat_id is not None and settings.admin_chat_id != chat_id:
        await update.message.reply_text("⛔ Bu buyruq faqat admin uchun.")
        logger.info("/stats denied for chat_id=%s", chat_id)
        return

    stats = get_detailed_stats()
    
    text_lines = [
        "📊 *Bot statistikasi*\n",
        f"👥 Foydalanuvchilar: {stats['users_count']}",
        f"⬇️ Yuklashlar (jami): {stats['downloads_count']}",
        f"✅ Muvaffaqiyatli: {stats['success_count']} ({stats['success_rate']}%)\n",
    ]
    
    # Media turlari statistikasi
    if stats['media_types_stats']:
        text_lines.append("📋 *Eng ko'p yuklanadigan turlar:*")
        for media_type, count in stats['media_types_stats'][:5]:
            text_lines.append(f"• {media_type}: {count} marta")
        text_lines.append("")
    
    # Oxirgi kunlardagi faollik
    if stats['daily_activity']:
        text_lines.append("📈 *Oxirgi 7 kun:*")
        for day, count in stats['daily_activity'][:5]:
            text_lines.append(f"• {day}: {count} yuklash")
    
    text = "\n".join(text_lines)

    await update.message.reply_text(text, parse_mode='Markdown')
    logger.info("/stats shown to chat_id=%s", chat_id)


def get_stats_handler() -> CommandHandler:
    return CommandHandler("stats", stats)
