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
from dotenv import load_dotenv

from google import genai
from google.genai import types

# =========================================
# LOAD ENV
# =========================================

load_dotenv()

GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", "").split(",")

MODELS = os.getenv(
    "MODELS",
    "gemini-2.0-flash,gemini-2.5-flash"
).split(",")

RSS_FEED_URL = os.getenv("RSS_FEED_URL")

WORDPRESS_URL = os.getenv("WORDPRESS_URL")

WORDPRESS_MEDIA_URL = os.getenv("WORDPRESS_MEDIA_URL")

WORDPRESS_TAGS_URL = os.getenv(
    "WORDPRESS_TAGS_URL",
    "https://sulsel.dpntimes.com/wp-json/wp/v2/tags"
)

WP_USERNAME = os.getenv("WP_USERNAME")

WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

POST_STATUS = os.getenv("POST_STATUS", "draft")

DELAY_BETWEEN_POSTS = int(
    os.getenv("DELAY_BETWEEN_POSTS", 60)
)

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

    try:

        with open(CACHE_FILE, "r") as f:
            return json.load(f)

    except:
        return []

def save_posted(url):

    data = load_posted()

    if url not in data:
        data.append(url)

    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

# =========================================
# GET RSS
# =========================================

def get_feed():

    logging.info("Fetching RSS Feed...")

    feed = feedparser.parse(RSS_FEED_URL)

    return feed.entries

# =========================================
# SCRAPE ARTICLE
# =========================================

def scrape_article(url):

    logging.info(f"Scraping article: {url}")

    article = Article(url)

    article.download()
    article.parse()

    content = article.text.strip()

    if len(content) < 300:
        raise Exception("Article content too short")

    return {
        "title": article.title,
        "text": content,
        "image": article.top_image
    }

# =========================================
# CLEAN JSON RESPONSE
# =========================================

def clean_json_response(text):

    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text)

    text = text.strip()

    return text

# =========================================
# GEMINI REWRITE
# =========================================

def rewrite_article(title, content):

    prompt = f"""
Rewrite berita berikut menjadi artikel baru yang unik,
natural, human readable, SEO friendly,
dan bukan hasil copy paste.

WAJIB:
- Bahasa Indonesia profesional
- Gaya media online Indonesia
- Minimal 900 kata
- Gunakan heading H2 dan H3
- Tambahkan FAQ
- Tambahkan kesimpulan
- Tambahkan bullet point jika perlu
- Jangan menyebut rewrite AI
- Jangan copy struktur asli
- Artikel harus lolos plagiarism checker
- Fokus SEO organik Google

Buat output JSON VALID tanpa markdown:

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
    random.shuffle(MODELS)

    for api_key in GEMINI_API_KEYS:

        api_key = api_key.strip()

        if not api_key:
            continue

        client = genai.Client(api_key=api_key)

        for model in MODELS:

            model = model.strip()

            try:

                logging.info(
                    f"Trying model: {model}"
                )

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.9,
                        max_output_tokens=7000,
                    )
                )

                text = response.text

                text = clean_json_response(text)

                result = json.loads(text)

                logging.info(
                    f"Rewrite success using {model}"
                )

                return result

            except Exception as e:

                logging.error(
                    f"[GEMINI ERROR] {model}: {e}"
                )

                time.sleep(10)

    return None

# =========================================
# DOWNLOAD IMAGE
# =========================================

def download_image(url):

    if not url:
        return None

    try:

        logging.info("Downloading image...")

        response = requests.get(
            url,
            timeout=30
        )

        if response.status_code != 200:
            return None

        filename = "featured.jpg"

        with open(filename, "wb") as f:
            f.write(response.content)

        return filename

    except Exception as e:

        logging.error(e)

        return None

# =========================================
# UPLOAD IMAGE TO WORDPRESS
# =========================================

def upload_image_to_wp(image_path):

    if not image_path:
        return None

    logging.info("Uploading image to WordPress...")

    headers = {
        "Content-Disposition":
        f'attachment; filename={os.path.basename(image_path)}'
    }

    try:

        with open(image_path, "rb") as img:

            response = requests.post(
                WORDPRESS_MEDIA_URL,
                headers=headers,
                data=img,
                auth=(WP_USERNAME, WP_APP_PASSWORD),
                timeout=60
            )

        if response.status_code in [200, 201]:

            media_id = response.json()["id"]

            logging.info(
                f"Image uploaded ID: {media_id}"
            )

            return media_id

        logging.error(response.text)

        return None

    except Exception as e:

        logging.error(e)

        return None

# =========================================
# CREATE TAGS
# =========================================

def create_tags(tags):

    tag_ids = []

    for tag in tags:

        try:

            response = requests.post(
                WORDPRESS_TAGS_URL,
                auth=(WP_USERNAME, WP_APP_PASSWORD),
                json={"name": tag},
                timeout=30
            )

            if response.status_code in [200, 201]:

                tag_ids.append(
                    response.json()["id"]
                )

            elif response.status_code == 400:

                search = requests.get(
                    WORDPRESS_TAGS_URL,
                    params={"search": tag},
                    auth=(WP_USERNAME, WP_APP_PASSWORD)
                )

                data = search.json()

                if data:
                    tag_ids.append(data[0]["id"])

        except Exception as e:

            logging.error(e)

    return tag_ids

# =========================================
# POST TO WORDPRESS
# =========================================

def post_to_wordpress(article_data, featured_media):

    logging.info("Posting article to WordPress...")

    slug = slugify(article_data["title"])

    tag_ids = create_tags(
        article_data.get("tags", [])
    )

    payload = {
        "title": article_data["title"],
        "slug": slug,
        "content": article_data["content"],
        "excerpt": article_data["excerpt"],
        "status": POST_STATUS,
        "featured_media": featured_media,
        "tags": tag_ids
    }

    try:

        response = requests.post(
            WORDPRESS_URL,
            auth=(WP_USERNAME, WP_APP_PASSWORD),
            json=payload,
            timeout=60
        )

        if response.status_code in [200, 201]:

            logging.info("SUCCESS POST")

            return True

        logging.error(response.text)

        return False

    except Exception as e:

        logging.error(e)

        return False

# =========================================
# MAIN
# =========================================

def main():

    logging.info("BOT STARTED")

    entries = get_feed()

    posted = load_posted()

    for item in entries:

        try:

            url = item.link

            if url in posted:

                logging.info(
                    f"Already posted: {url}"
                )

                continue

            logging.info(
                f"Processing: {url}"
            )

            data = scrape_article(url)

            rewritten = rewrite_article(
                data["title"],
                data["text"]
            )

            if not rewritten:

                logging.error(
                    "Rewrite failed"
                )

                continue

            image_path = download_image(
                data["image"]
            )

            media_id = upload_image_to_wp(
                image_path
            )

            success = post_to_wordpress(
                rewritten,
                media_id
            )

            if success:

                save_posted(url)

            logging.info(
                f"Sleeping {DELAY_BETWEEN_POSTS}s"
            )

            time.sleep(DELAY_BETWEEN_POSTS)

        except Exception as e:

            logging.error(e)

            continue

# =========================================
# RUN
# =========================================

if __name__ == "__main__":

    main()
