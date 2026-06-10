"""SVG icon ids for catalog categories in site navigation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Category

# More specific rules first.
_ICON_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("used", ("б/у", "b-u", "bu-", "-bu", "used", "вживан", "refurb")),
    ("modem", ("gsm", "модем", "modem", "xdsl", "dsl", "router", "роутер", "wifi", "wi-fi", "мереж", "network", "switch", "комутатор", "lan", "ethernet")),
    ("board", ("дошк", "board", "інтерактив", "interactive", "проектор", "projector", "флипчарт")),
    ("terminal", ("термінал", "terminal", "pos", "касов", "cash-register")),
    ("media", ("медіаплеєр", "media-player", "медиаплеер", "плеєр", "player", "стример")),
    ("laptop", ("ноутбук", "noutbuk", "laptop", "notebook", "нетбук", "netbook", "ultrabook")),
    ("desktop", ("комп'ютер", "компьютер", "desktop", "system-unit", "системний блок", "пк-", "-pc", "pc-")),
    ("monitor", ("монітор", "monitor", "display", "дисплей", "екран")),
    ("smartphone", ("смартфон", "smartphone", "iphone", "android", "планшет", "tablet", "ipad", "телефон", "phone", "mobile")),
    ("tv", ("телевізор", "televisor", "television", "тв-", "-tv", " tv", "smart-tv")),
    ("printer", ("принтер", "printer", "cartridge", "картридж", "тонер", "toner", "mfu", "багатофунк", "сканер", "scanner", "plotter")),
    ("component", (
        "комплектуюч",
        "component",
        "процесор",
        "processor",
        "cpu",
        "материн",
        "motherboard",
        "відеокарт",
        "gpu",
        "vga",
        "оператив",
        "ram",
        "ssd",
        "hdd",
        "накопич",
        "storage",
        "накопитель",
        "блок живлен",
        "psu",
        "power-supply",
        "корпус",
        "chassis",
        "cooling",
        "кулер",
    )),
    ("gaming", ("геймер", "gaming", "game", "ігров", "playstation", "xbox", "nintendo", "джойстик", "gamepad")),
    ("audio", ("навушник", "headphone", "headset", "audio", "колон", "speaker", "мікрофон", "microphone", "акустик", "soundbar", "сабвуфер")),
    ("camera", ("фото", "photo", "camera", "камер", "відеокамер", "webcam", "вебкамер")),
    ("ups", ("ибп", "ibp", "упс", "ups", "дбж", "пживлення", "power-backup", "стабілізатор")),
    ("appliance-large", ("велика побут", "large-appliance", "холодильник", "refrigerator", "пральн", "washing", "плит", "духов", "кондиціонер", "air-condition")),
    ("appliance-small", ("дрібна побут", "small-appliance", "чайник", "kettle", "пилосос", "vacuum", "блендер", "blender", "мікрохвил", "microwave")),
    ("smart-home", ("розумн", "smart-home", "hi-tech", "hitech", "гаджет", "gadget", "wearable", "фітнес", "fitness", "smartwatch")),
    ("office", ("канцтовар", "канцеляр", "office", "папір", "paper", "ручк", "pen", "marker", "степлер")),
    ("cable", ("кабел", "cable", "перехідник", "adapter", "аксесуар", "accessor", "чохол", "case", "клавіатур", "keyboard", "миш", "mouse", "pad")),
    ("software", ("soft", "ліценз", "license", "windows", "антивірус", "antivirus", "office-365", "підписк")),
    ("server", ("сервер", "server", "nas", "raid", "storage-system")),
)

_DEFAULT_ICON = "default"


def _category_haystack(category: Category) -> str:
    parts = [category.slug.replace("-", " "), category.name]
    name_en = getattr(category, "name_en", None)
    if name_en:
        parts.append(str(name_en))
    return " ".join(parts).lower()


def resolve_category_icon_id(category: Category) -> str:
    """Return built-in SVG icon id when no custom icon image is uploaded."""
    haystack = _category_haystack(category)
    for icon_id, keywords in _ICON_RULES:
        if any(keyword in haystack for keyword in keywords):
            return icon_id
    return _DEFAULT_ICON
