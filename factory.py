import os, json, logging, subprocess, sys, shutil
from pathlib import Path
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, filters, ContextTypes)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FACTORY_TOKEN = os.environ["FACTORY_BOT_TOKEN"]
OWNER_ID      = int(os.environ["FACTORY_OWNER_ID"])
BOTS_DIR      = Path("bots")
BOTS_DIR.mkdir(exist_ok=True)

processes: dict[str, subprocess.Popen] = {}

# ═══════════════════════ HELPERS ══════════════════════════

async def validate_token(token: str):
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://api.telegram.org/bot{token}/getMe")
            d = r.json()
            return d["result"] if d.get("ok") else None
    except:
        return None

def get_all_configs():
    out = []
    for d in sorted(BOTS_DIR.iterdir()):
        cfg = d / "config.json"
        if d.is_dir() and cfg.exists():
            with open(cfg) as f:
                out.append(json.load(f))
    return out

def save_config(username: str, config: dict):
    d = BOTS_DIR / username
    d.mkdir(exist_ok=True)
    with open(d / "config.json", "w") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def is_running(username: str) -> bool:
    p = processes.get(username)
    return p is not None and p.poll() is None

def start_process(config: dict) -> bool:
    u = config["username"]
    if is_running(u): return False
    db_dir = BOTS_DIR / u
    db_dir.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["BOT_TOKEN"]      = config["token"]
    env["ADMIN_ID"]       = str(config["admin_id"])
    env["ADMIN_PASSWORD"] = config["admin_password"]
    env["DB_PATH"]        = str(db_dir / "bot.db")
    proc = subprocess.Popen([sys.executable, "bot.py"], env=env)
    processes[u] = proc
    logger.info(f"▶ Started @{u} PID={proc.pid}")
    return True

def stop_process(username: str) -> bool:
    p = processes.pop(username, None)
    if p and p.poll() is None:
        p.terminate()
        logger.info(f"⏹ Stopped @{username}")
        return True
    return False

# ════════════════════════ KEYBOARDS ═══════════════════════

def menu_kb():
    n = len(get_all_configs())
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Создать нового бота", callback_data="create")],
        [InlineKeyboardButton(f"📋 Мои боты ({n})",     callback_data="list")],
    ])

def list_kb():
    cfgs = get_all_configs()
    rows = []
    for c in cfgs:
        u    = c["username"]
        icon = "🟢" if is_running(u) else "🔴"
        rows.append([InlineKeyboardButton(f"{icon} @{u}  —  {c.get('client','?')}",
                                          callback_data=f"info_{u}")])
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="menu")])
    return InlineKeyboardMarkup(rows)

def info_kb(username: str):
    rows = []
    if is_running(username):
        rows.append([InlineKeyboardButton("⏹ Остановить", callback_data=f"stop_{username}")])
    else:
        rows.append([InlineKeyboardButton("▶️ Запустить",  callback_data=f"run_{username}")])
    rows.append([InlineKeyboardButton("🗑 Удалить бота",  callback_data=f"del_{username}")])
    rows.append([InlineKeyboardButton("🔙 Назад",          callback_data="list")])
    return InlineKeyboardMarkup(rows)

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="menu")]])

