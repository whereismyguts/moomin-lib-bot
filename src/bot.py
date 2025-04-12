#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

# setup enhanced logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
)
logger = logging.getLogger(__name__)

# additional logging for telegram and httpx
logging.getLogger("telegram").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)

# log startup information
logger.info("starting telegram bot")
logger.debug(f"python version: {sys.version}")
logger.debug(f"current directory: {os.getcwd()}")
logger.debug(f"pythonpath: {sys.path}")

try:
    from telegram import Update, ReplyKeyboardMarkup, Bot
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ConversationHandler,
        ContextTypes,
        filters,
    )
    logger.info("telegram modules imported successfully")
except ImportError as e:
    logger.critical(f"failed to import telegram modules: {e}")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    # load environment variables
    load_dotenv(os.path.join(os.getcwd(), "config", ".env"))
    logger.info(f"loaded environment from {os.path.join(os.getcwd(), 'config', '.env')}")

    # verify token exists
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.critical("telegram token not found in environment")
        sys.exit(1)
    logger.debug("telegram token found")
except Exception as e:
    logger.critical(f"environment configuration error: {e}")
    sys.exit(1)

# for local debugging with venv
try:
    from src.database import MongoDBHandler
    logger.debug("imported database from src.database")
except ImportError:
    try:
        from database import MongoDBHandler
        logger.debug("imported database from database")
    except ImportError as e:
        logger.critical(f"failed to import database module: {e}")
        sys.exit(1)

# conversation states
MAIN_MENU, ADD_READER, READER_NAME, READER_CONTACT, CONFIRM_READER = range(5)
PROCESS_BOOK, CHOOSE_READER, CONFIRM_BOOK, RETURN_BOOK = range(5, 9)
READER_BOOKS, SELECT_READER_FOR_BOOKS, DEPOSIT_AMOUNT = range(9, 12)

# initialize database handler
try:
    db_handler = MongoDBHandler()
    logger.info("mongodb connection established")
except Exception as e:
    logger.critical(f"failed to initialize database connection: {e}")
    sys.exit(1)

# verify bot connectivity using async


async def check_bot_connectivity():
    try:
        test_bot = Bot(token)
        bot_info = await test_bot.get_me()
        logger.info(f"connected to telegram as @{bot_info.username} (id: {bot_info.id})")
        # check if webhook is set
        webhook_info = await test_bot.get_webhook_info()
        if webhook_info.url:
            logger.info(f"webhook currently set to: {webhook_info.url}")
            # clear webhook to avoid conflicts
            await test_bot.delete_webhook()
            logger.info("previous webhook cleared")
        return True
    except Exception as e:
        logger.critical(f"failed to connect to telegram api: {e}")
        return False

# run the connectivity check
try:
    # create event loop if not existing
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # run the connectivity check
    if not loop.run_until_complete(check_bot_connectivity()):
        sys.exit(1)
except Exception as e:
    logger.critical(f"failed during connectivity check: {e}")
    sys.exit(1)

import random
animal_emojis = [
    "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯",
    "🦁", "🐮", "🐷", "🐽", "🐸", "🐵", "🙈", "🙉", "🙊", "🐒",
    "🐔", "🐧", "🐦", "🐤", "🐣", "🐥", "🦆", "🦅", "🦉", "🦇",
    "🐺", "🐗", "🐴", "🦄", "🐝", "🐛", "🦋", "🐌", "🐞", "🐜",
    "🦟", "🦗", "🕷️", "🕸️", "🦂", "🐢", "🐍", "🦎", "🦖", "🦕",
    "🐙", "🦑", "🦐", "🦞", "🦀", "🐡", "🐠", "🐟", "🐬", "🐳",
    "🐋", "🦈", "🐊", "🐅", "🐆", "🦒", "🐘", "🦏", "🦛", "🐪",
    "🐫", "🦘", "🦙", "🐃", "🐂", "🐄", "🐎", "🐖", "🐏", "🐑",
    "🦌", "🐕", "🐩", "🐈", "🐓", "🦃", "🦚", "🦜", "🦢", "🦩",
    "🕊️", "🐇", "🦔", "🦦", "🦝", "🐀", "🐁", "🐉", "🐲", "🦥",
    "🦣", "🦬", "🦨", "🦡", "🦤", "🦫", "🦧", "🦮", "🐕‍🦺", "🦒",
    "🦍", "🦎", "🦊", "🦦", "🦥", "🦨", "🦡", "🦤", "🦧", "🦬",
    "🦣", "🦫"
]


