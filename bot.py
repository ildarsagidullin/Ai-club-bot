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

# ── Состояния ─────────────────────────────────────────────────────────────────
(
    MAIN_MENU,
    ASK_NAME,
    POLL,
    ADMIN_AUTH,
    BROADCAST,
    EVENT_MENU,
    EVENT_TOPIC,
    EVENT_DATE,
    EVENT_LOCATION,
    EVENT_MAP,
) = range(10)


# ═══════════════════════════════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════════════════════════════════════════════

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


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "register":
        event = db.get_event()
        if not event.get("is_active", True):
            await query.edit_message_text(
                msg.EVENT_INACTIVE,
                parse_mode="MarkdownV2",
                disable_web_page_preview=False,
            )
            return ConversationHandler.END

        await query.edit_message_text(
            msg.build_event_card(),
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


# ═══════════════════════════════════════════════════════════════════════════════
# РЕГИСТРАЦИЯ
# ═══════════════════════════════════════════════════════════════════════════════

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
    key = query.data[5:]
    interests: set = context.user_data.setdefault("interests", set())
    if key in interests:
        interests.discard(key)
    else:
        interests.add(key)
    await query.edit_message_reply_markup(
        InlineKeyboardMarkup(_build_poll_keyboard(interests))
    )
    return POLL


async def _finish_registration(query, context: ContextTypes.DEFAULT_TYPE, interests_str: str):
    try:
        name     = context.user_data["name"]
        tg_user  = query.from_user
        tg_id    = tg_user.id
        username = f"@{tg_user.username}" if tg_user.username else f"id:{tg_id}"

        db.save_registration(tg_id, username, name, interests_str)
        count = db.get_count()

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=msg.build_confirmation(name),
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
        logging.error("Ошибка при регистрации: %s", exc, exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Что-то пошло не так 😔 Попробуй ещё раз — напиши /start",
            )
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# /admin — список участников
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# /broadcast — рассылка всем
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    count = db.get_count()
    await update.message.reply_text(
        f"📢 Напиши текст сообщения — разошлю всем {count} зарегистрированным.\n\n"
        "Отправь /cancel чтобы отменить."
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
    await update.message.reply_text(f"✅ Готово! Отправлено: {sent}, не доставлено: {failed}")
    return ConversationHandler.END


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════════
# /event — управление анонсом (только для админа)
# ═══════════════════════════════════════════════════════════════════════════════

async def event_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    event = db.get_event()
    toggle_btn = (
        InlineKeyboardButton(msg.BTN_ACTIVATE,    callback_data="ev_activate")
        if not event.get("is_active")
        else InlineKeyboardButton(msg.BTN_DEACTIVATE, callback_data="ev_deactivate")
    )
    keyboard = [
        [InlineKeyboardButton(msg.BTN_EDIT_EVENT, callback_data="ev_edit")],
        [toggle_btn],
        [InlineKeyboardButton(msg.BTN_CANCEL_EVENT, callback_data="ev_cancel")],
    ]
    await update.message.reply_text(
        msg.build_event_admin_menu(),
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return EVENT_MENU


async def event_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "ev_edit":
        await query.edit_message_text(msg.ASK_EVENT_TOPIC, parse_mode="MarkdownV2")
        return EVENT_TOPIC

    if query.data == "ev_deactivate":
        db.set_event_active(False)
        await query.edit_message_text(msg.EVENT_HIDDEN, parse_mode="MarkdownV2")
        return ConversationHandler.END

    if query.data == "ev_activate":
        db.set_event_active(True)
        await query.edit_message_text(msg.EVENT_SHOWN, parse_mode="MarkdownV2")
        return ConversationHandler.END

    if query.data == "ev_cancel":
        await query.edit_message_text(msg.EVENT_CANCELLED, parse_mode="MarkdownV2")
        return ConversationHandler.END

    return EVENT_MENU


async def event_receive_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_topic"] = update.message.text.strip()
    await update.message.reply_text(msg.ASK_EVENT_DATE, parse_mode="MarkdownV2")
    return EVENT_DATE


async def event_receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_date"] = update.message.text.strip()
    await update.message.reply_text(msg.ASK_EVENT_LOCATION, parse_mode="MarkdownV2")
    return EVENT_LOCATION


async def event_receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_location"] = update.message.text.strip()
    await update.message.reply_text(msg.ASK_EVENT_MAP, parse_mode="MarkdownV2")
    return EVENT_MAP


async def event_receive_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    map_url = "" if raw.lower() in ("нет", "no", "-", "—") else raw

    topic    = context.user_data["new_topic"]
    date     = context.user_data["new_date"]
    location = context.user_data["new_location"]

    # Показываем превью
    preview = (
        "👀 *Вот как будет выглядеть анонс:*\n\n"
        f"📌 *Тема:* {msg.esc(topic)}\n"
        f"🕐 *Когда:* {msg.esc(date)}\n"
        f"📍 *Где:* {msg.esc(location)}\n"
    )
    if map_url:
        preview += f"🗺 [Карта]({map_url})\n"

    keyboard = [
        [InlineKeyboardButton("✅ Сохранить", callback_data="ev_save")],
        [InlineKeyboardButton("↩️ Отмена",   callback_data="ev_cancel")],
    ]
    context.user_data["new_map"] = map_url
    await update.message.reply_text(
        preview,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )
    return EVENT_MAP


async def event_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "ev_save":
        db.save_event(
            topic=context.user_data["new_topic"],
            date=context.user_data["new_date"],
            location=context.user_data["new_location"],
            map_url=context.user_data["new_map"],
        )
        await query.edit_message_text(msg.EVENT_SAVED, parse_mode="MarkdownV2")
    else:
        await query.edit_message_text(msg.EVENT_CANCELLED, parse_mode="MarkdownV2")

    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════════
# /export
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Главная воронка регистрации
    main_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(menu_callback, pattern="^(register|about|contact)$")],
            ASK_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            POLL:      [CallbackQueryHandler(poll_callback, pattern="^poll_")],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, fallback),
        ],
        allow_reentry=True,
    )

    # Список участников
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_start)],
        states={
            ADMIN_AUTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_auth)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    # Рассылка
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", broadcast_cancel)],
    )

    # Управление анонсом
    event_conv = ConversationHandler(
        entry_points=[CommandHandler("event", event_menu)],
        states={
            EVENT_MENU:     [CallbackQueryHandler(event_menu_callback, pattern="^ev_")],
            EVENT_TOPIC:    [MessageHandler(filters.TEXT & ~filters.COMMAND, event_receive_topic)],
            EVENT_DATE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, event_receive_date)],
            EVENT_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, event_receive_location)],
            EVENT_MAP:      [
                MessageHandler(filters.TEXT & ~filters.COMMAND, event_receive_map),
                CallbackQueryHandler(event_save_callback, pattern="^ev_(save|cancel)$"),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(main_conv)
    app.add_handler(admin_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(event_conv)
    app.add_handler(CommandHandler("export", export_command))

    print("✅ Бот запущен. Нажми Ctrl+C чтобы остановить.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
