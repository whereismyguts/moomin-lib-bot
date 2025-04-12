# Telegram Library Bot

A Telegram bot for managing a small library. Allows tracking readers, books, deposits, and quickly processing book checkouts and returns.

## Features

- Registration of new readers with contact information
- Lending books to readers with deposit tracking
- Book returns with deposit management
- View list of active book loans
- View list of all registered readers

## How to Run

1. Copy the configuration file and add your Telegram token:

   ```
   cp config/.env.example config/.env
   ```

   Then open the `config/.env` file and add your token from BotFather.

2. Start the bot using Docker Compose:

   ```
   docker-compose up -d
   ```

3. To stop the bot:

   ```
   docker-compose down
   ```

## Usage

1. Start interacting with the bot by sending the `/start` command
2. Select the desired action from the menu:
   - Add a new reader
   - Check out a book
   - Accept a book return
   - View the list of readers
   - View the list of checked out books

## Deposit System

The system works based on a fixed deposit of 50 euros. A reader can borrow multiple books (up to 5) for a single deposit. The deposit is returned when the reader returns all books.