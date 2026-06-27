from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_setting, get_channels, get_active_tasks, get_prices

PLATFORM_DISPLAY = {"yandex": "Яндекс Карты", "2gis": "2ГИС", "google": "Гугл Карты", "avito": "Авито"}

def back_kb(cb="back_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=cb)]])

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])

# ── Main menu ──────────────────────────────────────────
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_setting("btn_post","📝 Выложить задание"), callback_data="post_task")],
        [InlineKeyboardButton(get_setting("btn_stats","📊 Статистика"), callback_data="stats")],
        [InlineKeyboardButton(get_setting("btn_delete","🗑 Удалить задание"), callback_data="delete_task_menu")],
    ])

# ── Platform ───────────────────────────────────────────
def platform_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_setting("btn_yandex","🗺 Яндекс Карты"), callback_data="platform_yandex"),
         InlineKeyboardButton(get_setting("btn_2gis","🗺 2ГИС"), callback_data="platform_2gis")],
        [InlineKeyboardButton(get_setting("btn_google","🗺 Гугл Карты"), callback_data="platform_google"),
         InlineKeyboardButton(get_setting("btn_avito","🛍 Авито"), callback_data="platform_avito")],
        [InlineKeyboardButton(get_setting("btn_other","✏️ Другое"), callback_data="platform_other")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ])

# ── Price selection ────────────────────────────────────
def price_kb(platform_key):
    prices = get_prices(platform_key)
    buttons = []
    row = []
    for i, p in enumerate(prices):
        row.append(InlineKeyboardButton(p, callback_data=f"price_{p}"))
        if len(row) == 2:
            buttons.append(row); row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)

# ── Channel post buttons ───────────────────────────────
def channel_post_kb(author_username):
    contact = get_setting("ch_btn_contact", "Написать")
    payment = get_setting("ch_btn_payment", "Выплаты")
    learn   = get_setting("ch_btn_learn",   "Обучение")
    pay_url = get_setting("link_payment", "")
    lrn_url = get_setting("link_learn",   "")
    buttons = [[InlineKeyboardButton(contact, url=f"https://t.me/{author_username}")]]
    row2 = []
    if pay_url: row2.append(InlineKeyboardButton(payment, url=pay_url))
    if lrn_url: row2.append(InlineKeyboardButton(learn,   url=lrn_url))
    if row2: buttons.append(row2)
    return InlineKeyboardMarkup(buttons)

# ── Confirm / autodel ──────────────────────────────────
def confirm_post_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Выложить задание", callback_data="confirm_post")],
        [InlineKeyboardButton("❌ Отменить",         callback_data="cancel")],
    ])

def auto_delete_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("30 мин", callback_data="autodel_30"),
         InlineKeyboardButton("1 час",  callback_data="autodel_60"),
         InlineKeyboardButton("2 часа", callback_data="autodel_120")],
        [InlineKeyboardButton("6 часов",  callback_data="autodel_360"),
         InlineKeyboardButton("12 часов", callback_data="autodel_720"),
         InlineKeyboardButton("24 часа",  callback_data="autodel_1440")],
        [InlineKeyboardButton("🙋 Удалю сам", callback_data="autodel_manual")],
    ])

# ── Delete tasks list ──────────────────────────────────
def delete_tasks_kb(user_id):
    tasks = get_active_tasks(user_id)
    if not tasks: return None
    buttons = [[InlineKeyboardButton(f"#{t['id']} | {t['platform']} | {t['price']}", callback_data=f"do_delete_{t['id']}")] for t in tasks]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)

# ── Channel select ─────────────────────────────────────
def channel_select_kb():
    channels = get_channels()
    if not channels: return None
    buttons = [[InlineKeyboardButton(ch["channel_name"], callback_data=f"channel_{ch['channel_id']}")] for ch in channels]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)

# ══ ADMIN ═════════════════════════════════════════════

def admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Пользователи",    callback_data="adm_users"),
         InlineKeyboardButton("➕ Добавить",         callback_data="adm_add_user")],
        [InlineKeyboardButton("🗑 Удалить задание",  callback_data="adm_del_task"),
         InlineKeyboardButton("📢 Каналы",           callback_data="adm_channels")],
        [InlineKeyboardButton("💰 Цены платформ",   callback_data="adm_prices"),
         InlineKeyboardButton("🔤 Кнопки бота",      callback_data="adm_bot_buttons")],
        [InlineKeyboardButton("📋 Шаблоны текста",  callback_data="adm_templates"),
         InlineKeyboardButton("🔗 Ссылки кнопок",   callback_data="adm_links")],
        [InlineKeyboardButton("📨 Рассылка",         callback_data="adm_broadcast")],
        [InlineKeyboardButton("📊 Статистика",       callback_data="adm_stats")],
    ])

def admin_users_kb(users):
    buttons = []
    for u in users:
        status = "✅" if u["allowed"] else "🚫"
        name   = u["username"] or u["first_name"] or str(u["user_id"])
        buttons.append([InlineKeyboardButton(f"{status} @{name}", callback_data=f"adm_toggle_{u['user_id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_back")])
    return InlineKeyboardMarkup(buttons)

def admin_tasks_kb(tasks):
    buttons = []
    for t in tasks:
        uname = t.get("author_username") or "?"
        buttons.append([InlineKeyboardButton(f"#{t['id']} @{uname} | {t['platform']} | {t['price']}", callback_data=f"adm_close_{t['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_back")])
    return InlineKeyboardMarkup(buttons)

def admin_prices_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗺 Яндекс Карты", callback_data="adm_price_yandex")],
        [InlineKeyboardButton("🗺 2ГИС",          callback_data="adm_price_2gis")],
        [InlineKeyboardButton("🗺 Гугл Карты",    callback_data="adm_price_google")],
        [InlineKeyboardButton("🛍 Авито",          callback_data="adm_price_avito")],
        [InlineKeyboardButton("🔙 Назад",          callback_data="adm_back")],
    ])

def admin_bot_buttons_kb():
    items = [
        ("btn_post",   "Главная: Выложить"),
        ("btn_stats",  "Главная: Статистика"),
        ("btn_delete", "Главная: Удалить"),
        ("btn_yandex", "Платформа: Яндекс"),
        ("btn_2gis",   "Платформа: 2ГИС"),
        ("btn_google", "Платформа: Гугл"),
        ("btn_avito",  "Платформа: Авито"),
        ("btn_other",  "Платформа: Другое"),
    ]
    buttons = [[InlineKeyboardButton(label, callback_data=f"adm_btn_{key}")] for key, label in items]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_back")])
    return InlineKeyboardMarkup(buttons)

def admin_channel_buttons_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Название 'Написать'", callback_data="adm_btn_ch_btn_contact")],
        [InlineKeyboardButton("Название 'Выплаты'",  callback_data="adm_btn_ch_btn_payment")],
        [InlineKeyboardButton("Название 'Обучение'", callback_data="adm_btn_ch_btn_learn")],
        [InlineKeyboardButton("🔙 Назад",             callback_data="adm_back")],
    ])

def admin_links_kb():
    pay  = get_setting("link_payment","") or "не задана"
    lrn  = get_setting("link_learn",  "") or "не задана"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💳 Ссылка «Выплаты»",  callback_data="adm_link_payment")],
        [InlineKeyboardButton(f"📚 Ссылка «Обучение»", callback_data="adm_link_learn")],
        [InlineKeyboardButton("🔤 Названия кнопок канала", callback_data="adm_channel_buttons")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_back")],
    ])

def admin_templates_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Шаблон задания",  callback_data="adm_edit_template")],
        [InlineKeyboardButton("🔚 Шаблон закрытия", callback_data="adm_edit_closed_tpl")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_back")],
    ])

def broadcast_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Всем пользователям",       callback_data="adm_bc_all")],
        [InlineKeyboardButton("👤 Конкретному пользователю", callback_data="adm_bc_one")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_back")],
    ])

def admin_channels_kb():
    channels = get_channels()
    buttons  = [[InlineKeyboardButton(f"🗑 {ch['channel_name']}", callback_data=f"adm_delch_{ch['channel_id']}")] for ch in channels]
    buttons.append([InlineKeyboardButton("➕ Добавить канал", callback_data="adm_add_channel")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_back")])
    return InlineKeyboardMarkup(buttons)