def get_random_animal_emoji() -> str:
    """return a random animal emoji"""

    return random.choice(animal_emojis)


# action constants
ACTION_ADD_READER = "➕ Новый читатель"
ACTION_GET_LOANS = "📚 Список выданных книг"
ACTION_CHECK_OUT_BOOK = "📕 Выдать"
ACTION_RETURN_BOOK = "🔄 Вернуть"
ACTION_ALL_READERS = "👥 Список читателей"
ACTION_SELECT_READER_FOR_BOOKS = "📋 Книги читателя"
ACTION_BACK = "⬅️ Назад"

YES_BTN = "✅ да"
NO_BTN = "❌ нет"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """start the conversation and display main menu"""
    keyboard = [
        [ACTION_ADD_READER, ACTION_ALL_READERS],
        [ACTION_CHECK_OUT_BOOK, ACTION_RETURN_BOOK],
        [ACTION_GET_LOANS, ACTION_SELECT_READER_FOR_BOOKS],
    ]

    await update.message.reply_text(
        f"Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )

    return MAIN_MENU


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process main menu choice"""
    choice = update.message.text

    logger.info(f"User {update.effective_user.id} selected: {choice}")

    if choice == ACTION_ADD_READER:
        await update.message.reply_text("📝 Имя:")
        return READER_NAME
    elif choice == ACTION_CHECK_OUT_BOOK:
        readers = db_handler.get_all_readers()
        if not readers:
            await update.message.reply_text("❌ Нет читателей.")
            return await start(update, context)

        keyboard = [[reader["name"]] for reader in readers]
        keyboard.append([ACTION_BACK])

        await update.message.reply_text(
            "🔎 Кому выдать книгу?",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return CHOOSE_READER
    elif choice == ACTION_RETURN_BOOK:
        loans = db_handler.get_active_loans()

        if not loans:
            await update.message.reply_text("❌ Пусто.")
            return await start(update, context)

        keyboard = []
        for loan in loans:
            reader = db_handler.get_reader_by_id(loan["reader_id"])
            keyboard.append([f"{reader['name']}: {loan['book_title']}"])
        keyboard.append([ACTION_BACK])

        await update.message.reply_text(
            "🔎 Какую книгу вернуть?",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return RETURN_BOOK
    elif choice == ACTION_ALL_READERS:
        readers = db_handler.get_all_readers()
        if not readers:
            await update.message.reply_text("❌ Никого нет.")
        else:
            response = ""
            for i, reader in enumerate(readers, 1):
                response += f"{i}. {reader['name']}: {reader['contact']}\n"
            await update.message.reply_text(response)
        return await start(update, context)
    elif choice == ACTION_GET_LOANS:
        loans = db_handler.get_active_loans()
        if not loans:
            await update.message.reply_text("❌ Ничего не выдано.")
        else:
            response = ""
            for i, loan in enumerate(loans, 1):
                reader = db_handler.get_reader_by_id(loan["reader_id"])
                loan_date = loan["loan_date"].strftime("%d.%m.%Y")
                response += f"{i}. \"{loan['book_title']}\" - {reader['name']} ({loan_date})\n"
            await update.message.reply_text(response)
        return await start(update, context)
    elif choice == ACTION_SELECT_READER_FOR_BOOKS:
        readers = db_handler.get_all_readers()
        if not readers:
            await update.message.reply_text("❌ Нет читателей.")
            return await start(update, context)

        keyboard = [[reader["name"]] for reader in readers]
        keyboard.append([ACTION_BACK])

        await update.message.reply_text(
            "🔎 Выбрите читателя:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return SELECT_READER_FOR_BOOKS
    else:
        await update.message.reply_text(' '.join([get_random_animal_emoji() for i in range(3)]))
        return MAIN_MENU


async def reader_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process reader name input"""
    context.user_data["reader_name"] = f"{update.message.text} {get_random_animal_emoji()}"
    await update.message.reply_text("☎️ Контактные данные (телефон, e-mail, telegram, etc.):")
    return READER_CONTACT


async def reader_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process reader contact input"""
    context.user_data["reader_contact"] = update.message.text

    await update.message.reply_text(
        f'Имя: {context.user_data["reader_name"]}\n'
        f'Контакт: {context.user_data["reader_contact"]}',
        reply_markup=ReplyKeyboardMarkup([[YES_BTN, NO_BTN]], one_time_keyboard=True, resize_keyboard=True),
    )
    return CONFIRM_READER


async def confirm_reader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """confirm and add new reader to the database"""
    if update.message.text == YES_BTN:
        reader_data = {
            "name": context.user_data["reader_name"],
            "contact": context.user_data["reader_contact"],
            "deposit_amount": 0,  # will be updated when giving books
            "registration_date": datetime.now(),
        }

        db_handler.add_reader(reader_data)
        await update.message.reply_text(f"Читатель {reader_data['name']} добавлен!")
    else:
        await update.message.reply_text("Галя, у нас отмена!")

    return await start(update, context)


async def choose_reader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process reader selection for book lending"""
    choice = update.message.text

    if choice == ACTION_BACK:
        return await start(update, context)

    reader = db_handler.get_reader_by_name(choice)
    if not reader:
        await update.message.reply_text("Читатель не найден.")
        return CHOOSE_READER

    context.user_data["selected_reader"] = reader

    await update.message.reply_text(f"✏️ Название книги, которую получит {reader['name']}:")
    return PROCESS_BOOK


async def process_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process book title input"""
    book_title = update.message.text
    context.user_data["book_title"] = book_title
    reader = context.user_data["selected_reader"]

    # check if deposit needs to be updated
    current_loans = db_handler.get_reader_active_loans(reader["_id"])
    if not current_loans:
        # ask for deposit amount with quick 50 button
        keyboard = [["10", "20", "50"], [ACTION_BACK]]
        await update.message.reply_text(
            f"Введите сумму залога для {reader['name']} или выберите сумму:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        context.user_data["pending_book"] = book_title
        return DEPOSIT_AMOUNT
    else:
        # no deposit needed, continue with confirmation
        context.user_data["deposit_needed"] = 0
        await update.message.reply_text(
            f'{reader["name"]} уже имеет активные выдачи книг. Залог не требуется.\n\n'
            f"Выдаем \"{book_title}\"?",
            reply_markup=ReplyKeyboardMarkup([[YES_BTN, NO_BTN]], one_time_keyboard=True, resize_keyboard=True),
        )
        return CONFIRM_BOOK


async def deposit_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """handle deposit amount input with preset 50 button"""
    choice = update.message.text
    reader = context.user_data["selected_reader"]
    book_title = context.user_data["pending_book"]

    if choice == ACTION_BACK:
        return await start(update, context)

    try:
        deposit = int(choice)
    except ValueError:
        await update.message.reply_text("Не, нужно же было ввести число!")
        return DEPOSIT_AMOUNT

    # save deposit amount
    context.user_data["deposit_needed"] = deposit
    context.user_data["book_title"] = book_title

    # confirm book loan with deposit
    await update.message.reply_text(
        f"Читатель: {reader['name']}\n"
        f"Книга: {book_title}\n"
        f"Залог: {deposit}\n\n"
        f"Всё верно?",
        reply_markup=ReplyKeyboardMarkup([[YES_BTN, NO_BTN]], one_time_keyboard=True, resize_keyboard=True),
    )

    return CONFIRM_BOOK


async def confirm_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """confirm and add book loan to the database"""
    if update.message.text == YES_BTN:
        reader = context.user_data["selected_reader"]
        book_title = context.user_data["book_title"]
        deposit_needed = context.user_data["deposit_needed"]

        # add loan to database
        loan_data = {
            "reader_id": reader["_id"],
            "book_title": book_title,
            "loan_date": datetime.now(),
            "is_active": True,
        }

        # update reader's deposit if needed
        if deposit_needed > 0:
            db_handler.update_reader_deposit(reader["_id"], deposit_needed)
            deposit_message = f" Залог {deposit_needed} получен."
        else:
            deposit_message = ""

        db_handler.add_loan(loan_data)

        await update.message.reply_text(f"Книга \"{book_title}\" выдана {reader['name']}.{deposit_message}")
    else:
        await update.message.reply_text("Галя, у нас отмена!")

    return await start(update, context)


async def return_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process book return"""
    choice = update.message.text

    if choice == ACTION_BACK:
        return await start(update, context)

    # parse the selection e")
    try:
        reader_name, book_title = choice.split(": ")
        reader_name = reader_name.strip()
        book_title = book_title.strip()
    except ValueError:
        await update.message.reply_text("Что-то не так с выбором. Пожалуйста, выберите из списка.")
        return RETURN_BOOK

    reader = db_handler.get_reader_by_name(reader_name)
    if not reader:
        await update.message.reply_text("Читатель не найден.")
        return RETURN_BOOK

    # mark book as returned
    result = db_handler.return_book(reader["_id"], book_title)

    if result:
        # check if this was the last book
        active_loans = db_handler.get_reader_active_loans(reader["_id"])
        if not active_loans:
            # return deposit
            deposit_amount = reader["deposit_amount"]
            db_handler.update_reader_deposit(reader["_id"], 0)
            await update.message.reply_text(
                f"Книга \"{book_title}\" возвращена.\n"
                f"Это последняя книга {reader_name}. Верните залог {deposit_amount}."
            )
        else:
            await update.message.reply_text(f"Книга \"{book_title}\" возвращена.")
    else:
        await update.message.reply_text("Произошла ошибка при обработке возврата книги.")

    return await start(update, context)


async def select_reader_for_books(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """handle reader selection for viewing their books"""
    choice = update.message.text

    if choice == ACTION_BACK:
        return await start(update, context)

    reader = db_handler.get_reader_by_name(choice)
    if not reader:
        await update.message.reply_text("Читатель не найден. Пожалуйста, выберите из списка.")
        return SELECT_READER_FOR_BOOKS

    # get reader's books
    loans = db_handler.get_reader_active_loans(reader["_id"])

    if not loans:
        await update.message.reply_text(f"У читателя {reader['name']} нет активных выдач книг.")
    else:
        response = f"Книги, выданные читателю {reader['name']}:\n\n"
        for i, loan in enumerate(loans, 1):
            loan_date = loan["loan_date"].strftime("%d.%m.%Y")
            response += f"{i}. {loan['book_title']} (выдана {loan_date})\n"

        # add deposit info
        if reader["deposit_amount"] > 0:
            response += f"\nТекущий залог: {reader['deposit_amount']} евро"

        await update.message.reply_text(response)

    return await start(update, context)


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """log errors caused by updates"""
    logger.warning(f"Update {update} caused error {context.error}")


def main() -> None:
    """start the bot"""
    # create the application and pass it the bot's token
    application = Application.builder().token(os.environ.get("TELEGRAM_TOKEN")).build()

    async def log_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """log incoming updates"""
        logger.debug(f"received update: {update}")

    application.add_handler(MessageHandler(filters.ALL, log_update), group=-1)

    # add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
            READER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reader_name)],
            READER_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, reader_contact)],
            CONFIRM_READER: [MessageHandler(filters.Regex(f"^({YES_BTN}|{NO_BTN})$"), confirm_reader)],
            CHOOSE_READER: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_reader)],
            PROCESS_BOOK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_book)],
            DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount_input)],
            CONFIRM_BOOK: [MessageHandler(filters.Regex(f"^({YES_BTN}|{NO_BTN})$"), confirm_book)],
            RETURN_BOOK: [MessageHandler(filters.TEXT & ~filters.COMMAND, return_book)],
            SELECT_READER_FOR_BOOKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_reader_for_books)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)

    # log all errors
    application.add_error_handler(error)

    # check if webhook mode should be used
    webhook_enabled = os.environ.get("WEBHOOK_ENABLED", "").lower() == "true"
    webhook_url = os.environ.get("WEBHOOK_URL", "")

    if webhook_enabled and webhook_url:
        # use webhook
        webhook_port = int(os.environ.get("PORT", 8443))
        webhook_path = os.environ.get("WEBHOOK_PATH", "")

        logger.info(f"starting bot in webhook mode at {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=webhook_port,
            url_path=webhook_path,
            webhook_url=f"{webhook_url}{webhook_path}",
        )
    else:
        # use polling with explicit settings
        logger.info("starting bot in polling mode")
        application.run_polling(
            poll_interval=1.0,  # faster polling
            timeout=30,         # longer timeout
            drop_pending_updates=False,  # process any pending updates
            allowed_updates=["message", "callback_query"],  # specify updates we care about
            read_timeout=7,
            write_timeout=7,
        )


if __name__ == "__main__":
    main()
