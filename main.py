import os
import re
import json
import time
import random
import logging
import requests
import feedparser

from bs4 import BeautifulSoup
from newspaper import Article
from slugify import slugify

from google import genai
from google.genai import types

from config import *

# =========================================
# LOGGING
# =========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# =========================================
# CACHE
# =========================================

CACHE_FILE = "posted.json"

if not os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "w") as f:
        json.dump([], f)

def load_posted():

    with open(CACHE_FILE, "r") as f:
        return json.load(f)

def save_posted(url):

    data = load_posted()

    data.append(url)

    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

# =========================================
# GET RSS
# =========================================

def get_feed():

    feed = feedparser.parse(RSS_FEED_URL)

    return feed.entries

# =========================================
# SCRAPE ARTICLE
# =========================================

def scrape_article(url):

    article = Article(url)

    article.download()
    article.parse()

    return {
        "title": article.title,
        "text": article.text,
        "image": article.top_image
    }

# =========================================
# GEMINI REWRITE
# =========================================

def rewrite_article(title, content):

    prompt = f"""
Rewrite berita berikut menjadi artikel baru yang unik,
natural, human readable, dan bukan hasil copy paste.

WAJIB:
- Tidak plagiarisme
- Gaya media online Indonesia
- SEO friendly
- Panjang minimal 900 kata
- Gunakan heading H2 dan H3
- Tambahkan FAQ
- Tambahkan kesimpulan
- Jangan menyebut rewrite
- Jangan copy struktur asli

Buat output JSON valid seperti ini:

{{
  "title": "",
  "focus_keyword": "",
  "lsi_keywords": [],
  "tags": [],
  "excerpt": "",
  "meta_description": "",
  "content": ""
}}

Judul asli:
{title}

Isi berita:
{content}
"""

    random.shuffle(GEMINI_API_KEYS)

    for key in GEMINI_API_KEYS:

        client = genai.Client(api_key=key)

        for model in MODELS:

            try:

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.9,
                        max_output_tokens=6000,
                    )
                )

                text = response.text

                text = re.sub(r"```json", "", text)
                text = re.sub(r"```", "", text)

                return json.loads(text)

            except Exception as e:

                logging.error(e)

                time.sleep(15)

    return None

# =========================================
# DOWNLOAD IMAGE
# =========================================

def download_image(url):

    if not url:
        return None

    response = requests.get(url)

    filename = "featured.jpg"

    with open(filename, "wb") as f:
        f.write(response.content)

    return filename

# =========================================
# UPLOAD IMAGE TO WP
# =========================================

def upload_image_to_wp(image_path):

    if not image_path:
        return None

    headers = {
        "Content-Disposition": f'attachment; filename={os.path.basename(image_path)}'
    }

    with open(image_path, "rb") as img:

        response = requests.post(
            WORDPRESS_MEDIA_URL,
            headers=headers,
            data=img,
            auth=(WP_USERNAME, WP_APP_PASSWORD)
        )

    if response.status_code in [200, 201]:

        return response.json()["id"]

    logging.error(response.text)

    return None

# =========================================
# CREATE TAGS
# =========================================

def create_tags(tags):

    tag_ids = []

    for tag in tags:

        response = requests.post(
            "https://sulsel.dpntimes.com/wp-json/wp/v2/tags",
            auth=(WP_USERNAME, WP_APP_PASSWORD),
            json={"name": tag}
        )

        if response.status_code in [200, 201]:

            tag_ids.append(response.json()["id"])

    return tag_ids

# =========================================
# POST TO WORDPRESS
# =========================================

def post_to_wordpress(article_data, featured_media):

    slug = slugify(article_data["title"])

    tag_ids = create_tags(article_data["tags"])

    payload = {
        "title": article_data["title"],
        "slug": slug,
        "content": article_data["content"],
        "excerpt": article_data["excerpt"],
        "status": POST_STATUS,
        "featured_media": featured_media,
        "tags": tag_ids
    }

    response = requests.post(
        WORDPRESS_URL,
        auth=(WP_USERNAME, WP_APP_PASSWORD),
        json=payload
    )

    if response.status_code in [200, 201]:

        logging.info("SUCCESS POST")

        return True

    logging.error(response.text)

    return False

# =========================================
# MAIN
# =========================================

def main():

    entries = get_feed()

    posted = load_posted()

    for item in entries:

        url = item.link

        if url in posted:
            continue

        logging.info(f"Processing: {url}")

        try:

            data = scrape_article(url)

            rewritten = rewrite_article(
                data["title"],
                data["text"]
            )

            if not rewritten:
                continue

            image_path = download_image(data["image"])

            media_id = upload_image_to_wp(image_path)

            success = post_to_wordpress(
                rewritten,
                media_id
            )

            if success:

                save_posted(url)

            time.sleep(DELAY_BETWEEN_POSTS)

        except Exception as e:

            logging.error(e)

if __name__ == "__main__":
    main()
