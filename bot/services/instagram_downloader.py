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
    
    # 1) 'media' maydonida ro'yxat
    media = data.get("media")
    if isinstance(media, list):
        for item in media:
            if isinstance(item, dict) and "url" in item:
                url = item["url"]
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    media_urls.append(url)
                else:
                    logger.warning(f"Invalid media URL format: {url}")
    
    # 2) To'g'ridan-to'g'ri 'url' maydoni
    if not media_urls and "url" in data:
        url = data["url"]
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            media_urls.append(url)
        else:
            logger.warning(f"Invalid direct URL format: {url}")
    
    # 3) Boshqa keng tarqalgan formatlar
    if not media_urls:
        # 'download_url', 'video_url', 'image_url' kabi maydonlar
        for field in ["download_url", "video_url", "image_url", "media_url"]:
            if field in data:
                url = data[field]
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    media_urls.append(url)
                    break
    
    if not media_urls:
        logger.warning(f"No valid media URLs found in response: {data}")
    
    return media_urls


async def fetch_instagram_media(instagram_url: str) -> List[str]:
    """RapidAPI orqali Instagram media link(lar)ini olish.

    Natija sifatida bevosita yuklab olinadigan URL'lar ro'yxati qaytariladi.
    Keshdan olishga harakat qiladi, agar topilmasa API dan so'raydi.
    """
    
    # Avval keshdan tekshirish
    cached_media = get_cached_media(instagram_url)
    if cached_media is not None:
        return cached_media

    settings = get_settings()

    headers = {
        "x-rapidapi-key": settings.rapidapi_key,
        "x-rapidapi-host": settings.rapidapi_host,
    }

    params = {"url": instagram_url}

    client = await get_http_client()
    try:
        response = await client.get(
            settings.rapidapi_url,
            headers=headers,
            params=params,
        )
        # raise_for_status 429 holatini ham HTTPStatusError sifatida ko'taradi
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            logger.warning(f"RapidAPI rate limit reached for URL: {instagram_url}")
            raise RateLimitError("RapidAPI rate limit reached") from exc
        # Boshqa HTTP status xatolari
        logger.error(f"HTTP error {exc.response.status_code if exc.response else 'unknown'} for URL: {instagram_url}")
        return []
    except httpx.HTTPError as exc:
        logger.error(f"Network error for URL {instagram_url}: {str(exc)}")
        return []

    try:
        data = response.json()
    except Exception as exc:
        logger.error(f"Failed to parse JSON response for URL {instagram_url}: {str(exc)}")
        return []
    
    # RapidAPI javobini validatsiya qilish
    try:
        media_urls = _validate_rapidapi_response(data)
    except Exception as exc:
        logger.error(f"Response validation error for URL {instagram_url}: {str(exc)}")
        return []

    # Natijani keshga saqlash (faqat muvaffaqiyatli bo'lsa)
    if media_urls:
        cache_media(instagram_url, media_urls)
    
    return media_urls
