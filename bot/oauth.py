import os
import secrets
from urllib.parse import urlencode

CLIENT_ID = os.getenv("UPWORK_CLIENT_ID")
REDIRECT_URI = os.getenv("UPWORK_REDIRECT_URI")

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