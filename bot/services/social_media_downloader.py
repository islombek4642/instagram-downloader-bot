import logging
from typing import Any, Dict, List

import httpx

from ..config import get_settings
from .cache import get_cached_media, cache_media

logger = logging.getLogger(__name__)

# Global HTTP client connection pooling uchun
_http_client: httpx.AsyncClient | None = None


class RateLimitError(Exception):
    """RapidAPI limiti tugaganda ko'tariladigan istisno."""


class ValidationError(Exception):
    """RapidAPI javob validatsiyasi xatosi."""


async def get_http_client() -> httpx.AsyncClient:
    """HTTP client olish yoki yaratish (connection pooling)."""
    global _http_client
    
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=15,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
    
    return _http_client


async def close_http_client() -> None:
    """HTTP client ni yopish."""
    global _http_client
    
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


def _validate_rapidapi_response(data: Any) -> List[str]:
    """RapidAPI javobini validatsiya qilish va media URL'larini chiqarish."""
    if not isinstance(data, dict):
        logger.warning(f"Invalid response format: expected dict, got {type(data)}")
        return []
    
    media_urls: List[str] = []
    
    def _looks_like_media(u: str) -> bool:
        lowered = u.lower()
        return lowered.startswith(("http://", "https://")) and (
            lowered.endswith((".mp4", ".mov", ".mkv", ".webm", ".m4v"))
            or lowered.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
        )

    # 1) 'links' maydoni (Social Download All In One javoblarida keng tarqalgan)
    links = data.get("links")
    if isinstance(links, list):
        for item in links:
            if isinstance(item, dict):
                candidate = (
                    item.get("url")
                    or item.get("link")
                    or item.get("download_url")
                )
                if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                    media_urls.append(candidate)

    # 1b) Yuqori darajadagi 'medias' ro'yxati (video/audio obyektlari)
    if not media_urls:
        medias = data.get("medias")
        if isinstance(medias, list):
            def _is_audio_item(it: dict) -> bool:
                t = str(it.get("type", "")).lower()
                mime = str(it.get("mimeType", "")).lower()
                ext = str(it.get("extension", "")).lower()
                # Base detection
                audio = (
                    "audio" in mime or t == "audio" or ext in {"mp3", "m4a", "aac", "wav", "ogg"}
                )
                # If clearly video, override
                if "video" in t or ext in {"mp4", "mov", "webm", "mkv", "m4v"} or it.get("resolution"):
                    audio = False
                return audio

            # Itag/formatlarga ko'ra ustuvorlik: 18 (mp4+audio) > boshqa mp4 > boshqalar
            itag18: List[str] = []
            mp4_list: List[str] = []
            others: List[str] = []
            for item in medias:
                if isinstance(item, dict):
                    candidate = item.get("url") or item.get("download_url")
                    if not isinstance(candidate, str) or not candidate.startswith(("http://", "https://")):
                        continue
                    if _is_audio_item(item):
                        continue
                    itag_val = str(item.get("itag", "")).strip()
                    mime = str(item.get("mimeType", "")).lower()
                    ext = str(item.get("extension", "")).lower()
                    if itag_val == "18":
                        itag18.append(candidate)
                    elif "mp4" in mime or ext == "mp4":
                        mp4_list.append(candidate)
                    else:
                        others.append(candidate)
            media_urls.extend(itag18 + mp4_list + others)
            # Agar hali ham topilmasa, qolganlarini (audio, boshqalar) ham qo'shamiz
            if not media_urls:
                for item in medias:
                    if isinstance(item, dict):
                        candidate = item.get("url") or item.get("download_url")
                        if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                            media_urls.append(candidate)

    # 2) 'media' ro'yxati
    if not media_urls:
        media = data.get("media")
        if isinstance(media, list):
            for item in media:
                if isinstance(item, dict):
                    candidate = item.get("url") or item.get("download_url")
                    if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                        media_urls.append(candidate)

    # 3) 'result' yoki 'data' ichidagi strukturalar
    if not media_urls:
        container = data.get("result") or data.get("data")
        if isinstance(container, dict):
            # result/data -> links
            links2 = container.get("links") or container.get("medias")
            if isinstance(links2, list):
                for item in links2:
                    if isinstance(item, dict):
                        candidate = item.get("url") or item.get("link") or item.get("download_url")
                        if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                            media_urls.append(candidate)
            else:
                # result/data -> bevosita media url maydoni
                for field in ["download_url", "video_url", "image_url", "media_url", "url"]:
                    if field in container:
                        candidate = container[field]
                        if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                            media_urls.append(candidate)

        elif isinstance(container, list):
            for item in container:
                if isinstance(item, dict):
                    candidate = item.get("url") or item.get("link") or item.get("download_url")
                    if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                        media_urls.append(candidate)

    # 4) Fallback: to'g'ridan-to'g'ri 'url' (faqat u media faylga o'xshasa)
    if not media_urls and "url" in data:
        url = data["url"]
        if isinstance(url, str) and _looks_like_media(url):
            media_urls.append(url)
        else:
            logger.info("Top-level 'url' found but it doesn't look like a direct media file; ignoring.")
    
    if not media_urls:
        logger.warning(f"No valid media URLs found in response: {data}")
    
    return media_urls


