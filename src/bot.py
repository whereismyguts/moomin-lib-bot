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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """start the conversation and display main menu"""
    keyboard = [
        ["📋 Добавить читателя"],
        ["📚 Выдать книгу"],
        ["🔄 Вернуть книгу"],
        ["👥 Список читателей"],
        ["📖 Список выданных книг"],
    ]

    await update.message.reply_text(
        "Добро пожаловать в систему управления библиотекой! Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )

    return MAIN_MENU

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process main menu choice"""
    choice = update.message.text

    logger.info(f"User {update.effective_user.id} selected: {choice}")

    if choice == "📋 Добавить читателя":
        await update.message.reply_text("Введите имя нового читателя:")
        return READER_NAME
    elif choice == "📚 Выдать книгу":
        readers = db_handler.get_all_readers()
        if not readers:
            await update.message.reply_text("У вас еще нет читателей. Сначала добавьте читателя.")
            return await start(update, context)
        
        keyboard = [[reader["name"]] for reader in readers]
        keyboard.append(["⬅️ Назад"])
        
        await update.message.reply_text(
            "Выберите читателя, которому выдаете книгу:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return CHOOSE_READER
    elif choice == "🔄 Вернуть книгу":
        loans = db_handler.get_active_loans()
        
        if not loans:
            await update.message.reply_text("На данный момент нет активных выдач книг.")
            return await start(update, context)
        
        keyboard = []
        for loan in loans:
            reader = db_handler.get_reader_by_id(loan["reader_id"])
            keyboard.append([f"{reader['name']} - {loan['book_title']}"])
        keyboard.append(["⬅️ Назад"])
        
        await update.message.reply_text(
            "Выберите возвращаемую книгу:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        )
        return RETURN_BOOK
    elif choice == "👥 Список читателей":
        readers = db_handler.get_all_readers()
        if not readers:
            await update.message.reply_text("У вас еще нет читателей в базе.")
        else:
            response = "Список читателей:\n\n"
            for i, reader in enumerate(readers, 1):
                response += f"{i}. {reader['name']} - {reader['contact']}\n"
            await update.message.reply_text(response)
        return await start(update, context)
    elif choice == "📖 Список выданных книг":
        loans = db_handler.get_active_loans()
        if not loans:
            await update.message.reply_text("На данный момент нет активных выдач книг.")
        else:
            response = "Список выданных книг:\n\n"
            for i, loan in enumerate(loans, 1):
                reader = db_handler.get_reader_by_id(loan["reader_id"])
                loan_date = loan["loan_date"].strftime("%d.%m.%Y")
                response += f"{i}. {loan['book_title']} - {reader['name']} (выдана {loan_date})\n"
            await update.message.reply_text(response)
        return await start(update, context)
    else:
        await update.message.reply_text("Пожалуйста, выберите один из предложенных вариантов.")
        return MAIN_MENU

async def reader_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process reader name input"""
    context.user_data["reader_name"] = update.message.text
    await update.message.reply_text("Введите контактную информацию читателя (телефон или Telegram):")
    return READER_CONTACT

async def reader_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process reader contact input"""
    context.user_data["reader_contact"] = update.message.text
    
    await update.message.reply_text(
        f"Подтвердите информацию о читателе:\n\n"
        f"Имя: {context.user_data['reader_name']}\n"
        f"Контакт: {context.user_data['reader_contact']}\n\n"
        f"Всё верно?",
        reply_markup=ReplyKeyboardMarkup([["✅ Да", "❌ Нет"]], one_time_keyboard=True, resize_keyboard=True),
    )
    return CONFIRM_READER

async def confirm_reader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """confirm and add new reader to the database"""
    if update.message.text == "✅ Да":
        reader_data = {
            "name": context.user_data["reader_name"],
            "contact": context.user_data["reader_contact"],
            "deposit_amount": 0,  # will be updated when giving books
            "registration_date": datetime.now(),
        }
        
        db_handler.add_reader(reader_data)
        await update.message.reply_text(f"Читатель {reader_data['name']} успешно добавлен!")
    else:
        await update.message.reply_text("Отменено. Давайте начнем сначала.")
    
    return await start(update, context)

async def choose_reader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process reader selection for book lending"""
    choice = update.message.text
    
    if choice == "⬅️ Назад":
        return await start(update, context)
    
    reader = db_handler.get_reader_by_name(choice)
    if not reader:
        await update.message.reply_text("Читатель не найден. Пожалуйста, выберите из списка.")
        return CHOOSE_READER
    
    context.user_data["selected_reader"] = reader
    
    await update.message.reply_text(f"Введите название книги, которую выдаете {reader['name']}:")
    return PROCESS_BOOK

async def process_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process book title input"""
    book_title = update.message.text
    context.user_data["book_title"] = book_title
    reader = context.user_data["selected_reader"]
    
    # check if deposit needs to be updated
    current_loans = db_handler.get_reader_active_loans(reader["_id"])
    deposit_needed = 50 if not current_loans else 0
    deposit_message = f"\n\nНеобходимый залог: {deposit_needed} евро." if deposit_needed > 0 else ""
    
    await update.message.reply_text(
        f"Подтвердите выдачу книги:\n\n"
        f"Читатель: {reader['name']}\n"
        f"Книга: {book_title}{deposit_message}\n\n"
        f"Всё верно?",
        reply_markup=ReplyKeyboardMarkup([["✅ Да", "❌ Нет"]], one_time_keyboard=True, resize_keyboard=True),
    )
    
    context.user_data["deposit_needed"] = deposit_needed
    return CONFIRM_BOOK

async def confirm_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """confirm and add book loan to the database"""
    if update.message.text == "✅ Да":
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
            deposit_message = f" Залог {deposit_needed} евро получен."
        else:
            deposit_message = ""
        
        db_handler.add_loan(loan_data)
        
        await update.message.reply_text(f"Книга \"{book_title}\" выдана {reader['name']}.{deposit_message}")
    else:
        await update.message.reply_text("Выдача книги отменена.")
    
    return await start(update, context)

async def return_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """process book return"""
    choice = update.message.text
    
    if choice == "⬅️ Назад":
        return await start(update, context)
    
    # parse the selection (format: "Reader Name - Book Title")
    try:
        reader_name, book_title = choice.split(" - ", 1)
    except ValueError:
        await update.message.reply_text("Неверный формат. Пожалуйста, выберите из списка.")
        return RETURN_BOOK
    
    reader = db_handler.get_reader_by_name(reader_name)
    if not reader:
        await update.message.reply_text("Читатель не найден. Пожалуйста, выберите из списка.")
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
                f"Это последняя книга {reader_name}. Верните залог {deposit_amount} евро."
            )
        else:
            await update.message.reply_text(f"Книга \"{book_title}\" возвращена.")
    else:
        await update.message.reply_text("Произошла ошибка при обработке возврата книги.")
    
    return await start(update, context)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """log errors caused by updates"""
    logger.warning(f"Update {update} caused error {context.error}")

def main() -> None:
    """start the bot"""
    # create the application and pass it the bot's token
    application = Application.builder().token(os.environ.get("TELEGRAM_TOKEN")).build()

    # explicitly set up our update handler to get detailed logs
    async def log_update(update: Update) -> None:
        logger.debug(f"received update: {update}")
        
    application.add_handler(MessageHandler(filters.ALL, log_update), group=-1)

    # add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
            READER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reader_name)],
            READER_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, reader_contact)],
            CONFIRM_READER: [MessageHandler(filters.Regex("^(✅ Да|❌ Нет)$"), confirm_reader)],
            CHOOSE_READER: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_reader)],
            PROCESS_BOOK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_book)],
            CONFIRM_BOOK: [MessageHandler(filters.Regex("^(✅ Да|❌ Нет)$"), confirm_book)],
            RETURN_BOOK: [MessageHandler(filters.TEXT & ~filters.COMMAND, return_book)],
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