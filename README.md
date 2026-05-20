# СвітПК — Інтернет-магазин комп'ютерної техніки

Django 5 + HTMX + Vanilla JS (ES modules) + PostgreSQL 16 + Redis + Celery

## Швидкий старт (локально)

### Вимоги
- Python 3.11+
- PostgreSQL 14+
- Redis
- [uv](https://github.com/astral-sh/uv)

### Встановлення

```bash
# Клонуємо репозиторій
git clone <url> SvitPC && cd SvitPC

# Встановлюємо залежності
uv venv && uv sync --all-extras

# Налаштовуємо .env
cp .env.example .env
# Відредагуйте .env: SECRET_KEY, DATABASE_URL, REDIS_URL
```

### База даних

```bash
# Створюємо БД
createdb svitpc
psql postgres -c "CREATE USER svitpc WITH PASSWORD 'svitpc' CREATEDB;"
psql postgres -c "CREATE DATABASE svitpc OWNER svitpc;"

# Застосовуємо міграції
make migrate
```

### Запуск

```bash
make run         # Django dev server: http://localhost:8000
make worker      # Celery worker (окремий термінал)
make beat        # Celery beat — планувальник (окремий термінал)
```

### Імпорт SQL-бекапу OpenCart

```bash
# Кладемо файл бекапу в data/
mkdir -p data
cp /path/to/svitpc_backup.sql data/

# Запускаємо імпорт (streaming, без завантаження в RAM)
make import-sql
# або з вибором кроків:
python manage.py import_opencart_sql \
  --file data/svitpc_2023-02-28_15-47-34_backup.sql \
  --steps brands,categories,products,images,attrs,filters,seo,reviews
```

Логи помилок зберігаються у `logs/import_opencart.jsonl`.

## Змінні середовища (.env)

| Змінна | Опис | Приклад |
|---|---|---|
| `SECRET_KEY` | Django secret key | `django-insecure-...` |
| `DATABASE_URL` | URL PostgreSQL | `postgresql://svitpc:svitpc@localhost/svitpc` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379/0` |
| `SITE_URL` | Публічний URL сайту | `https://svitpc.com.ua` |
| `BRAIN_API_KEY` | Ключ Brain API | від замовниці |
| `KANCMASTER_XML_URL` | URL XML-фіду Kancmaster | від замовниці |
| `NOVA_POSHTA_API_KEY` | Ключ Нової Пошти | від замовниці |
| `LIQPAY_PUBLIC_KEY` / `LIQPAY_PRIVATE_KEY` | LiqPay | від замовниці |
| `WAYFORPAY_MERCHANT_ACCOUNT` / `WAYFORPAY_MERCHANT_SECRET` | WayForPay | від замовниці |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | від замовниці |
| `OPENAI_API_KEY` | OpenAI для AI-функцій | від замовниці |
| `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` | Web Push | генеруємо (`pywebpush vapid --gen-key`) |
| `GTM_ID` | Google Tag Manager ID | `GTM-XXXXXX` |
| `GA_MEASUREMENT_ID` | GA4 Measurement ID | `G-XXXXXXXX` |

## Celery

```bash
make worker   # celery -A config worker -l info
make beat     # celery -A config beat -l info --scheduler django
```

Заплановані задачі (beat):
- `brain.sync_prices` — кожні 4 год
- `brain.sync_stock` — щогодини
- `kancmaster.sync_all` — щодня о 3:00
- `loyalty.send_birthday_greetings` — щодня о 9:00
- `shipping.update_delivery_statuses` — кожні 2 год

## Налаштування інтеграцій

### Brain API
Вкажіть `BRAIN_API_KEY` в `.env`. Запустіть початкову синхронізацію:
```bash
python manage.py shell -c "from apps.integrations.brain.tasks import sync_products; sync_products.delay()"
```

### Нова Пошта — початкове завантаження міст
```bash
python manage.py shell -c "from apps.integrations.novaposhta.tasks import sync_np_cities; sync_np_cities.delay()"
```

### Vchasno.Kasa
Вкажіть `VCHASNOKASA_API_KEY` та `VCHASNOKASA_LICENSE_KEY` в `.env`. Фіскалізація відбувається автоматично після підтвердження оплати.

## Адмін-панель

Адмін-панель доступна за адресою `/admin/` (або іншим `ADMIN_URL` з `.env`).

### Початковий суперкористувач
```bash
make createsuperuser
# або: python manage.py createsuperuser
```

### 2FA
Після першого входу — увімкніть TOTP через "Мій обліковий запис → 2FA".

### Корисні дії в адмінці
- **Товари** → виберіть кілька → "Згенерувати SEO (AI)" — автоматичне написання title/description
- **Категорії** → drag-and-drop для зміни порядку (MPTT)
- **Інтеграції → Brain** → кнопка "Синхронізувати ціни/залишки" вручну
- **Замовлення** → "Створити ТТН НП", "Відправити повідомлення про статус"

## Бекап БД

```bash
make backup-db   # pg_dump → backups/svitpc_YYYYMMDD.sql.gz
```

Додайте до cron (щоденно о 2:00):
```cron
0 2 * * * cd /var/www/svitpc && .venv/bin/python manage.py backup_db >> logs/backup.log 2>&1
```

## Тести

```bash
make test                    # всі тести
pytest apps/importer/ -v     # тільки importer
pytest apps/catalog/ -v      # тільки catalog
```

## Лінтинг і форматування

```bash
make lint   # ruff check + mypy + djlint
make fmt    # ruff format
```

## Структура директорій

```
SvitPC/
├── apps/
│   ├── catalog/          # Product, Category, Brand, Attribute, Filter
│   ├── customers/        # Custom User model, Address
│   ├── cart/             # Session-based cart
│   ├── checkout/         # Multi-step checkout
│   ├── orders/           # Order, OrderItem, OrderStatus
│   ├── wishlist/         # WishlistItem
│   ├── compare/          # Session-based compare
│   ├── reviews/          # Product reviews with moderation
│   ├── shipping/         # Nova Poshta, Ukrposhta
│   ├── payments/         # LiqPay, WayForPay, Monobank
│   ├── loyalty/          # Bonus system, Coupons
│   ├── promotions/       # Promotions, Banners
│   ├── services/         # Service center pages
│   ├── pages/            # Static info pages (WYSIWYG)
│   ├── notifications/    # Email/SMS/Telegram/Push router
│   ├── bots/telegram/    # aiogram Telegram bot
│   ├── chat/             # Online consultant + Telegram bridge
│   ├── ai/               # LLM content gen, AI consultant, pgvector
│   ├── search/           # Postgres FTS + pgvector semantic search
│   ├── seo/              # Sitemaps, robots.txt, JSON-LD
│   ├── analytics/        # GA4/GTM, merchant feeds
│   ├── api/              # DRF /api/v1/ stubs
│   ├── importer/         # import_opencart_sql management command
│   ├── core/             # Middleware, templatetags, context processors
│   └── integrations/     # Brain, Kancmaster, NovaPoshta, payments
├── config/
│   ├── settings/         # base, develop, test, staging, production
│   ├── urls.py
│   ├── celery.py
│   └── asgi.py
├── static/
│   ├── css/              # BEM + cascade layers, mobile-first
│   └── js/               # ES modules, no globals
├── templates/            # Django templates
├── locale/uk/            # Ukrainian translations
└── data/                 # SQL backups (not in git)
```
