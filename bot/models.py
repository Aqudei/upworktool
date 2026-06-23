from tinydb import TinyDB, Query

DATABASE_FILE = "./data/database.json"


def mark_sent(chat_id: int, ids: list[int]):
    with TinyDB(DATABASE_FILE) as db:
        db.update({"sent": True}, doc_ids=ids)


def get_sending_jobs(chat_id: int) -> None:
    with TinyDB(DATABASE_FILE) as db:
        Job = Query()
        jobs = db.search((Job.sent == False) & (Job.chat_id == chat_id))
        return jobs


def save_jobs(chat_id: int, jobs_data: dict) -> None:

    edges = jobs_data.get("edges", [])
    if not edges:
        return

    with TinyDB(DATABASE_FILE) as db:
        for job in edges:
            node = job.get("node", {})
            title = node.get("title", "Untitled Job")
            ciphertext = node.get("ciphertext")
            url = f"https://www.upwork.com/jobs/{ciphertext}" if ciphertext else "URL not available"
            createdDateTime = node.get("createdDateTime")

            Job = Query()
            items = db.search((Job.ciphertext ==
                              ciphertext) & (Job.chat_id == chat_id))

            if len(items) > 0:
                continue

            db.insert(
                {
                    "title": title,
                    "url": url,
                    "ciphertext": ciphertext,
                    "chat_id": chat_id,
                    "createdDateTime": createdDateTime,
                    "description": node.get("description"),
                    "sent": False
                }
            )
