import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, timezone

from bot.oauth import exchange_code_for_token
from bot.ptb_jobs import create_repeating_job, fetch_jobs_callback, send_jobs_callback
from bot.utils import save_token_to_db

CLIENT_ID = os.getenv("UPWORK_CLIENT_ID")
CLIENT_SECRET = os.getenv("UPWORK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("UPWORK_REDIRECT_URI")

logger = logging.getLogger(__name__)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(f"You said: {text}")


async def parse_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()

    if "code=" not in text:
        return

    try:
        parsed = urlparse(text)
        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]

        if not code:
            await update.message.reply_text("Failed to extract the authorization code.")
            return

        # Acknowledge receipt without exposing the authorization code
        await update.message.reply_text("Authorization code received. Processing authentication...")

        token_data = await exchange_code_for_token(code)

        if not token_data or "access_token" not in token_data:
            logger.error(
                "Token exchange failed or returned invalid data: %s", token_data)
            await update.message.reply_text("Authentication failed. Please try again.")
            return

        # Calculate absolute expiration time securely
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # PRODUCTION REQUIREMENT: Replace with your Database ORM / secure storage logic
        await save_token_to_db(
            user_id=update.effective_user.id,
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at.timestamp()
        )

        chat_id = update.effective_chat.id

        await create_repeating_job(context, f"fetch_jobs_{chat_id}", update.effective_chat.id, fetch_jobs_callback, interval_minutes=10)
        await create_repeating_job(context, f"send_jobs_{chat_id}", chat_id, send_jobs_callback, interval_minutes=10)

        await update.message.reply_text("Authentication successful. Job fetching started. You will receive updates every 15 minutes.")

    except Exception as e:
        logger.error(
            "Unexpected error during OAuth redirect parsing: %s", e, exc_info=True)
        await update.message.reply_text("An internal error occurred during the authentication process.")
