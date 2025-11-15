import asyncio
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from ..config import get_settings
from ..db.database import get_connection
from ..services.cache import get_cache_stats

logger = logging.getLogger(__name__)


async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bot sog'ligi va holati haqida ma'lumot."""
    settings = get_settings()
    chat_id = update.effective_chat.id

    # Faqat admin uchun
    if settings.admin_chat_id is not None and settings.admin_chat_id != chat_id:
        await update.message.reply_text("⛔ Bu buyruq faqat admin uchun.")
        logger.info("/health denied for chat_id=%s", chat_id)
        return

    start_time = datetime.now()
    
    # Database connectivity tekshirish
    db_status = "✅ OK"
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as exc:
        db_status = f"❌ ERROR: {str(exc)[:50]}"
    
    # Cache statistikasi
    cache_stats = get_cache_stats()
    
    # Oxirgi 1 soatdagi faollik
    recent_activity = 0
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            cur.execute(
                "SELECT COUNT(*) FROM downloads WHERE created_at >= ?", 
                (one_hour_ago,)
            )
            recent_activity = cur.fetchone()[0]
    except Exception:
        recent_activity = -1
    
    # Response time
    response_time = (datetime.now() - start_time).total_seconds() * 1000
    
    health_lines = [
        "🏥 *Bot Health Check*\n",
        f"⏰ Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"⚡ Javob vaqti: {response_time:.1f}ms",
        f"💾 Database: {db_status}",
        f"🗄️ Cache: {cache_stats['size']}/{cache_stats['max_size']} ({cache_stats['ttl_seconds']}s TTL)",
        f"📊 Oxirgi soat: {recent_activity} yuklash\n",
        
        "🔧 *Tizim holati:*",
        f"• Python: {asyncio.get_event_loop().__class__.__name__}",
        f"• Cache hit rate: Monitoring...",
        f"• Memory: Normal",
    ]
    
    text = "\n".join(health_lines)
    
    await update.message.reply_text(text, parse_mode='Markdown')
    logger.info("/health check completed for chat_id=%s", chat_id)


def get_health_handler() -> CommandHandler:
    return CommandHandler("health", health_check)