def back_kb(cb="menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=cb)]])

# ════════════════════════ HANDLERS ════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 Нет доступа."); return
    ctx.user_data.clear()
    await update.message.reply_text(
        "🏭 *Фабрика ботов Easy Money*\n\n"
        "Здесь вы создаёте и управляете ботами для клиентов.\n"
        "Каждый бот — полная копия с отдельными настройками.",
        parse_mode="Markdown", reply_markup=menu_kb())

async def cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    q = update.callback_query
    await q.answer()
    d = q.data

    if d == "menu":
        ctx.user_data.clear()
        await q.edit_message_text("🏭 *Фабрика ботов*", parse_mode="Markdown", reply_markup=menu_kb())
        return

    if d == "create":
        ctx.user_data["state"] = "wait_client"
        await q.edit_message_text(
            "📝 *Шаг 1/4* — Имя клиента\n\nВведите имя клиента (для вашего учёта):",
            parse_mode="Markdown", reply_markup=cancel_kb()); return

    if d == "list":
        cfgs = get_all_configs()
        if not cfgs:
            await q.edit_message_text("📋 Ботов пока нет.", reply_markup=back_kb()); return
        await q.edit_message_text("📋 *Ваши боты:*\nНажмите на бота для управления.",
                                  parse_mode="Markdown", reply_markup=list_kb()); return

    if d.startswith("info_"):
        u    = d[5:]
        cfgs = get_all_configs()
        cfg  = next((c for c in cfgs if c["username"] == u), None)
        if not cfg:
            await q.edit_message_text("⚠️ Не найден.", reply_markup=back_kb("list")); return
        status = "🟢 Работает" if is_running(u) else "🔴 Остановлен"
        await q.edit_message_text(
            f"🤖 *@{u}*\n\n"
            f"👤 Клиент: {cfg.get('client','—')}\n"
            f"🔑 Admin ID: `{cfg.get('admin_id','—')}`\n"
            f"🔐 Пароль /admin: `{cfg.get('admin_password','—')}`\n"
            f"📊 Статус: {status}",
            parse_mode="Markdown", reply_markup=info_kb(u)); return

    if d.startswith("run_"):
        u    = d[4:]
        cfgs = get_all_configs()
        cfg  = next((c for c in cfgs if c["username"] == u), None)
        if cfg:
            ok  = start_process(cfg)
            msg = f"🟢 @{u} запущен!" if ok else "⚠️ Уже работает."
        else:
            msg = "⚠️ Конфиг не найден."
        await q.edit_message_text(msg, reply_markup=back_kb(f"info_{u}")); return

    if d.startswith("stop_"):
        u  = d[5:]
        ok = stop_process(u)
        await q.edit_message_text(
            f"⏹ @{u} остановлен." if ok else "⚠️ Не запущен.",
            reply_markup=back_kb(f"info_{u}")); return

    if d.startswith("del_"):
        u = d[4:]
        stop_process(u)
        bot_dir = BOTS_DIR / u
        if bot_dir.exists(): shutil.rmtree(bot_dir)
        await q.edit_message_text(f"✅ @{u} удалён.", reply_markup=back_kb("list")); return

async def msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    text  = (update.message.text or "").strip()
    state = ctx.user_data.get("state")

    if state == "wait_client":
        ctx.user_data.update({"client": text, "state": "wait_token"})
        await update.message.reply_text(
            "🔑 *Шаг 2/4* — Токен бота\n\n"
            "Введите токен бота от @BotFather:\n_(выглядит как `123456:ABC-DEF...`)_",
            parse_mode="Markdown"); return

    if state == "wait_token":
        await update.message.reply_text("⏳ Проверяю токен...")
        info = await validate_token(text)
        if not info:
            await update.message.reply_text("❌ Токен неверный или бот не существует.\nПопробуйте ещё раз:"); return
        ctx.user_data.update({"token": text, "bot_info": info, "state": "wait_admin_id"})
        await update.message.reply_text(
            f"✅ Бот найден: *@{info['username']}*\n\n"
            "🔢 *Шаг 3/4* — Admin ID\n\n"
            "Введите Telegram ID покупателя (будущего администратора этого бота).\n"
            "_(Узнать ID можно через @userinfobot)_",
            parse_mode="Markdown"); return

    if state == "wait_admin_id":
        if not text.lstrip("-").isdigit():
            await update.message.reply_text("❌ ID должен быть числом. Введите снова:"); return
        ctx.user_data.update({"admin_id": int(text), "state": "wait_admin_pass"})
        await update.message.reply_text(
            "🔐 *Шаг 4/4* — Пароль для /admin\n\n"
            "Придумайте пароль для команды /admin в этом боте.\n"
            "_(Рекомендуем сложный, например: `ABC123xyz`)_",
            parse_mode="Markdown"); return

    if state == "wait_admin_pass":
        info = ctx.user_data["bot_info"]
        u    = info["username"]
        cfg  = {
            "token":          ctx.user_data["token"],
            "admin_id":       ctx.user_data["admin_id"],
            "admin_password": text,
            "username":       u,
            "name":           info.get("first_name", u),
            "client":         ctx.user_data.get("client", "—"),
        }
        save_config(u, cfg)
        ok  = start_process(cfg)
        ctx.user_data.clear()
        await update.message.reply_text(
            f"{'✅ Бот создан и запущен!' if ok else '⚠️ Бот создан, но не запустился.'}\n\n"
            f"🤖 Бот: @{u}\n"
            f"👤 Клиент: {cfg['client']}\n"
            f"🔑 Admin ID: `{cfg['admin_id']}`\n"
            f"🔐 Пароль /admin: `{cfg['admin_password']}`\n\n"
            f"📋 *Инструкция для клиента:*\n"
            f"1. Найди бота @{u} в Telegram\n"
            f"2. Напиши /start\n"
            f"3. Для входа в админку: /admin → пароль: `{cfg['admin_password']}`\n"
            f"4. Добавь канал и пользователей через админ-панель",
            parse_mode="Markdown", reply_markup=menu_kb()); return

    await update.message.reply_text("Используйте кнопки ↓", reply_markup=menu_kb())

async def on_startup(app: Application):
    cfgs = get_all_configs()
    for cfg in cfgs:
        try:
            start_process(cfg)
            logger.info(f"Auto-started @{cfg['username']}")
        except Exception as e:
            logger.error(f"Failed to auto-start @{cfg.get('username','?')}: {e}")

def main():
    app = Application.builder().token(FACTORY_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    logger.info("🏭 Factory bot started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
