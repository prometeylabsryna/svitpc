"""UK → EN glossary for catalog labels when DB ``*_en`` fields are empty."""

from __future__ import annotations

import re

_CYRILLIC = re.compile(r"[а-яА-ЯіїєґІЇЄҐ]")

# Ukrainian catalog terms (aligned with apps.catalog.ru_localization.GLOSSARY_RU_UK).
GLOSSARY_UK_EN: dict[str, str] = {
    "Виробник": "Manufacturer",
    "Виробник акумулятора": "Battery manufacturer",
    "Виробник чіпсета": "Chipset manufacturer",
    "Країна виробник": "Country of manufacturer",
    "Країна-виробник": "Country of manufacturer",
    "Країна-виробник товару": "Product country of manufacturer",
    "Країна виробництва": "Country of manufacture",
    "Вага": "Weight",
    "Акумулятор": "Battery",
    "Колір": "Color",
    "Колір тексту": "Text color",
    "Гарантія, міс": "Warranty, months",
    "Гарантія": "Warranty",
    "Потужність": "Power",
    "Тип продукту": "Product type",
    "Розмір": "Size",
    "Об'єм": "Volume",
    "Об'єм чаші": "Bowl volume",
    "Довжина": "Length",
    "Ширина": "Width",
    "Висота": "Height",
    "Глибина": "Depth",
    "Матеріал": "Material",
    "Особливості": "Features",
    "Керування": "Control",
    "Швидкість": "Speed",
    "Пам'ять": "Memory",
    "Діагональ": "Diagonal",
    "Інтерфейс": "Interface",
    "Комплектація": "Package contents",
    "Призначення": "Purpose",
    "Характеристики": "Specifications",
    "Також шукають": "People also search for",
    "Кількість": "Quantity",
    "Кількість LAN-портів": "Number of LAN ports",
    "Кількість USB-портів": "Number of USB ports",
    "Серія": "Series",
    "Мова меню": "Menu language",
    "Функції": "Functions",
    "Тип нагріву": "Heating type",
    "Тип внутрішнього покриття": "Internal coating type",
    "Корисний об'єм морозильної камери": "Useful freezer volume",
    "Пристрої введення в комплекті": "Input devices included",
    "Потужність і тип конфорок": "Hob power and type",
    "Клас телефону": "Phone class",
    "Фокусна відстань min, мм": "Minimum focal length, mm",
    "Модель корпусу": "Case model",
    "Продуктивність охолодження": "Cooling performance",
    "Довжина виливу": "Spout length",
    "Для створення": "For creating",
    "Тип камери згоряння": "Combustion chamber type",
    "Обметування петлі": "Loop overcasting",
    "Місячний обсяг друку": "Monthly print volume",
    "Бренд": "Brand",
    "Червоний": "Red",
    "Синій": "Blue",
    "Зелений": "Green",
    "Чорний": "Black",
    "Білий": "White",
    "Сірий": "Grey",
    "Жовтий": "Yellow",
    "Помаранчевий": "Orange",
    "Рожевий": "Pink",
    "Фіолетовий": "Purple",
    "Коричневий": "Brown",
    "Срібний": "Silver",
    "Золотий": "Gold",
}

_RUNTIME_CACHE: dict[str, str] = {}


def localize_uk_to_en(text: str, *, cache: dict[str, str] | None = None) -> str:
    """Return English label for Ukrainian catalog copy when a glossary entry exists."""
    t = (text or "").strip()
    if not t:
        return t
    if not _CYRILLIC.search(t):
        return t
    store = cache if cache is not None else _RUNTIME_CACHE
    if t in store:
        return store[t]
    en = GLOSSARY_UK_EN.get(t, t)
    store[t] = en
    return en
