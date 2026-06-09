import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.exceptions import UpworkAPIError, UpworkAuthError
from .handlers import fetch_jobs_callback, fetch_upwork_jobs, send_job_messages
from bot.utils import get_valid_access_token
from .oauth import get_authorization_url

logger = logging.getLogger(__name__)

async def fetch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Telegram job queue callback that orchestrates fetching Upwork jobs and sending them to the user.
    """
    
    user_id = update.effective_user.id
    user_data = context.user_data
    
    search_term: str = user_data.get("search", "")
    search_field = user_data.get("search_field","titleExpression_eq")
    
    logger.debug(context.application.user_data)
    
    try:
        await context.bot.send_message(user_id, f"Fetching new jobs...\nUsing search term: {search_term}\n")

        # 1. Authentication Retrieval
        access_token = await get_valid_access_token(user_id=user_id)
        if not access_token:
            await context.bot.send_message(user_id, "No access token found. Please /start first.")
            return

        # 2. Fetch Data from Upwork API
        jobs_data = await fetch_upwork_jobs(access_token, search_term,search_field=search_field)

        # 3. Dispatch Data to Telegram
        await send_job_messages(context.bot, user_id, jobs_data)

    except UpworkAuthError:
        await context.bot.send_message(user_id, "Access token expired or invalid. Please /login again.")
        
    except UpworkAPIError:
        await context.bot.send_message(user_id, "An error occurred while fetching jobs from Upwork. Please try again later.")
        
    except PermissionError as e:
        logger.warning(f"Terminal auth failure for chat {user_id}: {e}")
        context.job.schedule_removal()
        await context.bot.send_message(
            chat_id=user_id, 
            text="Your authentication session has fully expired. Please log in again using the /start or /auth command."
        )
        
    except Exception as e:
        logger.error(f"Unexpected error executing fetch_jobs for chat {user_id}: {e}", exc_info=True)
    
    
    
async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    message = "User data available:\n\n"
    user_data = context.application.user_data[user_id]
    
    for k, v in user_data.items():
        message += f"{k} = {v}\n"

    await update.message.reply_text(message)


async def unset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Insufficient arguments provided.\n"
            "Correct Usage: /unset <key>\n"
            "Example: /unset language"
        )
        return

    key = context.args[0]
    # 3. Store the extracted information in the user_data dictionary
    if context.user_data is not None and key in context.user_data:
        context.user_data.pop(key, None)

    await update.message.reply_text(
        f"Configuration updated successfully: **{key}** was removed.",
        parse_mode="Markdown",
    )


async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the /set command to store user-specific data.
    Expected format: /set <key> <value>
    """
    # 1. Validate the presence of sufficient arguments
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Insufficient arguments provided.\n"
            "Correct Usage: /set <key> <value>\n"
            "Example: /set language English"
        )
        return

    # 2. Parse the key and the corresponding value
    key = context.args[0]
    value = " ".join(context.args[1:])

    # 3. Store the extracted information in the user_data dictionary
    if context.user_data is not None:
        context.user_data[key] = value

    # 4. Transmit a confirmation message back to the user
    await update.message.reply_text(
        f"Configuration updated successfully: **{key}** is now set to **{value}**.",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Available commands:\n/start\n/help")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
                fetch_jobs_callback, interval=60 * 20, first=0, data=chat_id, name=job_name
            )
            await update.message.reply_text(
                "Background job fetching has been successfully resumed."
            )

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
        logger.error(
            "Unexpected error during login verification for user %s: %s",
            user_id,
            e,
            exc_info=True,
        )
        await update.message.reply_text(
            "An internal server error occurred while verifying your session. Please attempt the operation again later."
        )
