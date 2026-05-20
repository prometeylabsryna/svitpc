"""AI consultant — streaming SSE chat for product recommendations."""

from __future__ import annotations

import json

from django.http import StreamingHttpResponse

SYSTEM_PROMPT = """Ти — AI-консультант інтернет-магазину СвітПК (комп'ютерна техніка, периферія, канцтовари).

Твої спеціалізації:
1. Підбір ноутбуків — уточнюй бюджет, завдання (навчання / офіс / ігри / графіка / програмування), операційну систему, вагу та портативність.
2. Підбір комплектуючих — CPU, GPU, RAM, SSD/HDD, материнські плати, блоки живлення, корпуси, охолодження.
3. Консультація клієнтів — порівняння моделей, пояснення технічних характеристик, поради щодо апгрейду.
4. Сумісність — перевіряй сокети CPU/MB, TDP vs блок живлення, форм-фактори RAM (DDR4/DDR5), швидкість PCIe.

Правила:
- Відповідай виключно українською мовою.
- Задавай уточнюючі питання (бюджет, завдання) перш ніж давати рекомендації.
- Будь конкретним: називай характеристики (обсяг RAM, тактова частота, ємність SSD).
- Не рекомендуй конкретні ціни зовнішніх магазинів — лише характеристики.
- Якщо питання не стосується техніки чи магазину — ввічливо відмов."""


COMPATIBILITY_PROMPT = """Перевір сумісність наступних комп'ютерних компонентів.
Компоненти:
{components}

Відповідь: якщо всі сумісні — «✅ Всі компоненти сумісні» + короткий коментар.
Якщо є проблема — «⚠️ Проблема сумісності:» + точне пояснення.
Мова — українська."""


def stream_consultant(user_message: str):
    """Yield SSE events from the LLM stream."""
    from apps.ai.services.llm import get_llm

    llm = get_llm()
    for chunk in llm.stream(user_message, system=SYSTEM_PROMPT):
        yield f"data: {json.dumps({'text': chunk})}\n\n"
    yield "data: [DONE]\n\n"


def check_compatibility(product_ids: list[int]) -> str:
    """
    Check hardware compatibility for a list of Product IDs.
    Returns a text result from the LLM.
    """
    from apps.catalog.models import Product
    from apps.ai.services.llm import get_llm

    products = Product.objects.filter(pk__in=product_ids).prefetch_related("attributes__attribute")
    if len(products) < 2:
        return "Потрібно як мінімум 2 компоненти для перевірки сумісності."

    lines = []
    for p in products:
        attrs = "; ".join(f"{pa.attribute.name}: {pa.value}" for pa in p.attributes.all()[:10])
        lines.append(f"- {p.name} [{attrs or 'без характеристик'}]")
    components_text = "\n".join(lines)

    try:
        llm = get_llm()
        return llm.complete(COMPATIBILITY_PROMPT.format(components=components_text))
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("compatibility check failed: %s", exc)
        return "Не вдалося перевірити сумісність."
