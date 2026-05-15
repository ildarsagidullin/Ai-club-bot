import io
import logging
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import database as db
import messages as msg
from config import ADMIN_ID, ADMIN_PASSWORD, BOT_TOKEN, COMMUNITY_LINK

logging.basicConfig(
    format="%(asctime)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)

# ── Состояния диалога ─────────────────────────────────────────────────────────
MAIN_MENU, ASK_NAME, POLL, ADMIN_AUTH, BROADCAST = range(5)


# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton(msg.BTN_REGISTER, callback_data="register")],
        [InlineKeyboardButton(msg.BTN_WHAT_IS,  callback_data="about")],
        [InlineKeyboardButton(msg.BTN_CONTACT,  callback_data="contact")],
    ]
    await update.message.reply_text(
        msg.WELCOME,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return MAIN_MENU


# ── Главное меню (callback) ───────────────────────────────────────────────────
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "register":
        await query.edit_message_text(
            msg.EVENT_CARD,
            parse_mode="MarkdownV2",
            disable_web_page_preview=False,
        )
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=msg.ASK_NAME,
            parse_mode="MarkdownV2",
        )
        return ASK_NAME

    if query.data == "about":
        keyboard = [[InlineKeyboardButton(msg.BTN_REGISTER, callback_data="register")]]
        await query.edit_message_text(
            msg.ABOUT_CLUB,
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return MAIN_MENU

    if query.data == "contact":
        await query.edit_message_text(msg.CONTACT_MSG, parse_mode="MarkdownV2")
        return ConversationHandler.END

    return MAIN_MENU


# ── Шаг 1: получаем имя → сразу показываем опрос ─────────────────────────────
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("Напиши хотя бы 2 символа 🙂")
        return ASK_NAME
    context.user_data["name"] = name
    context.user_data["interests"] = set()
    await update.message.reply_text(
        msg.POLL_QUESTION,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(_build_poll_keyboard(set())),
    )
    return POLL


def _build_poll_keyboard(selected: set) -> list:
    rows = []
    for label, key in msg.POLL_OPTIONS:
        prefix = "✅ " if key in selected else ""
        rows.append([InlineKeyboardButton(prefix + label, callback_data=f"poll_{key}")])
    rows.append([InlineKeyboardButton(msg.BTN_DONE_POLL, callback_data="poll_done")])
    return rows


# ── Опрос (multi-select) ──────────────────────────────────────────────────────
async def poll_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query

    if query.data == "poll_done":
        selected = context.user_data.get("interests", set())
        if not selected:
            await query.answer("Выбери хотя бы один вариант!", show_alert=True)
            return POLL
        await query.answer()
        label_map = {key: label for label, key in msg.POLL_OPTIONS}
        interests_str = ", ".join(label_map[k] for k in selected if k in label_map)
        await _finish_registration(query, context, interests_str)
        return ConversationHandler.END

    await query.answer()
    key = query.data[5:]  # strip "poll_"
    interests: set = context.user_data.setdefault("interests", set())
    if key in interests:
        interests.discard(key)
    else:
        interests.add(key)
    await query.edit_message_reply_markup(
        InlineKeyboardMarkup(_build_poll_keyboard(interests))
    )
    return POLL


# ── Завершение регистрации ────────────────────────────────────────────────────
async def _finish_registration(query, context: ContextTypes.DEFAULT_TYPE, interests_str: str):
    try:
        name     = context.user_data["name"]
        tg_user  = query.from_user
        tg_id    = tg_user.id
        username = f"@{tg_user.username}" if tg_user.username else f"id:{tg_id}"

        db.save_registration(tg_id, username, name, interests_str)
        count = db.get_count()

        confirmation = msg.CONFIRMATION_TPL.format(
            name=msg.esc(name),
            community=COMMUNITY_LINK,
        )
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=confirmation,
            parse_mode="MarkdownV2",
            disable_web_page_preview=False,
        )

        notification = msg.ADMIN_NOTIFICATION_TPL.format(
            name=name,
            username=username,
            interests=interests_str,
            count=count,
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=notification,
                parse_mode="MarkdownV2",
            )
        except Exception as exc:
            logging.warning("Не удалось уведомить администратора: %s", exc)

    except Exception as exc:
        logging.error("Ошибка при завершении регистрации: %s", exc, exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Что-то пошло не так 😔 Попробуй ещё раз — напиши /start",
            )
        except Exception:
            pass


# ── /admin ────────────────────────────────────────────────────────────────────
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(msg.ADMIN_ASK_PASSWORD)
    return ADMIN_AUTH


async def admin_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.strip() != ADMIN_PASSWORD:
        await update.message.reply_text(msg.ADMIN_WRONG_PASSWORD)
        return ConversationHandler.END

    rows = db.get_all_registrations()
    if not rows:
        await update.message.reply_text(msg.ADMIN_LIST_EMPTY)
        return ConversationHandler.END

    header = msg.ADMIN_LIST_HEADER.format(count=len(rows))
    lines = []
    for i, (rid, name, uname, interests, reg_at) in enumerate(rows, 1):
        lines.append(f"{i}\\. *{msg.esc(name)}* — {msg.esc(uname)}\n   _{msg.esc(interests)}_")
    await update.message.reply_text(
        header + "\n".join(lines),
        parse_mode="MarkdownV2",
    )
    return ConversationHandler.END


# ── /broadcast ───────────────────────────────────────────────────────────────
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    count = db.get_count()
    await update.message.reply_text(
        f"📢 Напиши текст сообщения — разошлю всем {count} зарегистрированным.\n\n"
        "Можно использовать эмодзи. Отправь /cancel чтобы отменить."
    )
    return BROADCAST


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    ids = db.get_all_telegram_ids()
    sent, failed = 0, 0
    for tg_id in ids:
        try:
            await context.bot.send_message(chat_id=tg_id, text=text)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"✅ Готово! Отправлено: {sent}, не доставлено: {failed}"
    )
    return ConversationHandler.END


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ── /export ───────────────────────────────────────────────────────────────────
async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    csv_bytes = db.export_csv()
    await update.message.reply_document(
        document=io.BytesIO(csv_bytes),
        filename="registrations.csv",
        caption=msg.EXPORT_CAPTION,
    )


# ── Fallback ──────────────────────────────────────────────────────────────────
async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(msg.FALLBACK)
    return ConversationHandler.END


# ── Запуск ────────────────────────────────────────────────────────────────────
def main():
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    main_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(menu_callback, pattern="^(register|about|contact)$")
            ],
            ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)
            ],
            POLL: [
                CallbackQueryHandler(poll_callback, pattern="^poll_")
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, fallback),
        ],
        allow_reentry=True,
    )

    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_start)],
        states={
            ADMIN_AUTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_auth)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send),
            ],
        },
        fallbacks=[CommandHandler("cancel", broadcast_cancel)],
    )

    app.add_handler(main_conv)
    app.add_handler(admin_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(CommandHandler("export", export_command))

    print("✅ Бот запущен. Нажми Ctrl+C чтобы остановить.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
