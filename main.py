import os
import feedparser
import google.generativeai as genai

# Ambil API Key dari Railway Variables
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Model Gemini
model = genai.GenerativeModel("gemini-1.5-flash")

# RSS Feed
feed = feedparser.parse("https://dpntimes.com/feed")

for entry in feed.entries[:1]:

    original_title = entry.title

    prompt = f"""
    Rewrite judul berita berikut menjadi lebih menarik
    dan SEO friendly:

    {original_title}
    """

    # Generate AI
    response = model.generate_content(prompt)

    rewritten = response.text

    print("HASIL AI:")
    print(rewritten)

print("BOT BERHASIL JALAN")
