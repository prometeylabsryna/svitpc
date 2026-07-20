"""Fill missing English translations in locale/en/LC_MESSAGES/django.po."""

from __future__ import annotations

import re
from pathlib import Path

TRANSLATIONS: dict[str, str] = {
    "LLM_API_KEY не налаштовано в .env — додайте ключ OpenAI-сумісного API.": (
        "LLM_API_KEY is not configured in .env — add an OpenAI-compatible API key."
    ),
    "Brain: синхронізувати (ціни, залишки, фото, опції)": (
        "Brain: sync (prices, stock, photos, options)"
    ),
    "Повну інкрементальну синхронізацію Brain поставлено в чергу Celery": (
        "Full incremental Brain sync queued in Celery"
    ),
    "Згенерувати повні описи (AI)": "Generate full descriptions (AI)",
    "Генерацію описів поставлено в чергу": "Description generation queued",
    "Згенерувати короткі описи (AI)": "Generate short descriptions (AI)",
    "Генерацію коротких описів поставлено в чергу": "Short description generation queued",
    "Покращити характеристики (AI)": "Improve specifications (AI)",
    "Покращення характеристик поставлено в чергу": "Specification improvement queued",
    "Brain: оновити ціни та залишки": "Brain: update prices and stock",
    "Оновлення цін і залишків Brain поставлено в чергу": "Brain price and stock update queued",
    "Brain: приховувати без залишку": "Brain: hide when out of stock",
    "Некоректна сума бонусів.": "Invalid bonus amount.",
    "Перевірте промокод або бонуси та спробуйте знову.": (
        "Check your promo code or bonuses and try again."
    ),
    "Прибрано з порівняння": "Removed from comparison",
    "Додано до порівняння": "Added to comparison",
    "У порівнянні вже максимум 4 товари": "Comparison already has the maximum of 4 products",
    "Порівняння очищено": "Comparison cleared",
    "Месенджери": "Messengers",
    "Введіть текст у полі telegram_text.": "Enter text in the telegram_text field.",
    "Введіть коректний номер телефону.": "Enter a valid phone number.",
    "Дата народження не може бути в майбутньому.": "Date of birth cannot be in the future.",
    "Порожньо — промокод для всіх; заповнено — лише для цього клієнта": (
        "Empty — promo code for everyone; filled — only for this customer"
    ),
    "Надіслати Telegram-повідомлення": "Send Telegram message",
    "ТТН (НП)": "Tracking number (NP)",
    "Ключ ідемпотентності": "Idempotency key",
    "Надіслати push-повідомлення про акцію": "Send push notification about promotion",
    "Push-розсилку поставлено в чергу: %(n)d акцій": "Push campaign queued: %(n)d promotions",
    "✅ Схвалити відгуки": "✅ Approve reviews",
    "🚫 Відхилити відгуки": "🚫 Reject reviews",
    "Заявка": "Request",
    "Внутрішнє": "Internal",
    "Оберіть оцінку від 1 до 5": "Select a rating from 1 to 5",
    "Опис (EN)": "Description (EN)",
    "Вкажіть ім'я.": "Enter your first name.",
    "Вкажіть прізвище.": "Enter your last name.",
    "Вкажіть телефон.": "Enter your phone number.",
    "Оберіть місто зі списку підказок.": "Select a city from the suggestions.",
    "Оберіть місто доставки.": "Select a delivery city.",
    "Оберіть відділення Нової Пошти.": "Select a Nova Post branch.",
    "Оберіть спосіб доставки.": "Select a delivery method.",
    "Товар додано до бажаних": "Product added to wishlist",
    "Прибрано з бажаних": "Removed from wishlist",
    "AI-консультант СвітПК — підбір ноутбуків, комплектуючих, перевірка сумісності компонентів": (
        "SvitPC AI consultant — laptop and component selection, compatibility checks"
    ),
    "Підбір ноутбуків, комплектуючих, консультація з вибору техніки та перевірка сумісності компонентів.": (
        "Laptop and component selection, tech buying advice, and compatibility checks."
    ),
    "Режими консультанта": "Consultant modes",
    "Швидкі запити": "Quick prompts",
    "Підібрати ноутбук до 30 000 ₴": "Find a laptop under 30,000 UAH",
    "Ігровий ПК до 50 000 ₴": "Gaming PC under 50,000 UAH",
    "Яку відеокарту обрати?": "Which graphics card should I choose?",
    "Офісний ПК — що потрібно?": "Office PC — what do I need?",
    "Порекомендуй принтер для дому": "Recommend a home printer",
    "Запитайте про ноутбук, GPU, сумісність...": "Ask about laptops, GPUs, compatibility...",
    "ID товарів для перевірки": "Product IDs to check",
    "Введіть ID товарів через кому або пробіл (мінімум 2). ID видно в адресному рядку сторінки товару або в адмінці.": (
        "Enter product IDs separated by commas or spaces (minimum 2). "
        "IDs appear in the product page URL or in the admin."
    ),
    "Рейтинг": "Rating",
    "Запитати AI-консультанта про цей товар": "Ask the AI consultant about this product",
    "Акційні кампанії та спецпропозиції →": "Promotions and special offers →",
    "Скористайтесь чат-кнопкою внизу сторінки для швидкого зв'язку з менеджером.": (
        "Use the chat button at the bottom of the page to contact a manager quickly."
    ),
    "Спосіб": "Method",
    "Індекс": "Postcode",
    "Оплата карткою (Visa/Mastercard)": "Card payment (Visa/Mastercard)",
    "Післяплата (при отриманні)": "Cash on delivery",
    "Напр. 01001": "E.g. 01001",
    "Самовивіз з нашого магазину:": "Pickup from our store:",
    "м. Дніпро, пр. Д. Яворницького 1": "Dnipro, 1 D. Yavornytskyi Ave.",
    "Пн–Пт 9:00–19:00, Сб 10:00–17:00": "Mon–Fri 9:00–19:00, Sat 10:00–17:00",
    "Visa / Mastercard через LiqPay": "Visa / Mastercard via LiqPay",
    "Швидка оплата з Google": "Fast checkout with Google",
    "Швидка оплата з Apple": "Fast checkout with Apple",
    "Оплата при отриманні на Новій Пошті": "Pay on delivery via Nova Post",
    "Розстрочка 0%% через LiqPay Installment": "0%% installment via LiqPay Installment",
    "Наприклад: BDAY-XXXXXXXX": "Example: BDAY-XXXXXXXX",
    "Сума бонусів (грн)": "Bonus amount (UAH)",
    "Прибрати %(name)s з порівняння": "Remove %(name)s from comparison",
    "Відкрити чат з консультантом": "Open chat with consultant",
    "Привіт! Напишіть ваше запитання, і менеджер відповість якнайшвидше.": (
        "Hello! Send your question and a manager will reply as soon as possible."
    ),
    "Акційні кампанії": "Promotions",
    "Швидка навігація": "Quick navigation",
    "Нова адреса": "New address",
    "Навігація кабінету": "Account navigation",
    "Дім, Робота...": "Home, Work...",
    "Зберегти адресу": "Save address",
    "Скасувати": "Cancel",
    "Мої адреси": "My addresses",
    "Адреси доставки": "Delivery addresses",
    "Додати": "Add",
    "Основна": "Default",
    "Видалити адресу": "Delete address",
    "Видалити цю адресу?": "Delete this address?",
    "Немає збережених адрес.": "No saved addresses.",
    "Додати першу адресу": "Add your first address",
    "Бонусна програма": "Bonus program",
    "Мій профіль": "My profile",
    "Деталі": "Details",
    "Редагування профілю": "Edit profile",
    "Зберегти зміни": "Save changes",
    "ТТН (НП):": "Tracking number (NP):",
    "Будь ласка, зачекайте. Вас перенаправляють на сторінку оплати...": (
        "Please wait. You are being redirected to the payment page..."
    ),
    "Не вдалося ініціювати оплату. Спробуйте ще раз або оберіть інший спосіб оплати.": (
        "Could not initiate payment. Try again or choose another payment method."
    ),
    "Усі товари зі знижкою →": "All discounted products →",
    "зірок": "stars",
    "Ремонт ноутбуків, ПК, принтерів, заправка картриджів, відновлення даних та інші послуги сервісного центру СвітПК": (
        "Laptop, PC and printer repair, cartridge refills, data recovery "
        "and other SvitPC service centre services"
    ),
    "Пошук товарів…": "Search products…",
    "Консультант": "Consultant",
    "Сумісність": "Compatibility",
    "Ноутбук для навчання": "Laptop for studying",
    "Ваше питання": "Your question",
    "Наприклад: 101, 245, 378": "E.g.: 101, 245, 378",
    "Перевірити": "Check",
    "Підкатегорії": "Subcategories",
    "Більше підкатегорій": "More subcategories",
    "Менше підкатегорій": "Fewer subcategories",
    "Запитати AI": "Ask AI",
    "Дякуємо! Менеджер відповість найближчим часом.": "Thank you! A manager will reply shortly.",
    "Онлайн-консультант": "Online consultant",
    "Підтвердження замовлення": "Order confirmation",
    "Перевірте замовлення": "Review your order",
    "Контактні дані": "Contact details",
    "Розстрочка 0%%": "0%% installment",
    "Знижка (промокод)": "Discount (promo code)",
    "Бонуси": "Bonuses",
    "Назва міста...": "City name...",
    "Оплата карткою": "Card payment",
    "Миттєва розстрочка": "Instant installment",
    "Промокод і бонуси": "Promo code and bonuses",
    "Доступно бонусів:": "Available bonuses:",
    "Списати бонуси": "Redeem bonuses",
    "Максимум для цього замовлення:": "Maximum for this order:",
    "Увійдіть": "Sign in",
    ", щоб списати бонуси.": " to redeem bonuses.",
    "До сплати": "Amount due",
    "Очистити все": "Clear all",
    "Таблиця порівняння": "Comparison table",
    "Закрити чат": "Close chat",
    "Ваше повідомлення…": "Your message…",
    "Введіть повідомлення": "Enter a message",
    "Сповіщення": "Notifications",
    "Поточний баланс": "Current balance",
    "Історія нарахувань": "Accrual history",
    "Бонусних операцій ще немає.": "No bonus transactions yet.",
    "Відстежити": "Track",
    "Перехід до оплати": "Proceed to payment",
    "Перенаправлення...": "Redirecting...",
    "Перейти до оплати": "Go to payment",
    "Повернутись до вибору оплати": "Back to payment selection",
    "Замовлення №%(pk)s на суму": "Order #%(pk)s for",
    "Відділення:": "Branch:",
    "Індекс не знайдено. Перевірте правильність.": "Postcode not found. Please check and try again.",
    "Повідомлення чату": "Chat messages",
    "Помилка з'єднання. Спробуйте ще раз.": "Connection error. Please try again.",
    "Не вдалося отримати відповідь. Спробуйте пізніше.": "Could not get a response. Please try later.",
    "Помилка мережі. Перевірте підключення.": "Network error. Check your connection.",
    "Перевіряю сумісність…": "Checking compatibility…",
    "Помилка перевірки": "Check failed",
    "Помилка мережі": "Network error",
    "Розкажи детальніше про товар: __NAME__. Які характеристики важливі і чи підійде він для типових задач?": (
        "Tell me more about the product: __NAME__. "
        "What specs matter and is it suitable for typical tasks?"
    ),
    "Текст повідомлення": "Message text",
    "Зміна балансу": "Balance change",
    "Додатне значення — нарахування, від'ємне — списання.": (
        "Positive value — accrual, negative — deduction."
    ),
    "Обрано %(counter)s клієнта.": "%(counter)s customer selected.",
    "Обрано %(counter)s клієнтів.": "%(counter)s customers selected.",
    # Warranty / service centre (RMA)
    "Серійний номер": "Serial number",
    "Серійні номери": "Serial numbers",
    "Оформлення гарантії": "Warranty registration",
    "Розділи сервісу": "Service sections",
    "Заявки на сервіс": "Service requests",
    "Заявки на гарантію": "Warranty claims",
    "Заявка на гарантію": "Warranty claim",
    "Створити нову заявку": "Create new request",
    "Серійний номер, RMA, товар...": "Serial number, RMA, product...",
    "Заявок ще немає.": "No requests yet.",
    "Створення заявки": "Create request",
    "Заповнити по СН": "Fill by serial number",
    "Знайти продаж": "Find sale",
    "Пошук товару": "Search product",
    "Без серійного номера": "Without serial number",
    "Чернетка": "Draft",
    "Відправлена": "Submitted",
    "В обробці": "In progress",
    "Завершена": "Completed",
    "№ RMA": "RMA No.",
    "Гарантійний": "Under warranty",
    "Опис дефекту": "Defect description",
    "ПІБ клієнта": "Customer full name",
    "Телефон клієнта": "Customer phone",
    "Email клієнта": "Customer email",
    "Адреса клієнта": "Customer address",
    "Номер накладної СД": "Carrier waybill number",
    "Дата накладної СД": "Carrier waybill date",
    "Створив": "Created by",
    "Запис серійного номера": "Serial number record",
    "Дата відправки": "Submitted at",
    "Товар гарантійний": "Product under warranty",
    "Гарантія закінчилась": "Warranty expired",
    "Вкажіть серійний номер або позначте «Без серійного номера».": (
        "Enter a serial number or check «Without serial number»."
    ),
    "Оберіть або вкажіть товар.": "Select or enter a product.",
    "Опишіть дефект.": "Describe the defect.",
    "Заповніть усі поля клієнта¹.": "Fill in all customer fields¹.",
    "Заповніть усі поля доставки².": "Fill in all delivery fields².",
    "Зберегти": "Save",
    "Відправити": "Submit",
    "Дані клієнта": "Customer details",
    "Доставка до СЦ": "Delivery to service centre",
    "— оберіть —": "— select —",
    "(макс. 60 символів)": "(max. 60 characters)",
    "(макс. 250 символів)": "(max. 250 characters)",
    "дане поле необхідно заповнити, якщо товар на сервіс передає фіз. особа, якій його було продано": (
        "required if the product is handed in for service by the individual it was sold to"
    ),
    "дане поле необхідно заповнити, якщо товар відправляється до сервісного центру службою доставки": (
        "required if the product is shipped to the service centre via a delivery service"
    ),
    "Інформація про гарантію": "Warranty information",
    "Цей розділ доступний лише співробітникам магазину. Увійдіть під обліковим записом персоналу або зверніться до адміністратора.": (
        "This section is available to store staff only. Sign in with a staff account or contact an administrator."
    ),
    "Серійний номер не знайдено в реєстрі. Додайте його в адмінці (Серійні номери) або виконайте sync_brain_serials.": (
        "Serial number not found in the registry. Add it in the admin (Serial numbers) or run sync_brain_serials."
    ),
    "Дані продажу підставлено": "Sale data filled in",
    "Поля заповнено за серійним номером": "Fields filled from serial number",
    "Серійний номер не знайдено в реєстрі": "Serial number not found in the registry",
    "Помилка конфігурації форми. Перезавантажте сторінку.": "Form configuration error. Reload the page.",
    "Спочатку введіть серійний номер": "Enter a serial number first",
    "Немає доступу. Увійдіть як співробітник (staff).": "Access denied. Sign in as staff.",
    "Помилка пошуку": "Lookup error",
    "Товар обрано": "Product selected",
    "Вручну": "Manual",
    "Назва товару": "Product name",
    "Код товару": "Product code",
    "Документ продажу": "Sale document",
    "Дата продажу": "Sale date",
    "Гарантія до": "Warranty until",
    "Джерело": "Source",
    "ID замовлення Brain": "Brain order ID",
    "Примітки": "Notes",
    "Інша": "Other",
    "RMA": "RMA",
    "Дефект": "Defect",
    "Клієнт¹": "Customer¹",
    "Доставка²": "Delivery²",
    "Службове": "Internal",
    # Missing / fuzzy UI strings (site-wide audit)
    "LLM_API_KEY не налаштовано в .env — додайте ключ OpenAI-сумісного API.": (
        "LLM_API_KEY is not configured in .env — add an OpenAI-compatible API key."
    ),
    "Надіслано: %(sent)d. Без Telegram ID або з помилкою: %(skipped)d.": (
        "Sent: %(sent)d. Missing Telegram ID or failed: %(skipped)d."
    ),
    "Мінімум 8 символів.": "At least 8 characters.",
    "Рекомендований розмір зображення": "Recommended image size",
    "Для обраної кількості колонок": "For the selected number of columns",
    "Підказка для головної": "Home page hint",
    "Розмір для головної": "Home page size",
    "Рекомендований розмір": "Recommended size",
    "колонки": "columns",
    "Кількість банерів у рядку": "Banners per row",
    "Скільки рекламних зображень показувати одночасно на головній сторінці (десктоп).": (
        "How many ad images to show at once on the home page (desktop)."
    ),
    "Переглянути банери для головної": "View home page banners",
    "Додати банер": "Add banner",
    "зараз на головній": "currently on home page",
    "Реклама на головній": "Home page advertising",
    "Товар і продаж": "Product and sale",
    "Гарантія, міс": "Warranty, months",
    "Каталог товарів": "Product catalog",
    "Навігація банерів": "Banner navigation",
    "Вихід з акаунту": "Sign out",
    "Ні": "No",
    "Так": "Yes",
    "Показати пароль": "Show password",
    "Приховати пароль": "Hide password",
    "Не вдалося зареєструватись. Перевірте поля форми.": (
        "Registration failed. Please check the form fields."
    ),
    "Товарів не знайдено": "No products found",
    "Помилка мережі. Спробуйте ще раз.": "Network error. Please try again.",
    "Увійдіть або зареєструйтесь, щоб залишити відгук.": (
        "Sign in or register to leave a review."
    ),
    "Створіть акаунт, щоб залишити відгук про товар.": (
        "Create an account to review this product."
    ),
    "Відгуки можуть залишати лише зареєстровані користувачі.": (
        "Only registered users can leave reviews."
    ),
    "Будь ласка, заповніть всі поля": "Please fill in all fields",
    "Інше": "Other",
    "Brain API": "Brain API",
    "Реклама": "Advertising",
    "Вийти": "Sign out",
    "Українська": "Ukrainian",
    "Помилка сервера — СвітПК": "Server error — SvitPC",
    "Помилка сервера": "Server error",
    "Вибачте, виникла помилка. Ми вже працюємо над її виправленням.": (
        "Sorry, something went wrong. We are already working on a fix."
    ),
    "СвітПК — повідомлення": "SvitPC — notification",
    "СвітПК — замовлення прийнято": "SvitPC — order received",
    "Замовлення №%(pk)s успішно оформлено": "Order #%(pk)s placed successfully",
    "СвітПК — статус замовлення": "SvitPC — order status",
    "Замовлення №%(pk)s: %(status)s": "Order #%(pk)s: %(status)s",
    "СвітПК — акція!": "SvitPC — promotion!",
    "Невірний формат product_ids": "Invalid product_ids format",
    "Потрібно як мінімум 2 товари": "At least 2 products required",
    # Email / SMS (transactional)
    "Замовлення прийнято": "Order received",
    "Дякуємо за замовлення #%(order)s": "Thank you for order #%(order)s",
    "Шановний(а) %(name)s!": "Dear %(name)s!",
    "Ми отримали ваше замовлення і вже обробляємо його.": (
        "We have received your order and are processing it."
    ),
    "Сума:": "Total:",
    "Оплата:": "Payment:",
    "Переглянути замовлення на сайті": "View order on the website",
    "СвітПК — комп'ютерна техніка та електроніка": "SvitPC — computers and electronics",
    "СвітПК — замовлення #%(pk)s прийнято": "SvitPC — order #%(pk)s received",
    "Статус замовлення змінено": "Order status updated",
    "Статус вашого замовлення змінено на:": "Your order status has been updated to:",
    "ТТН для відстеження:": "Tracking number:",
    "Штрихкод відправлення:": "Shipment barcode:",
    "Деталі замовлення на сайті": "Order details on the website",
    "СвітПК — замовлення #%(pk)s: %(status)s": "SvitPC — order #%(pk)s: %(status)s",
    "Замовлення доставлено": "Order delivered",
    "Замовлення #%(pk)s доставлено!": "Order #%(pk)s has been delivered!",
    "Ваше замовлення вже чекає на вас у відділенні.": (
        "Your order is waiting for you at the branch."
    ),
    "Дякуємо за покупку в СвітПК!": "Thank you for shopping at SvitPC!",
    "СвітПК — ваше замовлення #%(pk)s доставлено": "SvitPC — your order #%(pk)s has been delivered",
    "ТТН створено": "Tracking number created",
    "Замовлення #%(pk)s передано на доставку": "Order #%(pk)s handed over for delivery",
    "Ваше замовлення передано службі доставки.": (
        "Your order has been handed over to the delivery service."
    ),
    "Місто:": "City:",
    "Сума замовлення:": "Order total:",
    "Відслідкувати посилку:": "Track your parcel:",
    "СвітПК — ТТН створено для замовлення #%(pk)s": "SvitPC — tracking number created for order #%(pk)s",
    "Вітаємо з Днем народження!": "Happy birthday!",
    "Подарунок від нас:": "A gift from us:",
    "Ваш промокод на 10%% знижку:": "Your 10%% discount promo code:",
    "Дійсний до:": "Valid until:",
    "Бонусів нараховано:": "Bonuses credited:",
    "Введіть промокод при оформленні замовлення.": "Enter the promo code at checkout.",
    "СвітПК вітає з Днем народження, %(name)s!": "Happy birthday from SvitPC, %(name)s!",
    "English": "English",
    "\n          Чи точно ви хочете вийти з акаунту %(account)s?\n        ": (
        "\n          Are you sure you want to sign out of %(account)s?\n        "
    ),
    "Замовлення #%(order_id)s": "Order #%(order_id)s",
    "Ваше замовлення передано в доставку %(delivery)s.": (
        "Your order has been handed over for delivery via %(delivery)s."
    ),
    "Команда СвітПК щиро вітає вас із цим особливим днем і бажає здоров'я, успіхів та нових технологічних знахідок!": (
        "The SvitPC team wishes you health, success and great tech finds on your special day!"
    ),
    "Введіть промокод при оформленні замовлення на svitpc.ua": (
        "Enter the promo code at checkout on svitpc.ua"
    ),
    "Якщо ви не хочете отримувати подібні листи — оновіть налаштування в особистому кабінеті.": (
        "To stop receiving emails like this, update your preferences in your account."
    ),
    "СвітПК — комп'ютерна техніка та електроніка.": "SvitPC — computers and electronics.",
    "Команда СвітПК вітає вас із цим святом!": "The SvitPC team celebrates with you!",
    "Ваш подарунок:": "Your gift:",
    "На ваш бонусний рахунок нараховано +%(bonus)s грн": "%(bonus)s UAH credited to your bonus balance",
    "Скористайтесь на svitpc.ua": "Use it at svitpc.ua",
    "СвітПК: замовлення #%(pk)s — «%(status)s». %(url)s%(order_url)s": (
        "SvitPC: order #%(pk)s — «%(status)s». %(url)s%(order_url)s"
    ),
    "СвітПК: Замовлення №%(pk)s передано (%(delivery)s). ТТН: %(ttn)s.": (
        "SvitPC: Order #%(pk)s shipped (%(delivery)s). Tracking: %(ttn)s."
    ),
    "СвітПК: замовлення #%(pk)s — «%(status)s».": "SvitPC: order #%(pk)s — «%(status)s».",
    "ТТН: %(ttn)s.": "Tracking: %(ttn)s.",
    "Служба доставки": "Delivery service",
    "З Днем народження, %(name)s!": "Happy birthday, %(name)s!",
    "грн": "UAH",
    "Дякуємо за замовлення #%(order_id)s": "Thank you for order #%(order_id)s",
    "Замовлення #%(order_id)s доставлено!": "Order #%(order_id)s has been delivered!",
    "Замовлення #%(order_id)s передано на доставку": "Order #%(order_id)s handed over for delivery",
    "Доступ обмежено": "Access restricted",
}


