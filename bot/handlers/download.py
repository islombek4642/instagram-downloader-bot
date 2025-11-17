import logging
from urllib.parse import urlparse, parse_qs, urljoin

import io
from telegram import Update, InputFile
from telegram.ext import MessageHandler, ContextTypes, filters

from ..config import get_settings
from ..db.database import log_download
from ..services.social_media_downloader import fetch_media, RateLimitError, get_http_client

logger = logging.getLogger(__name__)


def _is_supported_url(text: str) -> bool:
    try:
        u = urlparse(text)
        return u.scheme in ("http", "https") and bool(u.netloc)
    except Exception:
        return False


def _guess_media_type(media_url: str) -> str:
    parsed = urlparse(media_url)
    path = parsed.path.lower()
    if path.endswith((".mp4", ".mov", ".mkv", ".webm", ".m4v")):
        return "video"
    if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return "photo"
    # YouTube/GoogleVideo style: mime=video/* yoki image/* query parametrlari
    try:
        q = parse_qs(parsed.query)
        mime = (q.get("mime", [""])[0] or "").lower()
        if mime.startswith("video/"):
            return "video"
        if mime.startswith("image/"):
            return "photo"
    except Exception:
        pass
    return "file"


async def _check_file_size(media_url: str, max_size_mb: int = 50) -> tuple[bool, int]:
    """File hajmini tekshirish. Returns (is_valid, size_mb)"""
    try:
        client = await get_http_client()
        
        # YouTube/GoogleVideo linklarida 'clen' query parametresi mavjud bo'ladi
        try:
            q = parse_qs(urlparse(media_url).query)
            clen = q.get("clen", [None])[0]
            if clen and clen.isdigit():
                size_bytes = int(clen)
                size_mb = size_bytes / (1024 * 1024)
                return size_mb <= max_size_mb, int(size_mb)
        except Exception:
            pass

        # HEAD request bilan file hajmini olish (redirectlarni kuzatish bilan)
        ua = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        }
        response = await client.head(media_url, timeout=20, follow_redirects=True, headers=ua)
        if response.status_code == 200:
            content_length = response.headers.get("content-length")
            if content_length and content_length.isdigit():
                size_bytes = int(content_length)
                size_mb = size_bytes / (1024 * 1024)
                return size_mb <= max_size_mb, int(size_mb)

        # Agar Content-Length yo'q bo'lsa, Range GET orqali umumiy hajmni bilishga urinamiz
        try:
            range_headers = {**ua, "Range": "bytes=0-0"}
            r = await client.get(media_url, timeout=20, follow_redirects=True, headers=range_headers)
            if r.status_code in (200, 206):
                content_range = r.headers.get("Content-Range")
                # Format: bytes 0-0/123456
                if content_range and "/" in content_range:
                    total = content_range.split("/")[-1].strip()
                    if total.isdigit():
                        size_bytes = int(total)
                        size_mb = size_bytes / (1024 * 1024)
                        return size_mb <= max_size_mb, int(size_mb)
        except Exception:
            pass

        # Hajmni aniqlab bo'lmadi -> xavfsizlik uchun jo'natmaslik
        return False, 0
    except Exception as exc:
        logger.warning(f"Could not check file size for {media_url}: {str(exc)}")
        # Xato bo'lsa, file ni yuklashga ruxsat beramiz
        return True, 0


async def _download_to_inputfile(media_url: str, media_type: str, max_size_mb: int = 50) -> InputFile | None:
    """Media faylni stream orqali yuklab, InputFile ko'rinishida qaytaradi."""
    try:
        client = await get_http_client()
        max_bytes = max_size_mb * 1024 * 1024
        # Ba'zi CDNlar uchun User-Agent talab qilinadi (masalan, googlevideo)
        ua = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        }
        # Manual redirect handling for streaming
        current_url = media_url
        for _ in range(3):
            async with client.stream("GET", current_url, timeout=120, headers=ua) as resp:
                if resp.status_code in (301, 302, 303, 307, 308):
                    loc = resp.headers.get("location") or resp.headers.get("Location")
                    if not loc:
                        break
                    # Relative Location uchun join
                    try:
                        current_url = urljoin(current_url, loc)
                    except Exception:
                        current_url = loc
                    continue
                resp.raise_for_status()
                buf = io.BytesIO()
                size = 0
                async for chunk in resp.aiter_bytes(8192):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        logger.warning(f"Downloaded content exceeds {max_size_mb}MB limit: {current_url}")
                        return None
                    buf.write(chunk)
                buf.seek(0)
                filename = "media.mp4" if media_type == "video" else ("image.jpg" if media_type == "photo" else "file.bin")
                return InputFile(buf, filename=filename)
        return None
    except Exception as exc:
        logger.warning(f"Stream download failed for {media_url}: {str(exc)}")
        return None


