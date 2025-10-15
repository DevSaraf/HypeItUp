import os
import requests
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()

BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1:free")

# 🔹 Generic OpenRouter call
def _call_openrouter(prompt, api_key):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an expert digital marketing AI specializing in viral campaigns, memes, and social trends.",
            },
            {"role": "user", "content": prompt},
        ],
    }

    try:
        r = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=90)
        
        # ✅ Handle OpenRouter 429 (Too Many Requests) gracefully
        if r.status_code == 429:
            print("⚠️ OpenRouter rate limit reached. Using fallback hashtags.")
            return """
            {
                "hashtags": ["#MarketingTips", "#SocialBuzz", "#ViralNow", "#Trendy2025", "#DigitalHype"],
                "tip": "Engage audiences with short, emotion-driven captions and trending sounds."
            }
            """
        
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print("⚠️ OpenRouter error:", e)
        return f"⚠️ OpenRouter error: {e}"



# 🔹 Main generator function
import os, requests

def generate_text(prompt, api_key=None):
    key = api_key or os.getenv("OPENROUTER_API_KEY")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek/deepseek-r1:free",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        data = response.json()

        # ✅ check before accessing
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        elif "error" in data:
            return f"⚠️ OpenRouter error: {data['error'].get('message', 'Unknown error')}"
        else:
            return "⚠️ Unexpected API response. Please try again later."

    except requests.exceptions.RequestException as e:
        return f"⚠️ Request failed: {e}"
    except Exception as e:
        return f"⚠️ Error generating content: {e}"


# 🔹 SERPAPI: Fetch trending topics (Trends + fallback to News)
def fetch_trending_keywords(region="India"):
    serp_key = os.getenv("SERPAPI_KEY")
    if not serp_key:
        return []

    geo_code = "IN" if "india" in region.lower() else "US"

    try:
        # Step 1: Try Google Trends
        params = {
            "engine": "google_trends",
            "q": "trending topics",
            "geo": geo_code,
            "api_key": serp_key
        }
        search = GoogleSearch(params)
        results = search.get_dict()

        trends = []

        # Extract from Trends API
        if "interest_over_time" in results:
            timeline = results["interest_over_time"].get("timeline_data", [])
            trends = list(
                {val["query"] for item in timeline for val in item.get("values", [])}
            )

        # Fallback to Google News
        if not trends:
            print("⚠️ No trends found in Trends API, using Google News fallback.")
            news_params = {
                "engine": "google_news",
                "q": "trending topics",
                "gl": geo_code.lower(),
                "api_key": serp_key
            }
            news_search = GoogleSearch(news_params)
            news_results = news_search.get_dict()
            news = news_results.get("news_results", [])
            trends = [n["title"] for n in news[:5]]

        print("🔥 Extracted trends:", trends)
        return trends[:5] if trends else []

    except Exception as e:
        print("⚠️ SerpAPI Error:", e)
        return []


# 🔹 SERPAPI: Fetch trending YouTube topics
def fetch_youtube_trends(keyword="viral memes"):
    serp_key = os.getenv("SERPAPI_KEY")
    if not serp_key:
        return []

    params = {
        "engine": "youtube",
        "search_query": keyword,
        "api_key": serp_key
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        videos = results.get("video_results", [])
        return [v["title"] for v in videos[:5]]
    except Exception as e:
        print("⚠️ SerpAPI YouTube Error:", e)
        return []
