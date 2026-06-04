import os
import secrets
from urllib.parse import urlencode

import httpx

CLIENT_ID = os.getenv("UPWORK_CLIENT_ID")
REDIRECT_URI = os.getenv("UPWORK_REDIRECT_URI")
CLIENT_SECRET = os.getenv("UPWORK_CLIENT_SECRET")


async def refresh_oauth_token(refresh_token):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.upwork.com/api/v3/oauth2/token/",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            headers=headers,
        )
        response.raise_for_status()

        return response.json()

def get_authorization_url():

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
    }

    auth_url = (
        "https://www.upwork.com/ab/account-security/oauth2/authorize?"
        + urlencode(params)
    )

    return auth_url

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