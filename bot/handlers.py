import json
from pathlib import Path
from bot.exceptions import UpworkAPIError, UpworkAuthError
from telegram import Update
from telegram.ext import ContextTypes
import httpx
from urllib.parse import urlparse, parse_qs
import os
from datetime import datetime, timedelta,timezone
import logging

from bot.oauth import exchange_code_for_token
from bot.utils import get_valid_access_token, save_token_to_db

CLIENT_ID = os.getenv("UPWORK_CLIENT_ID")
CLIENT_SECRET = os.getenv("UPWORK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("UPWORK_REDIRECT_URI")

logger = logging.getLogger(__name__)

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(f"You said: {text}")
    

async def fetch_upwork_jobs(access_token: str, search_term: str) -> dict:
    """
    Fetches job postings from the Upwork GraphQL API.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Authorization": f"Bearer {access_token}"
    }
    
    query = Path("./query.gql").read_text()
    payload = {
        "query": query,
        "variables": {
            "filter": {
                "pagination_eq": {"after": "0", "first": 20},
                "titleExpression_eq": "(python OR integration OR urgent OR desktop OR export OR C# OR windows OR API OR Backend)",
            }
        }
    } 
    
    if search_term and search_term.strip():
        payload['variables']['filter']['titleExpression_eq'] = search_term.strip()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.upwork.com/graphql",
            headers=headers,
            json=payload 
        )
        
        if response.status_code in [401, 403]:
            raise UpworkAuthError("Access token expired or invalid.")
            
        response.raise_for_status()
        response_data = response.json()
        
        if 'errors' in response_data:
            logger.error(f"GraphQL error response: {response.text}")
            raise UpworkAPIError("GraphQL response contained errors.")
        
        return response_data.get("data", {}).get("marketplaceJobPostingsSearch", {})


async def send_job_messages(bot, chat_id: int, jobs_data: dict) -> None:
    """
    Formats and sends job listings to a Telegram chat, adhering to message length limits.
    """
    total_count = jobs_data.get("totalCount", 0)
    await bot.send_message(chat_id, f"Total jobs found: {total_count}")
    
    edges = jobs_data.get("edges", [])
    if not edges:
        await bot.send_message(chat_id, "No new jobs found.")
        return
    
    MAX_MESSAGE_LENGTH = 4096 
    message_buffer = ""

    for job in edges:
        node = job.get("node", {})
        title = node.get("title", "Untitled Job")
        ciphertext = node.get("ciphertext")
        url = f"https://www.upwork.com/jobs/{ciphertext}" if ciphertext else "URL not available"
        
        job_text = f"{title}\n{url}\n\n"
        
        if len(message_buffer) + len(job_text) > MAX_MESSAGE_LENGTH:
            await bot.send_message(chat_id=chat_id, text=message_buffer)
            message_buffer = ""
            
        message_buffer += job_text

    if message_buffer.strip():
        await bot.send_message(chat_id=chat_id, text=message_buffer)

async def fetch_jobs_callback(context: ContextTypes.DEFAULT_TYPE):
    """
    Telegram job queue callback that orchestrates fetching Upwork jobs and sending them to the user.
    """
    chat_id = context.job.data
    user_data = context.application.user_data.get(chat_id, {})
    
    search_term: str = user_data.get("search", "")
    logger.debug(context.application.user_data)
    
    try:
        await context.bot.send_message(chat_id, f"Fetching new jobs...\nUsing search term: {search_term}\n")

        # 1. Authentication Retrieval
        access_token = await get_valid_access_token(user_id=chat_id)
        if not access_token:
            await context.bot.send_message(chat_id, "No access token found. Please /start first.")
            return

        # 2. Fetch Data from Upwork API
        jobs_data = await fetch_upwork_jobs(access_token, search_term)

        # 3. Dispatch Data to Telegram
        await send_job_messages(context.bot, chat_id, jobs_data)

    except UpworkAuthError:
        await context.bot.send_message(chat_id, "Access token expired or invalid. Please /login again.")
        
    except UpworkAPIError:
        await context.bot.send_message(chat_id, "An error occurred while fetching jobs from Upwork. Please try again later.")
        
    except PermissionError as e:
        logger.warning(f"Terminal auth failure for chat {chat_id}: {e}")
        context.job.schedule_removal()
        await context.bot.send_message(
            chat_id=chat_id, 
            text="Your authentication session has fully expired. Please log in again using the /start or /auth command."
        )
        
    except Exception as e:
        logger.error(f"Unexpected error executing fetch_jobs for chat {chat_id}: {e}", exc_info=True)
    
        
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
            logger.error("Token exchange failed or returned invalid data: %s", token_data)
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

        # Clear existing jobs for this chat to prevent duplicate polling
        job_name = f"fetch_jobs_{update.effective_chat.id}"
        current_jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in current_jobs:
            job.schedule_removal()

        # Schedule the new background job
        context.job_queue.run_repeating(
            fetch_jobs_callback, 
            interval=60 * 15, 
            first=0, 
            data=update.effective_chat.id,
            name=job_name
        )    
        
        await update.message.reply_text("Authentication successful. Job fetching started. You will receive updates every 15 minutes.")

    except Exception as e:
        logger.error("Unexpected error during OAuth redirect parsing: %s", e, exc_info=True)
        await update.message.reply_text("An internal error occurred during the authentication process.")