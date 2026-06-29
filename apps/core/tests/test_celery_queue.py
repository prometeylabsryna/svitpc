"""Tests for Celery queue pruning helpers."""

import json

from apps.core.celery_queue import filter_celery_messages


def _msg(task: str) -> bytes:
    return json.dumps({"headers": {"task": task}}).encode()


def test_filter_drops_np_chunks_and_duplicates():
    messages = [
        _msg("apps.integrations.novaposhta.tasks.sync_np_warehouses_chunk"),
        _msg("apps.integrations.brain.tasks.sync_prices"),
        _msg("apps.integrations.kancmaster.tasks.sync_all"),
        _msg("apps.integrations.kancmaster.tasks.sync_all"),
    ]
    kept, stats = filter_celery_messages(messages, drop_light_routed=False)
    assert stats.before == 4
    assert stats.after == 2
    assert stats.dropped_np_chunks == 1
    assert stats.dropped_duplicates == 1
    names = {json.loads(k.decode())["headers"]["task"] for k in kept}
    assert names == {
        "apps.integrations.brain.tasks.sync_prices",
        "apps.integrations.kancmaster.tasks.sync_all",
    }


def test_filter_drops_light_routed_tasks():
    messages = [
        _msg("apps.shipping.tasks.update_delivery_statuses"),
        _msg("apps.integrations.kancmaster.tasks.sync_all"),
    ]
    kept, stats = filter_celery_messages(messages)
    assert stats.after == 1
    assert stats.dropped_light_routed == 1
