"""English copy for service centre (imported from Ukrainian price list)."""

from __future__ import annotations

SERVICE_CATALOG_UK_EN: dict[str, dict[str, str]] = {
    "Види робіт загального призначення": {
        "category_en": "General services",
        "service_en": "General repairs",
        "description_en": (
            "Operating system setup, drivers and software, data backup, "
            "Windows/Office activation, antivirus check, and on-site visits."
        ),
    },
    "Ноутбуки": {
        "category_en": "Laptops",
        "service_en": "Laptop repair",
        "description_en": (
            "Diagnostics, screen and keyboard replacement, battery service, maintenance, "
            "liquid damage recovery, BGA soldering, and more."
        ),
    },
    "Системні блоки": {
        "category_en": "Desktop PCs",
        "service_en": "Desktop PC repair",
        "description_en": "Diagnostics, PC assembly, component replacement, and maintenance.",
    },
    "Монітори": {
        "category_en": "Monitors",
        "service_en": "Monitor repair",
        "description_en": "Power board repair and replacement of monitor control boards.",
    },
    "Принтери та БФП": {
        "category_en": "Printers and MFPs",
        "service_en": "Printer and MFP repair",
        "description_en": (
            "Diagnostics, maintenance, paper feed repairs, firmware updates, "
            "waste counter reset, and fuser replacement."
        ),
    },
    "Картриджі": {
        "category_en": "Cartridges",
        "service_en": "Cartridge refill and service",
        "description_en": "Laser and ink cartridge refills, cleaning, rebuilds, and part replacement.",
    },
    "Локальні мережі": {
        "category_en": "Local networks",
        "service_en": "Local network installation",
        "description_en": (
            "Cable and socket installation, switches and routers, MikroTik setup, "
            "and network printer configuration."
        ),
    },
}

PRICE_ITEM_UK_EN: dict[str, str] = {
    "Налаштування Операційної системи": "Operating system setup",
    "Налаштування Программ (Zoom,GoogleMeet,і т.п)": "Software setup (Zoom, Google Meet, etc.)",
    "Встановлення Драйвера 1шт": "Driver installation (1 item)",
    "Встановлення Комплекту Драйверів": "Full driver pack installation",
    "Встановлення Программи 1шт": "Application installation (1 item)",
    "Встановлення Комплекту Программ": "Software bundle installation",
    "Копіювання Інформації від 20Гб": "Data backup from 20 GB",
    "Активація Windows/Office": "Windows/Office activation",
    "Антивірусний контроль": "Antivirus check",
    "Виїзд в межех міста": "On-site visit (within city)",
    "Виїзд за межі міста": "On-site visit (outside city)",
    "Диагностика": "Diagnostics",
    "Діагностика": "Diagnostics",
    "Заміна HDD/RAM": "HDD/RAM replacement",
    "Заміна Матриці Ноутбука": "Laptop screen replacement",
    "Заміна Клавіатури Ноутбука": "Laptop keyboard replacement",
    "Заміна Клавіатури Топкейсу": "Top-case keyboard replacement",
    "Заміна АКБ Ноутбука": "Laptop battery replacement",
    "Заміна Динаміків Ноутбука(Технічне обслуговування входить в комплект)": (
        "Laptop speaker replacement (maintenance included)"
    ),
    "Заміна CD/DVD приводу на фрейм перехідник": "CD/DVD drive to caddy adapter replacement",
    "Заміна частин корпусу": "Chassis part replacement",
    "Технічне обслуговування": "Maintenance service",
    "Технічне обслуговування Ігрового Ноутбука": "Gaming laptop maintenance",
    "Відновлення після залиття": "Liquid damage recovery",
    "Прошивка BIOS": "BIOS firmware update",
    "Відновлення вузлів живлення": "Power circuit repair",
    "BGA Пайка": "BGA soldering",
    "Заміна кабелю Блока живлення": "Power supply cable replacement",
    "Складання Системного блоку": "Desktop PC assembly",
    "Заміна комплектуючих 1шт": "Component replacement (1 item)",
    "Заміна конденсаторів електролітичних 1шт": "Electrolytic capacitor replacement (1 pc)",
    "Заміна Електроних плат пристрою 1шт": "Device board replacement (1 pc)",
    "Ремонт Блока живлення": "Power supply repair",
    "Заміна вузлів подачі паперу": "Paper feed mechanism replacement",
    "Прошивка Пристрою": "Device firmware update",
    "Скидання лічильника абсорбера (памперса)": "Waste ink counter reset",
    "Заміна термоплівки": "Fuser replacement",
    "Заправка Лазерного": "Laser cartridge refill",
    "Заправка струйного": "Ink cartridge refill",
    "Заміна Фотобарабана": "Drum unit replacement",
    "Заміна Магнитного вала": "Magnetic roller replacement",
    "Заміна Вала Первинного заряду": "Primary charge roller replacement",
    "Заміна леза": "Blade replacement",
    "Чистка/Перезбинання": "Cleaning and rebuild",
    "Розмочка Струйного картриджа(незалежно від результату)": "Ink cartridge soak (regardless of result)",
    "Монтаж коробу пластикового (2м)": "Plastic trunking installation (2 m)",
    "Монтаж кабеля відкритим монтажем": "Surface cable installation",
    "Монтаж локальної розетки": "Network socket installation",
    "Монтаж кабеля в пластиковий короб": "Cable routing in trunking",
    "Пробивання отвору до ⌀ 25 мм товщіною до 500мм": "Drilling up to ⌀25 mm, depth up to 500 mm",
    "Пробивання отвору більше ⌀ 25 мм товщіною до 500мм": "Drilling over ⌀25 mm, depth up to 500 mm",
    "Демонтаж старої мережі": "Legacy network removal",
    "Монтаж гофротруби": "Corrugated conduit installation",
    "Монтаж Світча/Роутера": "Switch/router installation",
    "Налаштування Роутера": "Router setup",
    "Налаштування MikroTik": "MikroTik setup",
    "Налаштування доступу до локальної мережі": "Local network access setup",
    "Налаштування мережевого принтера": "Network printer setup",
    "Монтаж настінної комунікації": "Wall-mounted patch panel installation",
}

UNIT_UK_EN: dict[str, str] = {
    "шт": "pc",
    "м": "m",
    "км": "km",
}


def translate_category_name(name: str) -> str:
    meta = SERVICE_CATALOG_UK_EN.get((name or "").strip(), {})
    return meta.get("category_en", "")


def translate_service_name(category_name: str, service_name: str) -> str:
    meta = SERVICE_CATALOG_UK_EN.get((category_name or "").strip(), {})
    return meta.get("service_en", "")


def translate_service_description(category_name: str) -> str:
    meta = SERVICE_CATALOG_UK_EN.get((category_name or "").strip(), {})
    return meta.get("description_en", "")


def translate_price_item_name(name: str) -> str:
    key = (name or "").strip()
    return PRICE_ITEM_UK_EN.get(key, "")


def translate_unit(unit: str) -> str:
    key = (unit or "").strip()
    return UNIT_UK_EN.get(key, key)
