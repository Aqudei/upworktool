from datetime import datetime, timedelta, timezone
import json
import logging

from bot.oauth import refresh_oauth_token

logger = logging.getLogger(__name__)

async def save_token_to_db(user_id, access_token, refresh_token, expires_at):
    # PRODUCTION REQUIREMENT: Replace with your Database ORM / secure storage logic
    token_data = {
        "user_id": user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at
    }
    with open(f"./upwork-token-{user_id}.json", "wt") as f:
        json.dump(token_data, f)

async def get_token_from_db(user_id: int) -> dict:
    # PRODUCTION REQUIREMENT: Replace with your Database ORM / secure storage logic
    try:
        with open(f"./upwork-token-{user_id}.json", "rt") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Token file not found for user {user_id}")
        return None



async def get_valid_access_token(user_id: int) -> str:
    """
    Retrieves the current access token. If it is expired or expiring within 60 seconds,
    it refreshes the token via the API, updates the database, and returns the new token.
    """
    # 1. Retrieve the current token record from the database
    token_record = await get_token_from_db(user_id)
    if not token_record:
        raise ValueError("No authentication record found for user.")

    expires_at = datetime.fromtimestamp(token_record["expires_at"], tz=timezone.utc)
    
    # 2. Add a buffer (e.g., 60 seconds) to prevent failing requests in transit
    if datetime.now(timezone.utc) >= (expires_at - timedelta(seconds=60)):
        logger.info(f"Token expired for user {user_id}. Executing refresh workflow.")
        
        # 3. Call your OAuth provider's refresh endpoint
        new_token_data = await refresh_oauth_token(token_record["refresh_token"])
        
        if "access_token" not in new_token_data:
            logger.error(f"Failed to refresh token for user {user_id}: {new_token_data}")
            raise PermissionError("Refresh token is invalid or expired. Re-authentication required.")

        new_expires_in = new_token_data.get("expires_in", 3600)
        new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_expires_in)
        
        # If the provider doesn't return a new refresh token, keep the old one
        new_refresh_token = new_token_data.get("refresh_token", token_record["refresh_token"])

        # 4. Save the refreshed credentials back to the database
        await save_token_to_db(
            user_id=user_id,
            access_token=new_token_data["access_token"],
            refresh_token=new_refresh_token,
            expires_at=new_expires_at.timestamp()
        )
        return new_token_data["access_token"]

    # 5. Token is still valid; return the existing one
    return token_record["access_token"]