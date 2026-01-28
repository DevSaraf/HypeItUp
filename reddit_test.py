# reddit_test.py
import os
from dotenv import load_dotenv
import praw

load_dotenv()

def get_reddit_client():
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")
    user_agent = os.getenv("REDDIT_USER_AGENT", f"HypeItUpBot/0.1 (by u/{username})")

    if not all([client_id, client_secret, username, password]):
        raise SystemExit("Missing one or more reddit credentials in .env")

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        user_agent=user_agent,
        check_for_async=False
    )
    return reddit

if __name__ == "__main__":
    reddit = get_reddit_client()
    try:
        me = reddit.user.me()  # will raise if auth fails
        print("✅ Authenticated as:", me)
    except Exception as e:
        print("❌ Reddit auth failed:", e)
