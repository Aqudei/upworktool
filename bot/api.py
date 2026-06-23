import httpx

from bot.exceptions import UpworkAPIError, UpworkAuthError
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


async def fetch_upwork_jobs_async(access_token: str, search_term: str, search_field: str = 'searchExpression_eq') -> dict:
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
                search_field: 'title:(python OR integration OR desktop OR "export tool" OR "import tool" OR "C#" OR ".NET" OR Windows OR API OR Backend) OR (title:urgent AND title:python)',
            }
        }
    }

    if search_term and search_term.strip():
        payload['variables']['filter'][search_field] = search_term.strip()

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
