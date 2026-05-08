import os
import feedparser
import google.generativeai as genai
import requests

# Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.0-flash")

# RSS Feed
feed = feedparser.parse("https://dpntimes.com/feed")

# WordPress Config
WP_URL = "https://sulsel.dpntimes.com/wp-json/wp/v2/posts"
WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

for entry in feed.entries[:1]:

    original_title = entry.title

    prompt = f"""
    Rewrite judul berita berikut menjadi lebih menarik
    dan SEO friendly:

    {original_title}
    """

    response = model.generate_content(prompt)

    rewritten = response.text

    print("HASIL AI:")
    print(rewritten)

    # Data post WordPress
    data = {
        "title": rewritten,
        "content": rewritten,
        "status": "draft"
    }

    # Publish ke WordPress
    wp_response = requests.post(
        WP_URL,
        json=data,
        auth=(WP_USER, WP_APP_PASSWORD)
    )

    print("WORDPRESS STATUS:")
    print(wp_response.status_code)

print("BOT BERHASIL JALAN")
