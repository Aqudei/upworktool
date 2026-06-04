import logging

from telegram import Update
from telegram.ext import ContextTypes
from .handlers import fetch_jobs
from bot.utils import get_valid_access_token
from .oauth import get_authorization_url

logger = logging.getLogger(__name__)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! I'm alive."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Available commands:\n/start\n/help"
    )


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Acknowledge the command immediately to ensure application responsiveness
    await update.message.reply_text("Verifying existing authentication status...")

    try:
        # Attempt to retrieve a valid token. 
        # This function will automatically attempt a refresh if the token is nearing expiration.
        access_token = await get_valid_access_token(user_id=user_id)
        
        # If no exception is raised, a valid session exists.
        await update.message.reply_text(
            "You are already securely authenticated. No further action is required."
        )
        
        # Optional: Ensure the background polling job is active if the user restarts the bot
        job_name = f"fetch_jobs_{chat_id}"
        current_jobs = context.job_queue.get_jobs_by_name(job_name)
        
        if not current_jobs:
            context.job_queue.run_repeating(
                fetch_jobs, 
                interval=60 * 15, 
                first=0, 
                data=chat_id,
                name=job_name
            )
            await update.message.reply_text("Background job fetching has been successfully resumed.")

        return

    except (ValueError, PermissionError) as e:
        # ValueError implies no database record exists.
        # PermissionError implies the refresh token itself has expired.
        logger.info("Authentication required for user %s: %s", user_id, e)
        
        # Proceed with generating the standard OAuth authorization flow
        auth_url = get_authorization_url()
        
        await update.message.reply_text(
            "Authentication is required. Please access the following URL:\n\n"
            f"{auth_url}\n\n"
            "Upon successful login, copy the complete redirect URL and submit it here."
        )
        
    except Exception as e:
        # Catch unexpected database or network exceptions during verification
        logger.error("Unexpected error during login verification for user %s: %s", user_id, e, exc_info=True)
        await update.message.reply_text(
            "An internal server error occurred while verifying your session. Please attempt the operation again later."
        )