
import pdb

import httpx
import os
from pathlib import Path
import asyncio
import dotenv

dotenv.load_dotenv()

token = os.getenv("UPWORK_ACCESS_TOKEN")

async def main():
    query = Path("./query.gql").read_text()
    payload = {
        "query": query,
        "variables": {
            "filter": {
                "pagination_eq": {"after": "0", "first":20}
            }
        }
    } 
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Authorization": f"Bearer {token}"
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
            print("Unauthorized. Check your access token.")
            return
            
        response.raise_for_status()
        if 'error' in response.text:
            print("GraphQL error:", response.text)
            return
        
        # Renamed the parsed response variable to avoid shadowing the request payload
        response_data = response.json()
        
        jobs = response_data.get("data", {}).get("marketplaceJobPostingsSearch", {})
        
        # Simplified the condition to check for empty dictionaries or None
        if not jobs or not jobs.get("edges"):
            print("No new jobs found.")
            return
        
        message = ""
        for job in jobs.get("edges", [])[:5]:
            node = job.get("node", {})
            title = node.get("title", "Untitled Job")
            
            # Upwork job URLs are constructed using the ciphertext, not a direct 'url' field
            ciphertext = node.get("ciphertext")
            url = f"https://www.upwork.com/jobs/{ciphertext}" if ciphertext else "URL not available"
            
            message += f"{title}\n{url}\n\n"

    print(message)


if __name__ == "__main__":
    asyncio.run(main())