import os, logging
from datetime import datetime, timedelta
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice)
from telegram.ext import (Application, CommandHandler, MessageHandler, PreCheckoutQueryHandler,
                          CallbackQueryHandler, filters, ContextTypes)
import database as db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN      = os.environ["BOT_TOKEN"]
ADMIN_ID       = int(os.environ["ADMIN_ID"])
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "67cc67")
STARS_PRICE    = 30
TRIAL_DAYS     = 1

def is_admin(uid): return uid == ADMIN_ID

def has_access(user_id):
    if is_admin(user_id): return True
    user = db.get_user(user_id)
    if not user: return False
    if user["subscription"] in ("forever", "free"): return True
    if user["subscription"] == "trial" and user["trial_start"]:
        end = datetime.fromisoformat(user["trial_start"]) + timedelta(days=TRIAL_DAYS)
        return datetime.now() < end
    return False

def get_status_text(user_id):
    if is_admin(user_id): return "👑 Администратор"
    user = db.get_user(user_id)
    if not user: return "❌ Нет доступа"
    if user["subscription"] == "forever": return "✅ Вечная подписка"
    if user["subscription"] == "free":    return "🎁 Бесплатный доступ"
    if user["subscription"] == "trial" and user["trial_start"]:
        end  = datetime.fromisoformat(user["trial_start"]) + timedelta(days=TRIAL_DAYS)
        left = max(0, int((end - datetime.now()).total_seconds() / 3600))
        return f"⏱ Пробный период — осталось {left} ч"
    return "❌ Нет доступа"

# ── Keyboards ──────────────────────────────────────────

def main_kb(user_id):
    if has_access(user_id):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔇 Мои муты",        callback_data="my_mutes"),
             InlineKeyboardButton("⚠️ Варны",            callback_data="my_warns")],
            [InlineKeyboardButton("📖 Команды",          callback_data="commands")],
            [InlineKeyboardButton("👤 Профиль",          callback_data="profile")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⭐ Купить доступ ({STARS_PRICE} звёзд)", callback_data="buy")],
        [InlineKeyboardButton("🎁 Пробный период (1 день)",              callback_data="trial")],
    ])

def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Пользователи",  callback_data="adm_users"),
         InlineKeyboardButton("📊 Статистика",    callback_data="adm_stats")],
        [InlineKeyboardButton("🎁 Выдать доступ", callback_data="adm_give")],
    ])

def back_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]])

# ── Commands ───────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)
    ctx.user_data.clear()
    if has_access(user.id):
        await update.message.reply_text(
            f"👋 Привет, *{user.first_name}*!\n\n"
            f"Статус: {get_status_text(user.id)}\n\n"
            "Бот активен. Подключи через:\n"
            "*Настройки → Telegram Business → Чат-боты*\n\n"
            "Затем пиши команды прямо в чате с собеседником.",
            parse_mode="Markdown", reply_markup=main_kb(user.id))
    else:
        await update.message.reply_text(
            "👋 Привет!\n\n"
            "*SIALENS* — бот для управления личными чатами.\n\n"
            "После подключения через Telegram Business ты сможешь:\n"
            "🔇 Мутить собеседников\n"
            "⚠️ Выдавать предупреждения\n"
            "📊 Смотреть статус\n\n"
            "Выбери вариант доступа:",
            parse_mode="Markdown", reply_markup=main_kb(user.id))

async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Команда не найдена."); return
    ctx.user_data["state"] = "wait_admin_pass"
    await update.message.reply_text("🔐 Введите пароль:")

# ── Callbacks ──────────────────────────────────────────

