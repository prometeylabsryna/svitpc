"""Brain API client — api.brain.com.ua (session-based auth).

URL format: /endpoint/{SID}  or  /endpoint/{param}/{SID}
Auth:       POST /auth  →  {"login": ..., "password": md5(pwd)}  →  SID cached in Redis.
Docs:       https://api.brain.com.ua/help
"""

from __future__ import annotations

import hashlib
import json
import logging
import time

import httpx
from django.core.cache import cache

logger = logging.getLogger(__name__)
BASE_URL = "https://api.brain.com.ua"

# Brain API: max 3 requests/sec (error 115 → HTTP 429)
_RATE_INTERVAL_SEC = 0.35
_LAST_REQUEST_AT = 0.0

# Cache TTLs
_SID_CACHE_KEY = "brain:sid"
_SID_TTL = 23 * 3600          # sessions last ~24 h
_TTL_CATALOG = 60 * 60        # 1 h  — categories, vendors
_TTL_PRODUCTS = 60 * 15       # 15 min — product lists
_TTL_PRODUCT = 60 * 5         # 5 min  — single product, price, stock
_TTL_CONTENT = 60 * 30        # 30 min — options, images

# Brain API error codes that mean "session expired / invalid"
_SESSION_ERRORS = {2, 3, 4, 14}


def products_page_limit() -> int:
    """Brain page size: 100 without OWN_MODE, up to 1000 with OWN_MODE."""
    from django.conf import settings

    raw = int(getattr(settings, "BRAIN_PRODUCTS_PAGE_LIMIT", 100))
    return max(100, min(raw, 1000))


def _throttle_brain_request() -> None:
    global _LAST_REQUEST_AT
    now = time.monotonic()
    wait = _RATE_INTERVAL_SEC - (now - _LAST_REQUEST_AT)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_AT = time.monotonic()


