import os, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters, ContextTypes)
import database as db
from keyboards import (
    main_menu_kb, platform_kb, price_kb, confirm_post_kb, auto_delete_kb,
    delete_tasks_kb, channel_select_kb, channel_post_kb,
    admin_menu_kb, admin_users_kb, admin_tasks_kb, admin_prices_kb,
    admin_bot_buttons_kb, admin_channel_buttons_kb, admin_links_kb,
    admin_templates_kb, broadcast_kb, admin_channels_kb, back_kb, cancel_kb,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN      = os.environ["BOT_TOKEN"]
ADMIN_ID       = int(os.environ["ADMIN_ID"])
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "67FERTENK_BS67")

PLATFORM_DISPLAY = {"yandex": "Яндекс Карты", "2gis": "2ГИС",
                    "google": "Гугл Карты",    "avito": "Авито"}

def is_admin(uid): return uid == ADMIN_ID

def build_task_text(platform, price, description):
    return db.get_setting("task_template").format(
        platform=platform, price=price, description=description)

def build_closed_text():
    return db.get_setting("closed_template")

def fmt_min(m):
    if m < 60: return f"{m} мин"
    h = m // 60
    return f"{h} ч" if m % 60 == 0 else f"{h} ч {m%60} мин"

async def close_task_in_channel(ctx, task):
    try:
        await ctx.bot.edit_message_text(
            chat_id=task["channel_id"], message_id=task["message_id"],
            text=build_closed_text(), reply_markup=None)
    except Exception as e:
        logger.warning(f"Edit failed: {e}")
    db.close_task(task["id"])

# ════════════════════════════ COMMANDS ════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    if not db.is_allowed(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 У вас нет доступа.\nОбратитесь к администратору.")
        return
    ctx.user_data.clear()
    await update.message.reply_text(
        f"👋 Привет, *{user.first_name}*!\n\nВыберите действие:",
        parse_mode="Markdown", reply_markup=main_menu_kb())

async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    if is_admin(user.id):
        ctx.user_data["state"] = "wait_admin_pass"
        await update.message.reply_text("🔐 Введите пароль:")
    else:
        await update.message.reply_text("❌ Команда не найдена.")

# ════════════════════════════ CALLBACKS ═══════════════════════════