async def cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    uid  = q.from_user.id
    data = q.data

    if data == "back":
        await q.edit_message_text("Выберите действие:", reply_markup=main_kb(uid)); return

    if data == "buy":
        await q.answer()
        await ctx.bot.send_invoice(
            chat_id=uid,
            title="⭐ Вечная подписка SIALENS",
            description="Полный доступ ко всем функциям навсегда",
            payload="buy_forever",
            currency="XTR",
            prices=[LabeledPrice("Вечная подписка", STARS_PRICE)])
        return

    if data == "trial":
        user = db.get_user(uid)
        if user and user.get("had_trial"):
            await q.edit_message_text("❌ Пробный период уже был использован.", reply_markup=main_kb(uid)); return
        db.set_trial(uid)
        await q.edit_message_text(
            "✅ *Пробный период активирован!*\n\n"
            "У тебя есть 1 день.\n\n"
            "Подключи бота:\n*Настройки → Telegram Business → Чат-боты*\n\n"
            "Затем открой любой чат и пиши команды.",
            parse_mode="Markdown", reply_markup=main_kb(uid)); return

    if data == "profile":
        mutes = db.get_user_mutes_count(uid)
        warns = db.get_user_warns_count(uid)
        await q.edit_message_text(
            f"👤 *Профиль*\n\n"
            f"Статус: {get_status_text(uid)}\n"
            f"🔇 Активных мутов: {mutes}\n"
            f"⚠️ Выданных варнов: {warns}",
            parse_mode="Markdown", reply_markup=back_kb()); return

    if data == "commands":
        await q.edit_message_text(
            "📖 *Команды*\n\n"
            "Пиши в личном чате с собеседником:\n\n"
            "`.mute` — замутить\n"
            "_Сообщения собеседника будут удаляться, ему придёт уведомление что он в муте_\n\n"
            "`.unmute` — размутить\n\n"
            "`.warn` — предупреждение\n"
            "_3 варна — уведомление о блокировке_\n\n"
            "`.warns` — варны собеседника\n\n"
            "`.status` — статус собеседника",
            parse_mode="Markdown", reply_markup=back_kb()); return

    if data == "my_mutes":
        mutes = db.get_mutes(uid)
        text  = "🔇 *Активные муты:*\n\n" if mutes else "🔇 Нет активных мутов."
        for m in mutes:
            text += f"• @{m['muted_username'] or m['muted_user_id']}\n"
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb()); return

    if data == "my_warns":
        warns = db.get_all_warns(uid)
        text  = "⚠️ *Предупреждения:*\n\n" if warns else "⚠️ Нет предупреждений."
        for w in warns:
            text += f"• @{w['warned_username'] or w['warned_user_id']}: {w['count']}/3\n"
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb()); return

    # ── Admin ──────────────────────────────────────────
    if not is_admin(uid): return

    if data == "adm_stats":
        s = db.get_stats()
        await q.edit_message_text(
            f"📊 *Статистика*\n\n"
            f"👥 Всего пользователей: {s['total']}\n"
            f"✅ Вечная подписка: {s['subscribed']}\n"
            f"⏱ Пробный период: {s['trial']}\n"
            f"🎁 Бесплатный: {s['free']}",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="adm_back")]])); return

    if data == "adm_users":
        users = db.get_all_users()
        text  = f"👥 *Пользователи* ({len(users)}):\n\n"
        for u in users[:30]:
            sub  = u['subscription'] or 'нет'
            name = u['username'] or u['first_name'] or str(u['user_id'])
            text += f"• @{name} — {sub}\n"
        await q.edit_message_text(text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 Выдать доступ", callback_data="adm_give")],
                [InlineKeyboardButton("🔙 Назад", callback_data="adm_back")]])); return

    if data == "adm_give":
        ctx.user_data["state"] = "wait_give_user"
        await q.edit_message_text(
            "👤 Введите @username пользователя:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="adm_back")]])); return

    if data == "adm_back":
        await q.edit_message_text("🛠 *Админ-панель*", parse_mode="Markdown", reply_markup=admin_kb()); return

# ── Payments ───────────────────────────────────────────

async def precheckout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def payment_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid     = update.effective_user.id
    payload = update.message.successful_payment.invoice_payload
    if payload == "buy_forever":
        db.set_subscription(uid, "forever")
        await update.message.reply_text(
            "✅ *Оплата получена! Вечный доступ активирован.*\n\n"
            "Подключи бота:\n*Настройки → Telegram Business → Чат-боты*",
            parse_mode="Markdown", reply_markup=main_kb(uid))

# ── Business messages ──────────────────────────────────

async def handle_business(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.business_message
    if not msg: return

    try:
        conn     = await ctx.bot.get_business_connection(msg.business_connection_id)
        owner_id = conn.user.id
        conn_id  = msg.business_connection_id
    except Exception as e:
        logger.warning(f"Business connection error: {e}"); return

    if not has_access(owner_id): return

    text    = (msg.text or "").strip()
    chat_id = msg.chat.id
    sender  = msg.from_user

    # Commands from owner
    if sender and sender.id == owner_id:
        peer     = msg.chat
        peer_id  = peer.id
        peer_name = peer.username or peer.first_name or str(peer_id)

        async def del_cmd():
            try: await ctx.bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
            except: pass

        async def notify(text):
            await ctx.bot.send_message(chat_id=owner_id, text=text)

        if text == ".mute":
            db.add_mute(owner_id, peer_id, peer_name, conn_id)
            await del_cmd()
            await notify(f"🔇 @{peer_name} замучен.\nЕго сообщения будут удаляться.")
            return

        if text == ".unmute":
            db.remove_mute(owner_id, peer_id)
            await del_cmd()
            await notify(f"🔊 @{peer_name} размучен.")
            return

        if text == ".warn":
            count = db.add_warn(owner_id, peer_id, peer_name)
            await del_cmd()
            if count >= 3:
                await notify(f"⛔ @{peer_name} — 3/3 предупреждения!\nРекомендуем заблокировать вручную.")
            else:
                await notify(f"⚠️ @{peer_name} — предупреждение {count}/3")
            return

        if text == ".warns":
            count = db.get_warns(owner_id, peer_id)
            await del_cmd()
            await notify(f"⚠️ Варны @{peer_name}: {count}/3")
            return

        if text == ".status":
            muted = db.is_muted(owner_id, peer_id)
            warns = db.get_warns(owner_id, peer_id)
            await del_cmd()
            status = "🔇 Замучен" if muted else "🔊 Не замучен"
            await notify(f"📊 @{peer_name}:\n{status}\n⚠️ Варны: {warns}/3")
            return

    # Auto-delete muted user messages
    else:
        if sender and db.is_muted(owner_id, sender.id):
            try:
                await ctx.bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
                await ctx.bot.send_message(chat_id=chat_id,
                    text="🔇 Вы находитесь в муте и не можете отправлять сообщения.")
            except Exception as e:
                logger.warning(f"Mute delete failed: {e}")

# ── Text messages ──────────────────────────────────────

async def msg_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    text  = (update.message.text or "").strip()
    state = ctx.user_data.get("state")

    if state == "wait_admin_pass":
        if text == ADMIN_PASSWORD:
            ctx.user_data.clear()
            s = db.get_stats()
            await update.message.reply_text(
                f"🛠 *Админ-панель SIALENS*\n\n"
                f"👥 Всего: {s['total']}\n"
                f"✅ Подписка: {s['subscribed']}\n"
                f"⏱ Пробный: {s['trial']}\n"
                f"🎁 Бесплатно: {s['free']}",
                parse_mode="Markdown", reply_markup=admin_kb())
        else:
            ctx.user_data.clear()
            await update.message.reply_text("❌ Неверный пароль.")
        return

    if state == "wait_give_user":
        if not is_admin(user.id): return
        target = db.get_user_by_username(text.lstrip("@"))
        if target:
            db.set_subscription(target["user_id"], "free")
            ctx.user_data.clear()
            await update.message.reply_text(
                f"✅ @{text.lstrip('@')} получил бесплатный доступ.",
                reply_markup=admin_kb())
        else:
            await update.message.reply_text(
                f"⚠️ Пользователь не найден.\nОн должен сначала написать /start боту.")
        return

    await update.message.reply_text("Используйте кнопки ↓", reply_markup=main_kb(user.id))

# ── Main ───────────────────────────────────────────────

def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_done))
    app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, handle_business))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))
    logger.info("SIALENS Bot started")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