class BrainAPIClient:
    def __init__(self) -> None:
        from django.conf import settings
        self._login: str = settings.BRAIN_LOGIN
        self._password: str = settings.BRAIN_PASSWORD
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={"Accept": "application/json"},
            timeout=30,
        )

    # ── Auth ─────────────────────────────────────────────────────────────────────

    def _auth(self) -> str:
        """Authenticate and cache the SID."""
        pwd_md5 = hashlib.md5(self._password.encode()).hexdigest()
        resp = self._http.post("/auth", data={"login": self._login, "password": pwd_md5})
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != 1:
            raise RuntimeError(f"Brain auth failed: {body}")
        sid: str = body["result"]
        cache.set(_SID_CACHE_KEY, sid, _SID_TTL)
        logger.info("Brain API: new session obtained")
        return sid

    def _sid(self) -> str:
        return cache.get(_SID_CACHE_KEY) or self._auth()

    def invalidate_session(self) -> None:
        cache.delete(_SID_CACHE_KEY)

    # ── Low-level request ────────────────────────────────────────────────────────

    def _cache_key(self, path: str, params: dict | None) -> str:
        raw = json.dumps({"p": path, "q": sorted((params or {}).items())}, sort_keys=True)
        return f"brain:{hashlib.md5(raw.encode()).hexdigest()}"

    def _get(
        self,
        path_tpl: str,
        params: dict | None = None,
        cache_ttl: int = _TTL_CATALOG,
        *,
        _retry: bool = True,
        **path_kwargs: object,
    ) -> dict | list | None:
        """GET request with SID injected into path_tpl via {sid} placeholder.

        path_tpl examples:
            "/categories/{sid}"
            "/products/{cat_id}/{sid}"
            "/product/{pid}/{sid}"
        """
        sid = self._sid()
        path = path_tpl.format(sid=sid, **path_kwargs)
        ckey = self._cache_key(path, params)

        if (hit := cache.get(ckey)) is not None:
            return hit

        last_exc: Exception | None = None
        for attempt in range(6):
            _throttle_brain_request()
            try:
                resp = self._http.get(path, params=params or {})
                if resp.status_code == 429:
                    delay = 1.0 * (attempt + 1)
                    logger.warning("Brain API rate limit %s, retry in %.1fs", path, delay)
                    time.sleep(delay)
                    continue
                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, dict) and data.get("status") == 0:
                    if _retry and data.get("error_code") in _SESSION_ERRORS:
                        cache.delete(_SID_CACHE_KEY)
                        return self._get(path_tpl, params, cache_ttl, _retry=False, **path_kwargs)
                    logger.warning("Brain API %s → %s", path, data.get("error_message"))
                    return None

                result = data.get("result") if isinstance(data, dict) and "result" in data else data
                if result is not None:
                    cache.set(ckey, result, cache_ttl)
                return result
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code == 429 and attempt < 5:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                logger.error("Brain API request failed [%s]: %s", path_tpl, exc)
                return None
            except Exception as exc:
                last_exc = exc
                logger.error("Brain API request failed [%s]: %s", path_tpl, exc)
                return None

        if last_exc is not None:
            logger.error("Brain API request failed after retries [%s]: %s", path_tpl, last_exc)
        return None

    # ── Categories ───────────────────────────────────────────────────────────────

    def get_all_categories(self, lang: str = "ua") -> list[dict]:
        """Return flat list of all Brain categories.

        Each item: {categoryID, parentID, realcat, name}
        parentID=1  → top-level category.
        realcat > 0 → virtual category (alias of realcat category).
        """
        data = self._get("/categories/{sid}", {"lang": lang}, cache_ttl=_TTL_CATALOG)
        return data if isinstance(data, list) else []

    # ── Vendors (brands) ─────────────────────────────────────────────────────────

    def get_all_vendors(self) -> dict[int, str]:
        """Return {vendorID: name} mapping for all vendors."""
        data = self._get("/vendors/{sid}", cache_ttl=_TTL_CATALOG)
        vendors: dict[int, str] = {}
        if isinstance(data, list):
            for v in data:
                vid = v.get("vendorID")
                name = (v.get("name") or "").strip()
                if vid and name:
                    vendors[int(vid)] = name
        return vendors

    # ── Products ─────────────────────────────────────────────────────────────────

    def get_products(
        self,
        category_id: int,
        offset: int = 0,
        limit: int | None = None,
        lang: str = "ua",
    ) -> tuple[list[dict], int]:
        """Return (product list, total count) for a category (includes all sub-categories)."""
        page_limit = limit if limit is not None else products_page_limit()
        data = self._get(
            "/products/{cat_id}/{sid}",
            {
                "offset": offset,
                "limit": page_limit,
                "lang": lang,
                "sortby": "productID",
                "order": "asc",
            },
            cache_ttl=_TTL_PRODUCTS,
            cat_id=category_id,
        )
        if isinstance(data, dict):
            return data.get("list", []), int(data.get("count", 0))
        return [], 0

    def get_product(self, product_id: int, lang: str = "ua") -> dict | None:
        """Single product details including price_uah, is_archive, options."""
        return self._get(
            "/product/{pid}/{sid}",
            {"lang": lang},
            cache_ttl=_TTL_PRODUCT,
            pid=product_id,
        )

    # ── Options & Images ─────────────────────────────────────────────────────────

    def get_product_options(self, product_id: int, lang: str = "ua") -> list[dict]:
        """Return list of {OptionID, OptionName, ValueID, ValueName, FilterID, FilterName}."""
        data = self._get(
            "/product_options/{pid}/{sid}",
            {"lang": lang},
            cache_ttl=_TTL_CONTENT,
            pid=product_id,
        )
        return data if isinstance(data, list) else []

    def get_product_pictures(self, product_id: int) -> list[dict]:
        """Return list of {priority, small_image, medium_image, large_image, full_image}."""
        data = self._get(
            "/product_pictures/{pid}/{sid}",
            cache_ttl=_TTL_CONTENT,
            pid=product_id,
        )
        return data if isinstance(data, list) else []

    # ── Modified products ────────────────────────────────────────────────────────

    def get_report(
        self,
        report_type: str,
        *,
        date_from: str = "",
        date_to: str = "",
        file_type: str = "xls",
        order_id: str = "",
    ) -> bytes | str | None:
        """Fetch Brain dealer report (e.g. serial_numbers_by_dealer).

        Dates use DD.MM.YYYY. Rate limit: one request per report type per 300s.
        Returns raw response body (XLS bytes or HTML text).
        """
        params: dict[str, str] = {}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if file_type:
            params["file_type"] = file_type
        if order_id:
            params["orderID"] = order_id
        sid = self._sid()
        path = f"/report/{report_type}/{sid}"
        try:
            resp = self._http.get(path, params=params or {})
            resp.raise_for_status()
            content_type = (resp.headers.get("content-type") or "").lower()
            if "json" in content_type:
                data = resp.json()
                if isinstance(data, dict) and data.get("status") == 0:
                    logger.warning("Brain report %s → %s", report_type, data.get("error_message"))
                    return None
                result = data.get("result") if isinstance(data, dict) else data
                if isinstance(result, str):
                    return result.encode()
                return None
            return resp.content
        except Exception as exc:
            logger.error("Brain report request failed [%s]: %s", report_type, exc)
            return None

    def get_modified_since(
        self,
        modified_time: str,
        limit: int = 10000,
        mod_type: str = "",
    ) -> list[int]:
        """Return Brain productIDs modified after modified_time ('YYYY-MM-DD HH:MM:SS').

        mod_type: '' (any change) | 'options' | 'images' | 'descriptions' | 'new'
        Minimum limit is 100 per Brain API constraint.
        """
        effective_limit = max(limit, 100)
        # URL: /modified_products/{type}/{SID} — type is optional path segment
        path_tpl = f"/modified_products/{mod_type}/{{sid}}" if mod_type else "/modified_products/{sid}"
        data = self._get(
            path_tpl,
            {"modified_time": modified_time, "limit": effective_limit},
            cache_ttl=60,  # 1 min — volatile
        )
        if isinstance(data, dict):
            return [int(i) for i in data.get("productIDs", [])]
        return []
