import google.generativeai as genai
import feedparser
import requests

genai.configure(api_key="API_KEY")

model = genai.GenerativeModel("gemini-1.5-flash")

# RSS Feed
feed = feedparser.parse("https://dpntimes.com/feed")

# WordPress Config
WP_URL = "https://sulsel.dpntimes.com/wp-json/wp/v2/posts"
WP_USER = "dpntimes"
WP_APP_PASSWORD = "DPN2021Patar@01"

for entry in feed.entries[:1]:

    # Ambil judul
    original_title = entry.title

    # Prompt rewrite
    prompt = f"""
    Rewrite judul berita berikut menjadi lebih menarik
    dan SEO friendly:

    {original_title}
    """

    # AI Rewrite
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    rewritten = response.choices[0].message.content

    print("HASIL AI:")
    print(rewritten)

    # Data WordPress
    data = {
        "title": rewritten,
        "content": rewritten,
        "status": "draft"
    }

    # Publish ke WordPress
    data = {
        "title": rewritten,
        "content": rewritten,
        "status": "draft"
    }

    wp_response = requests.post(
        WP_URL,
        json=data,
        auth=(WP_USER, WP_APP_PASSWORD)
    )

    print(wp_response.status_code)