def _extract_metadata(data: Any) -> Dict[str, Any]:
    """Extract meta fields like source, author, title, thumbnail, duration from API response."""
    meta: Dict[str, Any] = {}
    if not isinstance(data, dict):
        return meta

    def _pick(d: Dict[str, Any]) -> None:
        for k in ("source", "author", "title", "thumbnail", "duration"):
            v = d.get(k)
            if isinstance(v, (str, int, float)) and v != "":
                meta[k] = v

    _pick(data)
    if not meta:
        container = data.get("data") or data.get("result")
        if isinstance(container, dict):
            _pick(container)
    return meta


async def fetch_media(instagram_url: str) -> tuple[Dict[str, Any], List[str]]:
    """RapidAPI orqali Instagram media link(lar)ini olish.

    Natija sifatida bevosita yuklab olinadigan URL'lar ro'yxati qaytariladi.
    Keshdan olishga harakat qiladi, agar topilmasa API dan so'raydi.
    """
    
    # Avval keshdan tekshirish
    cached_media = get_cached_media(instagram_url)
    if cached_media is not None:
        # Cache faqat URL ro'yxatini saqlaydi; meta mavjud emas
        return {}, cached_media

    settings = get_settings()

    headers = {
        "x-rapidapi-key": settings.rapidapi_key,
        "x-rapidapi-host": settings.rapidapi_host,
        "Content-Type": "application/json",
    }

    data = {"url": instagram_url}

    client = await get_http_client()
    try:
        response = await client.post(
            settings.rapidapi_url,
            headers=headers,
            json=data,
        )
        # raise_for_status 429 holatini ham HTTPStatusError sifatida ko'taradi
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            logger.warning(f"RapidAPI rate limit reached for URL: {instagram_url}")
            raise RateLimitError("RapidAPI rate limit reached") from exc
        # Boshqa HTTP status xatolari
        logger.error(f"HTTP error {exc.response.status_code if exc.response else 'unknown'} for URL: {instagram_url}")
        return {}, []
    except httpx.HTTPError as exc:
        logger.error(f"Network error for URL {instagram_url}: {str(exc)}")
        return {}, []

    try:
        data = response.json()
    except Exception as exc:
        logger.error(f"Failed to parse JSON response for URL {instagram_url}: {str(exc)}")
        return {}, []
    
    # RapidAPI javobini validatsiya qilish
    try:
        meta = _extract_metadata(data)
        media_urls = _validate_rapidapi_response(data)
    except Exception as exc:
        logger.error(f"Response validation error for URL {instagram_url}: {str(exc)}")
        return {}, []

    # Natijani keshga saqlash (faqat muvaffaqiyatli bo'lsa)
    if media_urls:
        cache_media(instagram_url, media_urls)
    
    return meta, media_urls
