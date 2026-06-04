import json
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes
import httpx
from urllib.parse import urlparse, parse_qs
import os

CLIENT_ID = os.getenv("UPWORK_CLIENT_ID")
CLIENT_SECRET = os.getenv("UPWORK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("UPWORK_REDIRECT_URI")

async def exchange_code_for_token(code):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.upwork.com/api/v3/oauth2/token/",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            headers=headers,
        )
        response.raise_for_status()

        return response.json()


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(f"You said: {text}")
    
    
async def fetch_jobs(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    await context.bot.send_message(chat_id, "Fetching new jobs...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    access_token = context.user_data.get("access_token")
    if not access_token:
        await context.bot.send_message(chat_id, "No access token found. Please /login first.")
        return
    headers["Authorization"] = f"Bearer {access_token}"
    
    query = Path("./query.gql").read_text()
    payload = {
        "query": query,
        # "variables": {
        #     "filter": {
        #         "searchTerm_eq": "python OR desktop"
        #     }
        # }
    } 
    
    # Assuming the GraphQL query and variables are stored in a dictionary named 'payload'
    async with httpx.AsyncClient() as client:
        # GraphQL requests require a POST method and a JSON payload
        response = await client.post(
            "https://api.upwork.com/graphql",
            headers=headers,
            json=payload 
        )
        
        if response.status_code == 401:
            await context.bot.send_message(chat_id, "Access token expired or invalid. Please /login again.")
            return
            
        response.raise_for_status()
        
        # Renamed the parsed response variable to avoid shadowing the request payload
        response_data = response.json()
        jobs = response_data.get("data", {}).get("marketplaceJobPostingsSearch", {})
        
        # Simplified the condition to check for empty dictionaries or None
        if not jobs or not jobs.get("edges"):
            await context.bot.send_message(chat_id, "No new jobs found.")
            return
        
        message = ""
        for job in jobs.get("edges", [])[:5]:
            node = job.get("node", {})
            title = node.get("title", "Untitled Job")
            
            # Upwork job URLs are constructed using the ciphertext, not a direct 'url' field
            ciphertext = node.get("ciphertext")
            url = f"https://www.upwork.com/jobs/~{ciphertext}" if ciphertext else "URL not available"
            
            message += f"{title}\n{url}\n\n"
            
        await context.bot.send_message(chat_id, message)


async def parse_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "code=" not in text:
        return

    parsed = urlparse(text)
    params = parse_qs(parsed.query)

    code = params.get("code", [None])[0]

    context.user_data["auth_code"] = code

    await update.message.reply_text(
        f"Authorization code received:\n{code}"
    )

    token = await exchange_code_for_token(code)
    with open("./upwork-token.json", "wt") as f:
        f.write(json.dumps(token))
    
    context.user_data["access_token"] = token["access_token"]
    
    await update.message.reply_text(
        f"Access Token:\n{token['access_token']}"
    )
    
    context.job_queue.run_repeating(fetch_jobs, interval=60*60, first=0, data=update.effective_chat.id)    
    await update.message.reply_text(
        f"Job fetching started. You will receive updates every hour."
    )