async def callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    data = q.data
    uid  = q.from_user.id

    # ── Navigation ──────────────────────────────────────
    if data == "back_main":
        ctx.user_data.clear()
        await q.edit_message_text("Выберите действие:", reply_markup=main_menu_kb())
        return
    if data == "cancel":
        ctx.user_data.clear()
        await q.edit_message_text("❌ Отменено.", reply_markup=main_menu_kb())
        return

    # ── Post task ───────────────────────────────────────
    if data == "post_task":
        if not db.is_allowed(uid) and not is_admin(uid):
            await q.edit_message_text("🚫 Нет доступа."); return
        if not db.get_channels():
            await q.edit_message_text("⚠️ Каналы не настроены. Обратитесь к администратору.",
                                      reply_markup=back_kb()); return
        await q.edit_message_text("📌 Выберите платформу:", reply_markup=platform_kb()); return

    if data.startswith("platform_"):
        key = data[len("platform_"):]
        if key == "other":
            ctx.user_data.update({"platform_key": "other", "state": "wait_platform_text"})
            await q.edit_message_text("✏️ Введите название платформы:", reply_markup=cancel_kb())
        else:
            display = PLATFORM_DISPLAY.get(key, key)
            ctx.user_data.update({"platform_key": key, "platform": display})
            await q.edit_message_text(
                f"📌 Платформа: *{display}*\n\n💰 Выберите оплату:",
                parse_mode="Markdown", reply_markup=price_kb(key))
        return

    if data.startswith("price_"):
        price = data[len("price_"):]
        ctx.user_data.update({"price": price, "state": "wait_description"})
        plat  = ctx.user_data.get("platform","—")
        await q.edit_message_text(
            f"📌 *{plat}* | 💰 *{price}*\n\n📝 Введите описание задания:",
            parse_mode="Markdown", reply_markup=cancel_kb()); return

    if data.startswith("channel_"):
        channel_id = data[len("channel_"):]
        ctx.user_data["selected_channel"] = channel_id
        plat = ctx.user_data.get("platform","—")
        price = ctx.user_data.get("price","—")
        desc  = ctx.user_data.get("description","—")
        preview = build_task_text(plat, price, desc)
        await q.edit_message_text(f"👁 *Предпросмотр:*\n\n{preview}",
                                  parse_mode="Markdown", reply_markup=confirm_post_kb()); return

    if data == "confirm_post":
        plat   = ctx.user_data.get("platform","—")
        price  = ctx.user_data.get("price","—")
        desc   = ctx.user_data.get("description","—")
        ch_id  = ctx.user_data.get("selected_channel")
        uname  = q.from_user.username
        if not uname:
            await q.edit_message_text(
                "⚠️ У вас нет username в Telegram.\n\nУстановите его: Настройки → Изменить профиль → Имя пользователя",
                reply_markup=back_kb()); return
        text = build_task_text(plat, price, desc)
        kb   = channel_post_kb(uname)
        try:
            msg = await ctx.bot.send_message(chat_id=ch_id, text=text, reply_markup=kb)
        except Exception as e:
            await q.edit_message_text(f"❌ Ошибка публикации: {e}\n\nПроверьте что бот — администратор канала.",
                                      reply_markup=back_kb()); return
        task_id = db.create_task(uid, uname, plat, price, desc, ch_id, msg.message_id)
        ctx.user_data["last_task_id"] = task_id
        ctx.user_data["state"] = "wait_autodel"
        await q.edit_message_text("✅ Задание опубликовано!\n\n⏱ Когда автоматически закрыть задание?",
                                  reply_markup=auto_delete_kb()); return

    if data.startswith("autodel_"):
        val     = data[len("autodel_"):]
        task_id = ctx.user_data.get("last_task_id")
        if task_id and val != "manual":
            mins   = int(val)
            auto_at = (datetime.utcnow() + timedelta(minutes=mins)).strftime("%Y-%m-%d %H:%M:%S")
            conn = db.get_conn()
            conn.execute("UPDATE tasks SET auto_delete_at=? WHERE id=?", (auto_at, task_id))
            conn.commit(); conn.close()
            await q.edit_message_text(f"⏰ Задание закроется через {fmt_min(mins)}.", reply_markup=back_kb())
        else:
            await q.edit_message_text("👌 Закроете вручную через «Удалить задание».", reply_markup=back_kb())
        ctx.user_data.clear(); return

    # ── Stats ───────────────────────────────────────────
    if data == "stats":
        tasks = db.get_active_tasks(uid)
        await q.edit_message_text(f"📊 *Ваша статистика*\n\n• Активных заданий: {len(tasks)}",
                                  parse_mode="Markdown", reply_markup=back_kb()); return

    # ── Delete task ─────────────────────────────────────
    if data == "delete_task_menu":
        kb = delete_tasks_kb(uid)
        if not kb:
            await q.edit_message_text("📭 Нет активных заданий.", reply_markup=back_kb()); return
        await q.edit_message_text("🗑 Выберите задание для закрытия:", reply_markup=kb); return

    if data.startswith("do_delete_"):
        task_id = int(data[len("do_delete_"):])
        task    = db.get_task(task_id)
        if task and task["user_id"] == uid and task["status"] == "active":
            await close_task_in_channel(ctx, task)
            await q.edit_message_text("✅ Задание закрыто.", reply_markup=back_kb())
        else:
            await q.edit_message_text("⚠️ Задание не найдено.", reply_markup=back_kb())
        return

    # ══════════════════════ ADMIN ══════════════════════

    if not is_admin(uid): return

    if data == "adm_back":
        await q.edit_message_text("🛠 *Панель администратора*", parse_mode="Markdown",
                                  reply_markup=admin_menu_kb()); return

    if data == "adm_stats":
        s = db.get_stats()
        await q.edit_message_text(
            f"📊 *Статистика*\n\n"
            f"👥 Всего пользователей: {s['total_users']}\n"
            f"✅ С доступом: {s['allowed_users']}\n"
            f"📋 Всего заданий: {s['total_tasks']}\n"
            f"🟢 Активных: {s['active_tasks']}",
            parse_mode="Markdown", reply_markup=back_kb("adm_back")); return

    if data == "adm_users":
        users = db.get_all_users()
        if not users:
            await q.edit_message_text("👥 Нет пользователей.", reply_markup=back_kb("adm_back")); return
        await q.edit_message_text("👥 *Пользователи*\nНажмите для смены доступа:",
                                  parse_mode="Markdown", reply_markup=admin_users_kb(users)); return

    if data.startswith("adm_toggle_"):
        target_id = int(data[len("adm_toggle_"):])
        users = db.get_all_users()
        target = next((u for u in users if u["user_id"] == target_id), None)
        if target: db.set_allowed(target_id, not target["allowed"])
        users = db.get_all_users()
        await q.edit_message_text("👥 *Пользователи*\nНажмите для смены доступа:",
                                  parse_mode="Markdown", reply_markup=admin_users_kb(users)); return

    if data == "adm_add_user":
        ctx.user_data["state"] = "wait_add_user"
        await q.edit_message_text("➕ Введите @username пользователя:",
                                  reply_markup=back_kb("adm_back")); return

    if data == "adm_del_task":
        tasks = db.get_all_active_tasks()
        if not tasks:
            await q.edit_message_text("📭 Нет активных заданий.", reply_markup=back_kb("adm_back")); return
        await q.edit_message_text("🗑 Выберите задание:", reply_markup=admin_tasks_kb(tasks)); return

    if data.startswith("adm_close_"):
        task_id = int(data[len("adm_close_"):])
        task    = db.get_task(task_id)
        if task and task["status"] == "active":
            await close_task_in_channel(ctx, task)
            await q.edit_message_text("✅ Задание закрыто.", reply_markup=back_kb("adm_back"))
        else:
            await q.edit_message_text("⚠️ Не найдено.", reply_markup=back_kb("adm_back"))
        return

    if data == "adm_channels":
        await q.edit_message_text("📢 *Каналы*", parse_mode="Markdown",
                                  reply_markup=admin_channels_kb()); return

    if data == "adm_add_channel":
        ctx.user_data["state"] = "wait_add_channel_id"
        await q.edit_message_text("📢 Введите ID канала (например: `-1001234567890`):",
                                  reply_markup=back_kb("adm_back")); return

    if data.startswith("adm_delch_"):
        ch_id = data[len("adm_delch_"):]
        db.delete_channel(ch_id)
        await q.edit_message_text("✅ Канал удалён.", reply_markup=admin_channels_kb()); return

    if data == "adm_prices":
        await q.edit_message_text("💰 *Цены платформ*\nВыберите платформу:",
                                  parse_mode="Markdown", reply_markup=admin_prices_kb()); return

    if data.startswith("adm_price_"):
        key     = data[len("adm_price_"):]
        current = db.get_setting(f"prices_{key}", "")
        display = PLATFORM_DISPLAY.get(key, key)
        ctx.user_data.update({"state": "wait_edit_price", "edit_price_key": key})
        await q.edit_message_text(
            f"💰 *{display}*\n\nТекущие цены: `{current}`\n\n"
            "Введите новые цены через запятую:\n_Пример: 100₽,200₽,300₽_",
            parse_mode="Markdown", reply_markup=back_kb("adm_back")); return

    if data == "adm_bot_buttons":
        await q.edit_message_text("🔤 *Кнопки бота*:", parse_mode="Markdown",
                                  reply_markup=admin_bot_buttons_kb()); return

    if data == "adm_channel_buttons":
        await q.edit_message_text("🔤 *Кнопки канала*:", parse_mode="Markdown",
                                  reply_markup=admin_channel_buttons_kb()); return

    if data.startswith("adm_btn_"):
        key     = data[len("adm_btn_"):]
        current = db.get_setting(key, "")
        ctx.user_data.update({"state": "wait_edit_btn", "edit_btn_key": key})
        await q.edit_message_text(f"✏️ Текущий текст: *{current}*\n\nВведите новый:",
                                  parse_mode="Markdown", reply_markup=back_kb("adm_back")); return

    if data == "adm_links":
        pay = db.get_setting("link_payment","") or "не задана"
        lrn = db.get_setting("link_learn","")   or "не задана"
        await q.edit_message_text(
            f"🔗 *Ссылки кнопок канала*\n\n💳 Выплаты: `{pay}`\n📚 Обучение: `{lrn}`",
            parse_mode="Markdown", reply_markup=admin_links_kb()); return

    if data == "adm_link_payment":
        ctx.user_data.update({"state": "wait_edit_link", "edit_link_key": "link_payment"})
        await q.edit_message_text("💳 Введите ссылку для кнопки *Выплаты*:",
                                  parse_mode="Markdown", reply_markup=back_kb("adm_back")); return

    if data == "adm_link_learn":
        ctx.user_data.update({"state": "wait_edit_link", "edit_link_key": "link_learn"})
        await q.edit_message_text("📚 Введите ссылку для кнопки *Обучение*:",
                                  parse_mode="Markdown", reply_markup=back_kb("adm_back")); return

    if data == "adm_templates":
        await q.edit_message_text("📋 *Шаблоны текста*", parse_mode="Markdown",
                                  reply_markup=admin_templates_kb()); return

    if data == "adm_edit_template":
        current = db.get_setting("task_template","")
        ctx.user_data["state"] = "wait_edit_template"
        await q.edit_message_text(
            f"📝 *Текущий шаблон:*\n\n`{current}`\n\n"
            "Переменные: `{platform}` `{price}` `{description}`",
            parse_mode="Markdown", reply_markup=back_kb("adm_back")); return

    if data == "adm_edit_closed_tpl":
        current = db.get_setting("closed_template","")
        ctx.user_data["state"] = "wait_edit_closed_tpl"
        await q.edit_message_text(f"🔚 *Текущий шаблон закрытия:*\n\n`{current}`\n\nВведите новый текст:",
                                  parse_mode="Markdown", reply_markup=back_kb("adm_back")); return

    if data == "adm_broadcast":
        await q.edit_message_text("📨 *Рассылка* — выберите получателей:",
                                  parse_mode="Markdown", reply_markup=broadcast_kb()); return

    if data == "adm_bc_all":
        ctx.user_data["state"] = "wait_bc_msg_all"
        await q.edit_message_text("📨 Введите сообщение для *всех* пользователей:",
                                  parse_mode="Markdown", reply_markup=back_kb("adm_back")); return

    if data == "adm_bc_one":
        ctx.user_data["state"] = "wait_bc_username"
        await q.edit_message_text("👤 Введите @username получателя:",
                                  reply_markup=back_kb("adm_back")); return

