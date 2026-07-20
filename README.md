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
make worker-priority  # Celery worker для ТТН/доставки (окремий термінал)
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
| `LLM_API_KEY` | OpenAI-сумісний API для AI (описи, SEO, консультант) | від замовниці |
| `LLM_MODEL` | Модель LLM | `gpt-4o-mini` |
| `LLM_BASE_URL` | Base URL OpenAI-сумісного API | `https://api.openai.com/v1` |
| `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` | Web Push | генеруємо (`pywebpush vapid --gen-key`) |
| `GTM_ID` | Google Tag Manager ID | `GTM-XXXXXX` |
| `GA_MEASUREMENT_ID` | GA4 Measurement ID | `G-XXXXXXXX` |

### AI (LLM)

У `.env` вкажіть `LLM_API_KEY` (OpenAI або інший OpenAI-сумісний endpoint через `LLM_BASE_URL`).

| Функція | Де | Примітка |
|---|---|---|
| AI-консультант (чат, сумісність) | `/ai/consultant/` | Синхронно, Celery не потрібен |
| SEO title/description товарів | Адмінка → Товари → «Згенерувати SEO (AI)» | Потрібен Celery worker |
| Повні / короткі описи, характеристики | Адмінка → Товари → відповідні AI-дії | Потрібен Celery worker |
| Опис категорій | Адмінка → Категорії → «Згенерувати AI-опис категорій» | Синхронно |
| EN-переклад каталогу через LLM | `translate_to_english --backend=llm` | Альтернатива Google Translate |

## Celery

```bash
make worker   # celery -A config worker -l info
make beat     # celery -A config beat -l info --scheduler django
```

Заплановані задачі (beat, Europe/Kyiv) — див. `config/celery_beat_schedule.py`:

**Вночі (03:00–06:00):** Kancmaster, Brain повний імпорт, фото (1 раз), описи, EN-переклад.  
**Вдень:** ціни/залишки/метадані Brain (без завантаження фото).  
Важкі задачі серіалізовані через Redis-lock (`apps/integrations/heavy_sync.py`).

## Налаштування інтеграцій

### Brain API
Вкажіть `BRAIN_LOGIN` та `BRAIN_PASSWORD` в `.env` (див. `.env.example`).  
Після імпорту з OpenCart — увімкніть політику приховування та backfill:
```bash
uv run manage.py brain_setup --sync-now   # одразу
uv run manage.py brain_setup --enqueue    # через Celery
```
Повна нічна синхронізація:
```bash
uv run manage.py shell -c "from apps.integrations.brain.tasks import sync_products; sync_products.delay()"
```
В адмінці: **Товари** → дії «Brain: синхронізувати…» / «Brain: оновити ціни та залишки».
Націнки: **Налаштування → Знижкові правила** (`MarkupRule`).

### Англійські переклади каталогу

Інтерфейс сайту — через Django `locale/`. Назви та описи товарів/категорій — окремі поля `*_en` у БД (`django-modeltranslation`).

Після імпорту або синхронізації заповніть відсутні EN-поля:

```bash
make translate-en
# або частково:
uv run manage.py translate_to_english --what=products
uv run manage.py translate_to_english --what=site
```

Автоматично: Celery beat `catalog-translate-en` (кожні 6 год) і після `sync_kancmaster` / нічного `brain.sync_products`.

### Kancmaster XML
Вкажіть у `.env`: `KANCMASTER_XML_URL`, `KANCMASTER_LOGIN`, `KANCMASTER_PASSWORD`  
(URL зазвичай `https://kancmaster.com.ua/export/kancmaster.xml`; без credentials endpoint `xml_export_request` повертає HTML).

Повна синхронізація (канцтовари, ціни, залишки, фото, описи, категорії):
```bash
uv run manage.py sync_kancmaster
```
Автоматично через Celery beat: `kancmaster.sync_all` — кожні 6 год.

### Нова Пошта — початкове завантаження міст
```bash
uv run manage.py sync_novaposhta
# або через Celery:
uv run manage.py sync_novaposhta --async
```

Потрібні змінні в `.env`: `NOVA_POSHTA_API_KEY`, `NP_SENDER_*` (для ТТН).

### Vchasno.Kasa
Вкажіть `VCHASNO_CASHBOX_KEY` (токен тестової або бойової каси з kasa.vchasno.ua) у `.env`. Фіскалізація відбувається автоматично після підтвердження оплати. Перевірка: `make test-vchasnokasa`.

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
- **Товари** → виберіть кілька → AI-дії (потрібні `LLM_API_KEY` у `.env` та запущений Celery worker):
  - «Згенерувати SEO (AI)» — title/description
  - «Згенерувати повні описи (AI)»
  - «Згенерувати короткі описи (AI)»
  - «Покращити характеристики (AI)»
- **Категорії** → «Згенерувати AI-опис категорій» (синхронно, без Celery); drag-and-drop для зміни порядку (MPTT)
- **Товари** → дії Brain (синхронізація, ціни/залишки, приховування без залишку)
- **Замовлення** → "Створити ТТН НП", "Відправити повідомлення про статус"

## Деплой на сервер (Docker)

На сервері проєкт зазвичай лежить у `/var/www/svitpc`.

### 1. Локально (Mac) — спочатку push

```bash
git add -A
git commit -m "ТТН НП: autocomplete в адмінці, priority worker, виправлення API"
git push origin main
```

### 2. На сервері

```bash
cd /var/www/svitpc   # або ваш шлях до клону репозиторію
git pull origin main
```

Перевірте `.env` (ключі Нової Пошти обовʼязкові для ТТН):

```bash
grep -E '^NOVA_POSHTA_API_KEY=|^NP_SENDER_' .env
```

Якщо порожньо — допишіть значення в `.env` і збережіть.

### 3. Перезбірка і запуск

```bash
bash deploy/docker/deploy.sh
```

Скрипт сам: `docker compose build`, `up -d`, міграції через backend, `collectstatic`.

### 4. Перевірка після деплою

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 celery_worker_priority
curl -sf http://127.0.0.1/healthz/ && echo OK
```

У списку контейнерів має бути **`celery_worker_priority`** у статусі Up — без нього ТТН не створюються.

### 5. Тест ТТН

1. Адмінка → Замовлення → створити/відкрити НП-замовлення з містом і відділенням з підказок.
2. Післяплата — зберегти; або картка — увімкнути «Оплачено».
3. Через 1–2 хв у полі **ТТН** зʼявиться номер, або action «Створити ТТН (Нова Пошта)».

Логи помилок API:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs celery_worker_priority | grep -i 'NP create_ttn'
```

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
│   ├── shipping/         # Nova Poshta
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
