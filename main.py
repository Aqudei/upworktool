import logging
from logging.handlers import RotatingFileHandler
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)


def setup_logging():
    """Configures both console and file logging with rotation."""

    # 1. Create a custom formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 2. Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 3. Setup Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 4. Setup File Handler (10 MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        "bot_production.log", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 5. Mute noisy dependencies
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    return logging.getLogger(__name__)


# Initialize the logger
logger = setup_logging()

from bot.config import BOT_TOKEN
from bot.commands import start, help_command, set_command, unset_command, list_command
from bot.handlers import echo, parse_redirect


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("set", set_command))
    app.add_handler(CommandHandler("unset", unset_command))
    app.add_handler(CommandHandler("list", list_command))

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