def _escape_po(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _format_msgstr(value: str) -> str:
    if "\n" in value:
        parts = value.split("\n")
        lines = ['msgstr ""']
        for part in parts:
            lines.append(f'"{_escape_po(part)}\\n"')
        return "\n".join(lines)
    return f'msgstr "{_escape_po(value)}"'


def main() -> None:
    po_path = Path("locale/en/LC_MESSAGES/django.po")
    text = po_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    updated = 0
    unfuzzied = 0

    while i < len(lines):
        line = lines[i]
        if line.startswith("#, fuzzy"):
            block_start = len(out)
            block: list[str] = [line]
            i += 1
            while i < len(lines) and not lines[i].startswith("msgid "):
                block.append(lines[i])
                i += 1
            msgid_lines = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                msgid_lines.append(lines[i])
                i += 1
            msgstr_lines = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                msgstr_lines.append(lines[i])
                i += 1

            msgid = "".join(re.findall(r'"(.*)"', "".join(msgid_lines)))
            if msgid in TRANSLATIONS:
                out.extend(block[1:])  # drop fuzzy comment + #| lines
                out.extend(msgid_lines)
                out.append(_format_msgstr(TRANSLATIONS[msgid]) + "\n")
                updated += 1
                unfuzzied += 1
            else:
                out.extend(block)
                out.extend(msgid_lines)
                out.extend(msgstr_lines)
            continue

        if line.startswith('msgid "') and line != 'msgid ""\n':
            msgid_lines = [line]
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                msgid_lines.append(lines[i])
                i += 1
            msgstr_lines = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                msgstr_lines.append(lines[i])
                i += 1

            msgid = "".join(re.findall(r'"(.*)"', "".join(msgid_lines)))
            msgstr = "".join(re.findall(r'"(.*)"', "".join(msgstr_lines)))
            if not msgstr and msgid in TRANSLATIONS:
                out.extend(msgid_lines)
                out.append(_format_msgstr(TRANSLATIONS[msgid]) + "\n")
                updated += 1
            else:
                out.extend(msgid_lines)
                out.extend(msgstr_lines)
            continue

        out.append(line)
        i += 1

    po_path.write_text("".join(out), encoding="utf-8")
    print(f"Updated {updated} translations, removed fuzzy flag from {unfuzzied} entries.")


if __name__ == "__main__":
    main()
