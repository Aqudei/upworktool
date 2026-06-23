import os
import logging
from bot.api import fetch_upwork_jobs_async
from bot.exceptions import UpworkAPIError, UpworkAuthError
from telegram.ext import ContextTypes


from bot.models import get_sending_jobs, mark_sent, save_jobs
from bot.utils import get_valid_access_token, send_job_messages

CLIENT_ID = os.getenv("UPWORK_CLIENT_ID")
CLIENT_SECRET = os.getenv("UPWORK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("UPWORK_REDIRECT_URI")

logger = logging.getLogger(__name__)


async def create_repeating_job(context: ContextTypes.DEFAULT_TYPE, job_name, chat_id, callback, interval_minutes=10):

    current_jobs = context.job_queue.get_jobs_by_name(job_name)

    if current_jobs:
        return False

    context.job_queue.run_repeating(
        callback,
        interval=60 * interval_minutes,
        first=0,
        data=chat_id,
        name=job_name,
    )

    return True  # created successfully


async def send_jobs_callback(context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram job queue callback that orchestrates fetching Upwork jobs and sending them to the user.
    """
    chat_id = context.job.data
    user_data = context.application.user_data.get(chat_id, {})

    search_term: str = user_data.get("search", "")
    search_field = user_data.get("search_field", "searchExpression_eq")
    logger.debug(context.application.user_data)
    try:
        jobs_data = get_sending_jobs(chat_id)
        await send_job_messages(context.bot, chat_id, jobs_data)
        doc_ids = [j['doc_id'] for j in jobs_data]
        mark_sent(chat_id, doc_ids)

    except UpworkAuthError:
        # await context.bot.send_message(chat_id, "Access token expired or invalid. Please /login again.")
        logger.info("Access token expired or invalid. Please /login again.")
    except UpworkAPIError:
        # await context.bot.send_message(chat_id, "An error occurred while fetching jobs from Upwork. Please try again later.")
        logger.info(
            "An error occurred while fetching jobs from Upwork. Please try again later.")
    except PermissionError as e:
        logger.warning(f"Terminal auth failure for chat {chat_id}: {e}")
        context.job.schedule_removal()
        await context.bot.send_message(
            chat_id=chat_id,
            text="Your authentication session has fully expired. Please log in again using the /start or /auth command."
        )
        logger.info(
            "Your authentication session has fully expired. Please log in again using the /start or /auth command.")

    except Exception as e:
        logger.error(
            f"Unexpected error executing fetch_jobs for chat {chat_id}: {e}", exc_info=True)


async def fetch_jobs_callback(context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram job queue callback that orchestrates fetching Upwork jobs and sending them to the user.
    """
    chat_id = context.job.data
    user_data = context.application.user_data.get(chat_id, {})

    search_term: str = user_data.get("search", "")
    search_field = user_data.get("search_field", "searchExpression_eq")
    logger.debug(context.application.user_data)
    try:
        # await context.bot.send_message(chat_id, f"Fetching new jobs...\nUsing search term: {search_term}\n")
        logger.info(
            f"Fetching new jobs...\nUsing search term: {search_term}\n")

        # 1. Authentication Retrieval
        access_token = await get_valid_access_token(user_id=chat_id)
        if not access_token:
            # await context.bot.send_message(chat_id, "No access token found. Please /start first.")
            logger.info("No access token found. Please /start first.")
            return

        # 2. Fetch Data from Upwork API
        jobs_data = await fetch_upwork_jobs_async(access_token, search_term, search_field=search_field)
        save_jobs(chat_id, jobs_data)

        # 3. Dispatch Data to Telegram
        # await send_job_messages(context.bot, chat_id, jobs_data)

    except UpworkAuthError:
        # await context.bot.send_message(chat_id, "Access token expired or invalid. Please /login again.")
        logger.info("Access token expired or invalid. Please /login again.")
    except UpworkAPIError:
        # await context.bot.send_message(chat_id, "An error occurred while fetching jobs from Upwork. Please try again later.")
        logger.info(
            "An error occurred while fetching jobs from Upwork. Please try again later.")
    except PermissionError as e:
        logger.warning(f"Terminal auth failure for chat {chat_id}: {e}")
        context.job.schedule_removal()
        await context.bot.send_message(
            chat_id=chat_id,
            text="Your authentication session has fully expired. Please log in again using the /start or /auth command."
        )
        logger.info(
            "Your authentication session has fully expired. Please log in again using the /start or /auth command.")

    except Exception as e:
        logger.error(
            f"Unexpected error executing fetch_jobs for chat {chat_id}: {e}", exc_info=True)
