"""Service centre template tags."""

from django import template
from django.utils import translation

from apps.services.i18n import translate_unit

register = template.Library()


@register.filter
def service_unit(value: str) -> str:
    if (translation.get_language() or "uk").split("-")[0].lower() != "en":
        return value or ""
    return translate_unit(value or "")