# ════════════════════════════ MESSAGES ════════════════════════════

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    text  = (update.message.text or "").strip()
    state = ctx.user_data.get("state")

    # ── Admin password ──────────────────────────────────
    if state == "wait_admin_pass":
        if text == ADMIN_PASSWORD:
            ctx.user_data.clear()
            await update.message.reply_text("✅ *Добро пожаловать!*", parse_mode="Markdown",
                                            reply_markup=admin_menu_kb())
        else:
            ctx.user_data.clear()
            await update.message.reply_text("❌ Неверный пароль.")
        return

    if not db.is_allowed(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 Нет доступа."); return

    # ── Platform text (Другое) ──────────────────────────
    if state == "wait_platform_text":
        ctx.user_data.update({"platform": text, "state": "wait_price_text"})
        await update.message.reply_text(f"✅ Платформа: *{text}*\n\n💰 Введите цену:",
                                        parse_mode="Markdown", reply_markup=cancel_kb()); return

    if state == "wait_price_text":
        ctx.user_data.update({"price": text, "state": "wait_description"})
        plat = ctx.user_data.get("platform","—")
        await update.message.reply_text(f"📌 *{plat}* | 💰 *{text}*\n\n📝 Введите описание:",
                                        parse_mode="Markdown", reply_markup=cancel_kb()); return

    # ── Description ─────────────────────────────────────
    if state == "wait_description":
        ctx.user_data["description"] = text
        channels = db.get_channels()
        plat  = ctx.user_data.get("platform","—")
        price = ctx.user_data.get("price","—")
        if len(channels) == 1:
            ctx.user_data["selected_channel"] = channels[0]["channel_id"]
            preview = build_task_text(plat, price, text)
            await update.message.reply_text(f"👁 *Предпросмотр:*\n\n{preview}",
                                            parse_mode="Markdown", reply_markup=confirm_post_kb())
        else:
            await update.message.reply_text("📢 Выберите канал:", reply_markup=channel_select_kb())
        return

    # ── Admin: add user ─────────────────────────────────
    if state == "wait_add_user":
        if not is_admin(user.id): return
        uname = text.lstrip("@")
        db.add_user_by_username(uname)
        ctx.user_data.clear()
        await update.message.reply_text(f"✅ @{uname} добавлен и получил доступ.",
                                        reply_markup=admin_menu_kb()); return

    # ── Admin: add channel ──────────────────────────────
    if state == "wait_add_channel_id":
        if not is_admin(user.id): return
        ctx.user_data.update({"new_channel_id": text, "state": "wait_add_channel_name"})
        await update.message.reply_text("✏️ Введите название канала:"); return

    if state == "wait_add_channel_name":
        if not is_admin(user.id): return
        ch_id = ctx.user_data.get("new_channel_id")
        db.add_channel(ch_id, text)
        ctx.user_data.clear()
        await update.message.reply_text(f"✅ Канал «{text}» добавлен.",
                                        reply_markup=admin_menu_kb()); return

    # ── Admin: edit prices ──────────────────────────────
    if state == "wait_edit_price":
        if not is_admin(user.id): return
        key = ctx.user_data.get("edit_price_key")
        db.set_setting(f"prices_{key}", text)
        display = PLATFORM_DISPLAY.get(key, key)
        ctx.user_data.clear()
        await update.message.reply_text(f"✅ Цены для *{display}*: `{text}`",
                                        parse_mode="Markdown", reply_markup=admin_menu_kb()); return

    # ── Admin: edit button text ─────────────────────────
    if state == "wait_edit_btn":
        if not is_admin(user.id): return
        key = ctx.user_data.get("edit_btn_key")
        db.set_setting(key, text)
        ctx.user_data.clear()
        await update.message.reply_text(f"✅ Кнопка обновлена: *{text}*",
                                        parse_mode="Markdown", reply_markup=admin_menu_kb()); return

    # ── Admin: edit link ────────────────────────────────
    if state == "wait_edit_link":
        if not is_admin(user.id): return
        key = ctx.user_data.get("edit_link_key")
        db.set_setting(key, text)
        label = "Выплаты" if key == "link_payment" else "Обучение"
        ctx.user_data.clear()
        await update.message.reply_text(f"✅ Ссылка «{label}» обновлена.",
                                        reply_markup=admin_menu_kb()); return

    # ── Admin: edit templates ───────────────────────────
    if state == "wait_edit_template":
        if not is_admin(user.id): return
        db.set_setting("task_template", text)
        ctx.user_data.clear()
        await update.message.reply_text("✅ Шаблон задания обновлён.", reply_markup=admin_menu_kb()); return

    if state == "wait_edit_closed_tpl":
        if not is_admin(user.id): return
        db.set_setting("closed_template", text)
        ctx.user_data.clear()
        await update.message.reply_text("✅ Шаблон закрытия обновлён.", reply_markup=admin_menu_kb()); return

    # ── Admin: broadcast all ────────────────────────────
    if state == "wait_bc_msg_all":
        if not is_admin(user.id): return
        users = db.get_allowed_users()
        sent = failed = 0
        for u in users:
            try:
                await ctx.bot.send_message(chat_id=u["user_id"], text=f"📢 {text}")
                sent += 1
            except:
                failed += 1
        ctx.user_data.clear()
        await update.message.reply_text(
            f"✅ Рассылка завершена!\n✉️ Отправлено: {sent}\n❌ Ошибок: {failed}",
            reply_markup=admin_menu_kb()); return

    if state == "wait_bc_username":
        if not is_admin(user.id): return
        ctx.user_data.update({"bc_target": text.lstrip("@"), "state": "wait_bc_msg_one"})
        await update.message.reply_text(f"✉️ Введите сообщение для @{text.lstrip('@')}:"); return

    if state == "wait_bc_msg_one":
        if not is_admin(user.id): return
        target_uname = ctx.user_data.get("bc_target")
        target = db.get_user_by_username(target_uname)
        if target and target.get("user_id") and target["user_id"] > 0:
            try:
                await ctx.bot.send_message(chat_id=target["user_id"], text=f"📢 {text}")
                await update.message.reply_text(f"✅ Сообщение отправлено @{target_uname}.",
                                                reply_markup=admin_menu_kb())
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=admin_menu_kb())
        else:
            await update.message.reply_text(
                f"⚠️ @{target_uname} не найден или не запускал бота.",
                reply_markup=admin_menu_kb())
        ctx.user_data.clear(); return

    await update.message.reply_text("Используйте кнопки меню ↓", reply_markup=main_menu_kb())

# ════════════════════════ AUTO-DELETE JOB ═════════════════════════

async def auto_delete_job(context: ContextTypes.DEFAULT_TYPE):
    for task in db.get_tasks_to_auto_delete():
        logger.info(f"Auto-closing task #{task['id']}")
        await close_task_in_channel(context, task)

# ═════════════════════════════ MAIN ══════════════════════════════

def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.job_queue.run_repeating(auto_delete_job, interval=60, first=10)
    logger.info("Bot started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
