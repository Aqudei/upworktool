from telegram import Update
from telegram.ext import ContextTypes
from .oauth import get_authorization_url


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! I'm alive."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Available commands:\n/start\n/help"
    )


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth_url = get_authorization_url()

    await update.message.reply_text(
        f"Open this URL:\n\n{auth_url}\n\n"
        "After login, copy the full redirect URL and send it here."
    )