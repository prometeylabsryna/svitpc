"""Безпечне ставлення Celery-задач на user-facing шляхах.

`.delay()` кидає виняток, коли брокер недоступний — checkout/оплата не повинні
падати через неможливість поставити побічний ефект (email, ТТН, фіскалізацію)
у чергу. Бізнес-операція комітиться завжди; втрачене сповіщення має шлях
повтору (admin action / Beat-звірка).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def safe_delay(task, *args, **kwargs) -> bool:
    """task.delay(...) без винятку при недоступному брокері.

    Повертає True, якщо задачу поставлено в чергу; False — брокер недоступний
    (подія залогована з traceback).
    """
    try:
        task.delay(*args, **kwargs)
        return True
    except Exception:
        logger.warning(
            "Celery broker unavailable — task %s skipped (args=%r)",
            getattr(task, "name", task),
            args,
            exc_info=True,
        )
        return False
