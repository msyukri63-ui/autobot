import os
import time
import requests
import feedparser

from google import genai
from google.genai.errors import APIError

# =========================
# GEMINI CONFIG
# =========================

API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY)

MODEL_NAME = "gemini-1.5-flash"

# =========================
# WORDPRESS CONFIG
# =========================

WP_URL = "https://sulsel.dpntimes.com/wp-json/wp/v2/posts"

WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

# =========================
# RSS FEED
# =========================

feed = feedparser.parse("https://dpntimes.com/feed")

# =========================
# LOOP POST
# =========================

for entry in feed.entries[:1]:

    original_title = entry.title

    prompt = f"""
Rewrite judul berita berikut menjadi lebih menarik,
SEO friendly, natural, dan tidak clickbait berlebihan.

Judul:
{original_title}

Hasil:
"""

    rewritten = None

    # =========================
    # RETRY GEMINI
    # =========================

    for attempt in range(5):

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )

            rewritten = response.text.strip()

            break

        except APIError as e:

            print(f"[GEMINI ERROR] Attempt {attempt+1}: {e}")

            # Retry kalau quota/rate limit
            if "429" in str(e):

                wait_time = 5 * (attempt + 1)

                print(f"Retry dalam {wait_time} detik...")

                time.sleep(wait_time)

            else:
                raise

    # =========================
    # VALIDASI RESPONSE
    # =========================

    if not rewritten:

        print("Gagal generate judul AI")
        continue

    print("\n=== HASIL AI ===")
    print(rewritten)

    # =========================
    # DATA WORDPRESS
    # =========================

    data = {
        "title": rewritten,
        "content": f"<p>{rewritten}</p>",
        "status": "draft"
    }

    # =========================
    # POST KE WORDPRESS
    # =========================

    try:

        wp_response = requests.post(
            WP_URL,
            json=data,
            auth=(WP_USER, WP_APP_PASSWORD),
            timeout=30
        )

        print("\n=== WORDPRESS STATUS ===")
        print(wp_response.status_code)

        # Debug response
        if wp_response.status_code not in [200, 201]:

            print(wp_response.text)

    except requests.exceptions.RequestException as e:

        print(f"[WORDPRESS ERROR] {e}")

print("\nBOT BERHASIL JALAN")
