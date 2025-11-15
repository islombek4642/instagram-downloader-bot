import logging
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import MessageHandler, ContextTypes, filters

from ..config import get_settings
from ..db.database import log_download
from ..services.instagram_downloader import RateLimitError, fetch_instagram_media

logger = logging.getLogger(__name__)


def _is_instagram_url(text: str) -> bool:
    lowered = text.lower()
    return "instagram.com" in lowered


def _guess_media_type(media_url: str) -> str:
    path = urlparse(media_url).path.lower()
    if path.endswith((".mp4", ".mov", ".mkv", ".webm")):
        return "video"
    if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return "photo"
    return "file"


async def _check_file_size(media_url: str, max_size_mb: int = 50) -> tuple[bool, int]:
    """File hajmini tekshirish. Returns (is_valid, size_mb)"""
    try:
        from ..services.instagram_downloader import get_http_client
        client = await get_http_client()
        
        # HEAD request bilan file hajmini olish
        response = await client.head(media_url, timeout=10)
        
        if response.status_code == 200:
            content_length = response.headers.get('content-length')
            if content_length:
                size_bytes = int(content_length)
                size_mb = size_bytes / (1024 * 1024)  # MB ga aylantirish
                return size_mb <= max_size_mb, int(size_mb)
        
        # Agar content-length yo'q bo'lsa, kichik deb hisoblaymiz
        return True, 0
    except Exception as exc:
        logger.warning(f"Could not check file size for {media_url}: {str(exc)}")
        # Xato bo'lsa, file ni yuklashga ruxsat beramiz
        return True, 0


async def handle_instagram_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    url = update.message.text.strip()

    if not _is_instagram_url(url):
        await update.message.reply_text(
            "❗ Iltimos, faqat Instagram post yoki reels linkini yuboring (instagram.com/... )."
        )
        log_download(chat_id=chat_id, instagram_url=url, status="invalid_url", error_message="not_instagram")
        return

    # Progress indicator
    progress_message = await update.message.reply_text("🔄 Instagram'dan media yuklanmoqda...")
    await update.message.chat.send_action(action="upload_document")

    try:
        # Progress indicator yangilash
        await progress_message.edit_text("🔍 Media URL'lari qidirilmoqda...")
        media_urls = await fetch_instagram_media(url)
    except RateLimitError as exc:
        log_download(chat_id=chat_id, instagram_url=url, status="rate_limit", error_message=str(exc))

        await update.message.reply_text(
            "⏱ API limiti vaqtincha tugadi. Iltimos, birozdan so'ng qayta urinib ko'ring."
        )

        settings = get_settings()
        if settings.admin_chat_id is not None:
            # Adminga texnik xabar
            try:
                await context.bot.send_message(
                    chat_id=settings.admin_chat_id,
                    text=(
                        "⚠️ RapidAPI rate limit tugadi.\n\n"
                        f"User chat_id: {chat_id}\n"
                        f"URL: {url}"
                    ),
                )
            except Exception:
                # Admin'ga xabar yuborishda xato bo'lsa, foydalanuvchi uchun muhim emas
                pass

        return
    except Exception as exc:
        log_download(chat_id=chat_id, instagram_url=url, status="error", error_message=str(exc))
        await update.message.reply_text(
            "⚠️ Serverda kutilmagan xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."
        )
        return

    if not media_urls:
        log_download(chat_id=chat_id, instagram_url=url, status="no_media", error_message="empty_result")
        await progress_message.edit_text(
            "🔍 Media topilmadi yoki link noto'g'ri. Iltimos, linkni tekshirib qayta yuboring."
        )
        return
    
    # Progress indicator: Media topildi
    await progress_message.edit_text(f"✅ {len(media_urls)} ta media topildi. Yuborilmoqda...")

    sent_any = False

    for index, media_url in enumerate(media_urls, start=1):
        media_type = _guess_media_type(media_url)
        
        # File hajmini tekshirish
        is_size_ok, file_size_mb = await _check_file_size(media_url)
        if not is_size_ok:
            logger.warning(f"File too large ({file_size_mb}MB) for chat_id={chat_id}, url={media_url}")
            await update.message.reply_text(
                f"⚠️ {index}-fayl juda katta ({file_size_mb}MB). "
                f"Telegram 50MB dan katta fayllarni qabul qilmaydi."
            )
            continue

        caption_lines = []
        if media_type == "video":
            caption_lines.append("🎬 Video")
        elif media_type == "photo":
            caption_lines.append("🖼 Rasm")
        else:
            caption_lines.append("📎 Fayl")

        if len(media_urls) > 1:
            caption_lines.append(f"(fayl {index}/{len(media_urls)})")

        caption_lines.append("")
        caption_lines.append(f"🔗 Asl post: {url}")

        caption = "\n".join(caption_lines)

        try:
            if media_type == "video":
                await update.message.reply_video(video=media_url, caption=caption)
            elif media_type == "photo":
                await update.message.reply_photo(photo=media_url, caption=caption)
            else:
                await update.message.reply_document(document=media_url, caption=caption)
            sent_any = True
            logger.info(f"Successfully sent {media_type} to chat_id={chat_id}, url={media_url}")
        except Exception as exc:
            logger.error(
                f"Failed to send {media_type} to chat_id={chat_id}, "
                f"media_url={media_url}, error={str(exc)}"
            )
            continue

    # Progress indicator o'chirish
    try:
        await progress_message.delete()
    except Exception:
        pass  # Agar o'chirib bo'lmasa, muhim emas
    
    if sent_any:
        # Media turlari va hajmlarini to'plash
        media_types_list = []
        file_sizes_list = []
        
        for media_url in media_urls:
            media_type = _guess_media_type(media_url)
            media_types_list.append(media_type)
            
            # File hajmini olishga harakat qilish
            try:
                _, file_size = await _check_file_size(media_url)
                file_sizes_list.append(str(file_size))
            except Exception:
                file_sizes_list.append("0")
        
        log_download(
            chat_id=chat_id,
            instagram_url=url,
            status="success",
            media_count=len(media_urls),
            media_types=",".join(media_types_list),
            file_sizes_mb=",".join(file_sizes_list),
        )
    else:
        log_download(chat_id=chat_id, instagram_url=url, status="error", error_message="send_failed")
        await update.message.reply_text(
            "⚠️ Media topildi, lekin Telegram orqali yuborishda xatolik yuz berdi. Keyinroq qayta urinib ko'ring."
        )


def get_download_handler() -> MessageHandler:
    return MessageHandler(filters.TEXT & ~filters.COMMAND, handle_instagram_link)
