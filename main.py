from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import BOT_TOKEN
from bot.commands import login, start, help_command
from bot.handlers import echo, parse_redirect


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # Messages
    app.add_handler(CommandHandler("login", login))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            parse_redirect,
        )
    )

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()