def _is_mp4(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.path.lower().endswith(".mp4"):
            return True
        q = parse_qs(parsed.query)
        mime = (q.get("mime", [""])[0] or "").lower()
        return mime.startswith("video/mp4")
    except Exception:
        return False


def _is_googlevideo(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return host == "redirector.googlevideo.com" or host.endswith(".googlevideo.com")
    except Exception:
        return False


async def _select_sendable_urls(urls: list[str], limit: int = 1, max_size_mb: int = 50) -> list[str]:
    candidates: list[tuple[int, int, int, str]] = []
    for u in urls:
        ok, size_mb = await _check_file_size(u, max_size_mb=max_size_mb)
        if not ok:
            logger.debug(f"[select] filtered out (too big/unknown): {u}")
            continue
        not_mp4 = 0 if _is_mp4(u) else 1
        # Prefer itag=18 for YouTube when present
        try:
            itag = (parse_qs(urlparse(u).query).get("itag", [""])[0] or "").strip()
        except Exception:
            itag = ""
        not_itag18 = 0 if itag == "18" else 1
        candidates.append((not_mp4, not_itag18, size_mb, u))
        logger.debug(f"[select] candidate size={size_mb}MB itag={itag or '-'} mp4={not_mp4==0}: {u}")
    candidates.sort()
    chosen = [u for *_, u in candidates[:limit]]
    if chosen:
        logger.debug(f"[select] chosen: {chosen}")
    else:
        logger.debug("[select] no candidates under size limit")
    return chosen


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    url = update.message.text.strip()
    settings = get_settings()

    if not _is_supported_url(url):
        await update.message.reply_text(
            "❗ Iltimos, ijtimoiy tarmoqdan to'g'ri link yuboring (https://...)."
        )
        log_download(chat_id=chat_id, media_url=url, status="invalid_url", error_message="not_instagram")
        return

    # Progress indicator
    progress_message = await update.message.reply_text("🔄 Media yuklanmoqda...")
    await update.message.chat.send_action(action="upload_document")

    try:
        # Progress indicator yangilash
        await progress_message.edit_text("🔍 Media URL'lari qidirilmoqda...")
        meta, media_urls = await fetch_media(url)
        logger.debug(f"[fetch] meta={meta} urls_count={len(media_urls)}")
    except RateLimitError as exc:
        log_download(chat_id=chat_id, media_url=url, status="rate_limit", error_message=str(exc))

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
        log_download(chat_id=chat_id, media_url=url, status="error", error_message=str(exc))
        await update.message.reply_text(
            "⚠️ Serverda kutilmagan xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."
        )
        return

    if not media_urls:
        log_download(chat_id=chat_id, media_url=url, status="no_media", error_message="empty_result")
        await progress_message.edit_text(
            "🔍 Media topilmadi yoki link noto'g'ri. Iltimos, linkni tekshirib qayta yuboring."
        )
        return
    
    # settings.max_send_mb dan kichik va MP4'ni afzal ko'rib eng yaxshi variant(lar)ni tanlash
    all_media_urls = list(media_urls)
    selected_urls = await _select_sendable_urls(media_urls, limit=1, max_size_mb=settings.max_send_mb)
    if not selected_urls:
        log_download(chat_id=chat_id, media_url=url, status="too_large_all", error_message="over_50mb")
        await progress_message.edit_text(
            f"⚠️ Bu media variantlari juda katta ({settings.max_send_mb}MB+). Qisqa link yoki past sifatli variantni yuboring."
        )
        # Katta fayllar uchun to'g'ridan-to'g'ri yuklab olish link(lar)i
        try:
            # Top 3 eng kichik variantlarni ko'rsatish (noma'lum hajmli linklarni ham qo'shamiz)
            sizes: list[tuple[int, str]] = []
            unknown: list[str] = []
            for u in media_urls:
                ok, sz = await _check_file_size(u, max_size_mb=10**9)
                if sz > 0:
                    sizes.append((sz, u))
                else:
                    unknown.append(u)
            sizes.sort()
            items: list[str] = [f"• {s}MB → {u}" for s, u in sizes[:3]]
            if len(items) < 3:
                for uu in unknown[: 3 - len(items)]:
                    items.append(f"• (hajm noma'lum) → {uu}")
            text = (
                "🔗 Katta fayl(lar) uchun to'g'ridan-to'g'ri yuklab olish linklari:\n" + ("\n".join(items) if items else "(hajmni aniqlab bo'lmadi)")
            )
            await update.message.reply_text(text)
            logger.debug(f"[fallback-links] provided {len(items)} links")
        except Exception:
            pass
        return
    media_urls = selected_urls
    await progress_message.edit_text(f"✅ {len(selected_urls)} ta media topildi. Yuborilmoqda...")

    sent_any = False

    for index, media_url in enumerate(media_urls, start=1):
        media_type = _guess_media_type(media_url)
        
        # File hajmini tekshirish
        is_size_ok, file_size_mb = await _check_file_size(media_url, max_size_mb=settings.max_send_mb)
        if not is_size_ok:
            logger.warning(f"File too large ({file_size_mb}MB) for chat_id={chat_id}, url={media_url}")
            await update.message.reply_text(
                f"⚠️ {index}-fayl juda katta ({file_size_mb}MB). "
                f"Telegram {settings.max_send_mb}MB dan katta fayllarni qabul qilmaydi."
            )
            continue

        caption_lines = []
        if media_type == "video":
            caption_lines.append("🎬 Video")
        elif media_type == "photo":
            caption_lines.append("🖼 Rasm")
        else:
            caption_lines.append("📎 Fayl")

        try:
            t = meta.get("title") if isinstance(meta, dict) else None
            if t:
                caption_lines.append(f"📝 {t}")
            a = meta.get("author") if isinstance(meta, dict) else None
            if a:
                caption_lines.append(f"👤 {a}")
        except Exception:
            pass

        if len(media_urls) > 1:
            caption_lines.append(f"(fayl {index}/{len(media_urls)})")

        caption_lines.append("")
        caption_lines.append(f"🔗 Asl post: {url}")

        caption = "\n".join(caption_lines)

        try:
            if media_type == "video":
                # googlevideo linklarida Telegram ko'pincha to'g'ridan-to'g'ri URL'dan yuklay olmaydi
                if _is_googlevideo(media_url):
                    logger.debug("[send] googlevideo detected, using streaming upload")
                    input_file = await _download_to_inputfile(media_url, media_type, max_size_mb=settings.max_send_mb)
                    if input_file is None:
                        raise Exception("streaming_unavailable_or_too_large")
                    await update.message.reply_video(video=input_file, caption=caption)
                else:
                    logger.debug("[send] direct video url path")
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
            # Fallback: faylni yuklab, InputFile sifatida yuborish
            try:
                input_file = await _download_to_inputfile(media_url, media_type)
                if input_file is not None:
                    if media_type == "video":
                        await update.message.reply_video(video=input_file, caption=caption)
                    elif media_type == "photo":
                        await update.message.reply_photo(photo=input_file, caption=caption)
                    else:
                        await update.message.reply_document(document=input_file, caption=caption)
                    sent_any = True
                    logger.info(f"Fallback upload succeeded for chat_id={chat_id}, url={media_url}")
                    continue
            except Exception as exc2:
                logger.error(
                    f"Fallback upload failed for chat_id={chat_id}, url={media_url}, error={str(exc2)}"
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
            media_url=url,
            status="success",
            media_count=len(media_urls),
            media_types=",".join(media_types_list),
            file_sizes_mb=",".join(file_sizes_list),
        )
    else:
        log_download(chat_id=chat_id, media_url=url, status="error", error_message="send_failed")
        await update.message.reply_text(
            "⚠️ Media topildi, lekin Telegram orqali yuborishda xatolik yuz berdi. Keyinroq qayta urinib ko'ring."
        )
        # Fallback sifatida to'g'ridan-to'g'ri yuklab olish linklarini yuborish
        try:
            sizes: list[tuple[int, str]] = []
            unknown: list[str] = []
            for u in all_media_urls:
                ok, sz = await _check_file_size(u, max_size_mb=10**9)
                if sz > 0:
                    sizes.append((sz, u))
                else:
                    unknown.append(u)
            sizes.sort()
            items: list[str] = [f"• {s}MB → {u}" for s, u in sizes[:3]]
            if len(items) < 3:
                for uu in unknown[: 3 - len(items)]:
                    items.append(f"• (hajm noma'lum) → {uu}")
            if items:
                await update.message.reply_text(
                    "🔗 To'g'ridan-to'g'ri yuklab olish linklari:\n" + "\n".join(items)
                )
        except Exception:
            pass


def get_download_handler() -> MessageHandler:
    return MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)
