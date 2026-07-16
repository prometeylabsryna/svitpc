"""Light/denne Brain-задачі не повинні писати Product одночасно з важким
нічним синком (окремий celery-воркер працює паралельно з light-воркером)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.cache import cache

from apps.integrations.heavy_sync import LOCK_KEY, is_heavy_sync_running, skip_if_heavy_sync_running


@pytest.fixture(autouse=True)
def _clear_heavy_lock():
    cache.delete(LOCK_KEY)
    yield
    cache.delete(LOCK_KEY)


class TestConfigurableTimeLimits:
    """soft_time_limit читається з Django settings (env-конфігуровано) — ops
    можуть підняти ліміт без релізу коду, якщо реальний нічний прогін довший
    за дефолт (не вгадуючи заново тривалість у Python-константі)."""

    def test_brain_time_limits_helper_reads_settings(self, settings):
        from apps.integrations.brain.tasks import _time_limits

        settings.BRAIN_SYNC_PRODUCTS_SOFT_TIME_LIMIT = 1234
        soft, hard = _time_limits("BRAIN_SYNC_PRODUCTS_SOFT_TIME_LIMIT", 999)
        assert soft == 1234
        assert hard == 1234 + 300

    def test_brain_time_limits_helper_falls_back_to_default(self, settings):
        from apps.integrations.brain.tasks import _time_limits

        assert not hasattr(settings, "SOME_MISSING_TIME_LIMIT_SETTING")
        soft, hard = _time_limits("SOME_MISSING_TIME_LIMIT_SETTING", 555)
        assert soft == 555
        assert hard == 555 + 300

    def test_kancmaster_time_limits_helper_reads_settings(self, settings):
        from apps.integrations.kancmaster.tasks import _sync_all_time_limits

        settings.KANCMASTER_SYNC_ALL_SOFT_TIME_LIMIT = 4321
        soft, hard = _sync_all_time_limits()
        assert soft == 4321
        assert hard == 4321 + 300


class TestSkipIfHeavySyncRunning:
    def test_false_when_no_heavy_sync(self):
        def dummy_task():
            pass

        dummy_task.apply_async = lambda **kw: pytest.fail("must not reschedule")

        assert skip_if_heavy_sync_running(dummy_task, "dummy") is False

    def test_true_and_reschedules_when_heavy_sync_running(self):
        cache.set(LOCK_KEY, "brain_products", 60)
        calls = []

        def dummy_task():
            pass

        dummy_task.apply_async = lambda **kw: calls.append(kw)

        assert skip_if_heavy_sync_running(dummy_task, "dummy") is True
        assert calls == [{"countdown": 600}]

    def test_custom_kwargs_forwarded(self):
        cache.set(LOCK_KEY, "brain_products", 60)
        calls = []

        def dummy_task():
            pass

        dummy_task.apply_async = lambda **kw: calls.append(kw)

        skip_if_heavy_sync_running(dummy_task, "dummy", kwargs={"reset_cursor": True})
        assert calls == [{"kwargs": {"reset_cursor": True}, "countdown": 600}]

    def test_is_heavy_sync_running_reflects_lock(self):
        assert is_heavy_sync_running() is False
        cache.set(LOCK_KEY, "kancmaster", 60)
        assert is_heavy_sync_running() is True


@pytest.mark.django_db
class TestBrainDaytimeTasksSkipDuringHeavySync:
    """Кожна з цих задач мусить вийти ДО будь-якого API-виклику чи запису в
    БД, якщо зараз триває важкий нічний синк — інакше вона писала б Product
    паралельно з ним."""

    @pytest.mark.parametrize(
        "task_name",
        [
            "sync_categories",
            "sync_prices",
            "sync_stock",
            "sync_options",
            "sync_images",
            "sync_new_products",
            "backfill_metadata",
            "reconcile_stale_stock",
            "sync_description_updates",
        ],
    )
    def test_task_skips_and_reschedules(self, task_name):
        from apps.integrations.brain import tasks as brain_tasks

        cache.set(LOCK_KEY, "brain_products", 60)
        task = getattr(brain_tasks, task_name)

        with patch("apps.integrations.brain.tasks._brain_client") as mock_client:
            with patch.object(task, "apply_async") as mock_apply_async:
                task()

        mock_client.assert_not_called()
        mock_apply_async.assert_called_once()

    def test_backfill_descriptions_skips_with_reset_cursor_kwarg(self):
        from apps.integrations.brain.tasks import backfill_descriptions

        cache.set(LOCK_KEY, "brain_products", 60)

        with patch(
            "apps.integrations.brain.description_sync.run_backfill_descriptions_chunk"
        ) as mock_chunk:
            with patch.object(backfill_descriptions, "apply_async") as mock_apply_async:
                backfill_descriptions(reset_cursor=True)

        mock_chunk.assert_not_called()
        mock_apply_async.assert_called_once_with(kwargs={"reset_cursor": True}, countdown=600)

    def test_time_limits_stay_below_lock_ttl(self):
        """Guardrail: якщо soft/time_limit колись підніметься >= LOCK_TTL (4 год),
        лок сам протухне під час ще живої задачі — і другий синк зможе стартувати
        паралельно (race). Усі важкі задачі мають лишатись безпечно нижче TTL."""
        from apps.integrations.brain import tasks as brain_tasks
        from apps.integrations.heavy_sync import LOCK_TTL
        from apps.integrations.kancmaster import tasks as kancmaster_tasks

        heavy_tasks = [
            brain_tasks.sync_products,
            brain_tasks.sync_brain_images_nightly,
            brain_tasks.sync_all_availability,
            kancmaster_tasks.sync_all,
        ]
        for task in heavy_tasks:
            assert task.time_limit is not None, f"{task.name}: no time_limit set"
            assert task.time_limit < LOCK_TTL, f"{task.name}: time_limit >= heavy lock TTL"

    def test_task_runs_normally_when_no_heavy_sync(self):
        """Sanity check: без активного лока задача поводиться як раніше."""
        from apps.integrations.brain import tasks as brain_tasks

        with patch("apps.integrations.brain.tasks._brain_client") as mock_client:
            mock_client.return_value.get_all_categories.return_value = []
            with patch(
                "apps.integrations.brain.tasks.sync_brain_categories", return_value={},
            ):
                brain_tasks.sync_categories()

        mock_client.assert_called_once()
