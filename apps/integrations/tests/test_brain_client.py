"""Tests for Brain API client (mocked HTTP)."""

from unittest.mock import MagicMock, patch


class TestBrainAPIClient:
    """Unit tests for BrainAPIClient — all HTTP calls are mocked."""

    def _make_client(self, MockClient: MagicMock) -> "BrainAPIClient":  # type: ignore[name-defined]
        from apps.integrations.brain.client import BrainAPIClient

        client = BrainAPIClient()
        client._http = MockClient
        return client

    # ── Auth ─────────────────────────────────────────────────────────────────

    def test_auth_caches_sid(self):
        from apps.integrations.brain.client import BrainAPIClient, _SID_CACHE_KEY

        mock_http = MagicMock()
        mock_http.post.return_value.json.return_value = {"status": 1, "result": "test-sid-abc"}
        mock_http.post.return_value.raise_for_status = MagicMock()

        with patch("apps.integrations.brain.client.cache") as mock_cache:
            mock_cache.get.return_value = None  # no cached SID
            with patch("django.conf.settings") as mock_settings:
                mock_settings.BRAIN_LOGIN = "user@test.com"
                mock_settings.BRAIN_PASSWORD = "secret"
                client = BrainAPIClient()
                client._http = mock_http
                sid = client._auth()

        assert sid == "test-sid-abc"
        mock_cache.set.assert_called_once_with(_SID_CACHE_KEY, "test-sid-abc", 23 * 3600)

    # ── Categories ──────────────────────────────────────────────────────────

    def test_get_all_categories_returns_list(self):
        from apps.integrations.brain.client import BrainAPIClient

        cats = [
            {"categoryID": 1, "parentID": 1, "realcat": 0, "name": "Ноутбуки"},
            {"categoryID": 2, "parentID": 1, "realcat": 0, "name": "ПК"},
        ]
        mock_http = MagicMock()
        mock_http.get.return_value.json.return_value = {"status": 1, "result": cats}
        mock_http.get.return_value.raise_for_status = MagicMock()

        with patch("apps.integrations.brain.client.cache") as mock_cache:
            mock_cache.get.side_effect = lambda k: "cached-sid" if "sid" in k else None
            with patch("django.conf.settings") as mock_settings:
                mock_settings.BRAIN_LOGIN = "u"
                mock_settings.BRAIN_PASSWORD = "p"
                client = BrainAPIClient()
                client._http = mock_http
                result = client.get_all_categories()

        assert isinstance(result, list)
        assert len(result) == 2

    # ── Products ─────────────────────────────────────────────────────────────

    def test_get_products_returns_tuple(self):
        from apps.integrations.brain.client import BrainAPIClient

        product_list = [{"productID": 100, "name": "Laptop", "price_uah": "30000", "is_archive": 0}]
        mock_http = MagicMock()
        mock_http.get.return_value.json.return_value = {
            "status": 1,
            "result": {"list": product_list, "count": 1},
        }
        mock_http.get.return_value.raise_for_status = MagicMock()

        with patch("apps.integrations.brain.client.cache") as mock_cache:
            mock_cache.get.side_effect = lambda k: "cached-sid" if "sid" in k else None
            with patch("django.conf.settings") as mock_settings:
                mock_settings.BRAIN_LOGIN = "u"
                mock_settings.BRAIN_PASSWORD = "p"
                client = BrainAPIClient()
                client._http = mock_http
                items, total = client.get_products(category_id=1181)

        assert isinstance(items, list)
        assert total == 1

    # ── Modified products ─────────────────────────────────────────────────────

    def test_get_modified_since_returns_id_list(self):
        from apps.integrations.brain.client import BrainAPIClient

        mock_http = MagicMock()
        mock_http.get.return_value.json.return_value = {
            "status": 1,
            "result": {"productIDs": [10, 20, 30], "count": 3, "current": "2026-05-19 12:00:00"},
        }
        mock_http.get.return_value.raise_for_status = MagicMock()

        with patch("apps.integrations.brain.client.cache") as mock_cache:
            mock_cache.get.side_effect = lambda k: "cached-sid" if "sid" in k else None
            with patch("django.conf.settings") as mock_settings:
                mock_settings.BRAIN_LOGIN = "u"
                mock_settings.BRAIN_PASSWORD = "p"
                client = BrainAPIClient()
                client._http = mock_http
                ids = client.get_modified_since("2026-05-19 07:00:00")

        assert ids == [10, 20, 30]

    # ── Products content (OWN_MODE) ───────────────────────────────────────────

    def test_get_products_content_batches_post(self):
        from apps.integrations.brain.client import BrainAPIClient

        items = [
            {"productID": 100, "description": "Повний опис ноутбука"},
            {"productID": 101, "description": "Опис монітора"},
        ]
        mock_http = MagicMock()
        mock_http.post.return_value.json.return_value = {
            "status": 1,
            "result": {"list": items, "count": 2},
        }
        mock_http.post.return_value.raise_for_status = MagicMock()

        with patch("apps.integrations.brain.client.cache") as mock_cache:
            mock_cache.get.side_effect = lambda k: "cached-sid" if "sid" in k else None
            with patch("django.conf.settings") as mock_settings:
                mock_settings.BRAIN_LOGIN = "u"
                mock_settings.BRAIN_PASSWORD = "p"
                mock_settings.BRAIN_CONTENT_BATCH_SIZE = 50
                client = BrainAPIClient()
                client._http = mock_http
                result = client.get_products_content([100, 101], lang="ua")

        assert len(result) == 2
        assert result[0]["description"] == "Повний опис ноутбука"
        mock_http.post.assert_called_once()
        call_kwargs = mock_http.post.call_args
        assert call_kwargs[1]["data"]["productIDs"] == "100,101"
        assert call_kwargs[1]["data"]["lang"] == "ua"
