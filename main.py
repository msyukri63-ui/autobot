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

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)

logging.info("BOT STARTED")

# =========================================
# HEADERS
# =========================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

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
        json.dump(data, f, indent=2)


# =========================================
# GET RSS
# =========================================

def get_feed():

    logging.info("Fetching RSS Feed...")

    feed = feedparser.parse(RSS_FEED_URL)

    return feed.entries


# =========================================
# CLEAN TEXT
# =========================================

def clean_text(text):

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================
# SCRAPE ARTICLE
# =========================================

def scrape_article(url):

    logging.info(f"Scraping article: {url}")

    # =====================================
    # METHOD 1 -> newspaper3k
    # =====================================

    try:

        article = Article(url)

        article.download()
        article.parse()

        text = clean_text(article.text)

        if len(text) > 300:

            logging.info("SUCCESS scrape via newspaper3k")

            return {
                "title": article.title,
                "text": text,
                "image": article.top_image
            }

        logging.warning("newspaper3k gagal, fallback bs4...")

    except Exception as e:

        logging.error(f"Newspaper error: {e}")

    # =====================================
    # METHOD 2 -> BeautifulSoup fallback
    # =====================================

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        soup = BeautifulSoup(response.text, "html.parser")

        # =====================================
        # TITLE
        # =====================================

        title = ""

        title_selectors = [
            "h1.entry-title",
            "h1.tdb-title-text",
            "h1"
        ]

        for selector in title_selectors:

            element = soup.select_one(selector)

            if element:
                title = element.get_text(strip=True)
                break

        # =====================================
        # CONTENT
        # =====================================

        content_selectors = [
            ".td-post-content",
            ".entry-content",
            ".post-content",
            "article",
            ".content"
        ]

        content = ""

        for selector in content_selectors:

            body = soup.select_one(selector)

            if body:

                paragraphs = body.find_all("p")

                content = "\n".join(
                    p.get_text(strip=True)
                    for p in paragraphs
                )

                content = clean_text(content)

                if len(content) > 500:
                    break

        # =====================================
        # IMAGE
        # =====================================

        image = None

        og_image = soup.find(
            "meta",
            property="og:image"
        )

        if og_image:
            image = og_image.get("content")

        if len(content) < 200:
            raise Exception("Konten masih terlalu pendek")

        logging.info("SUCCESS scrape via BeautifulSoup")

        return {
            "title": title,
            "text": content,
            "image": image
        }

    except Exception as e:

        logging.error(f"BS4 scrape gagal: {e}")

        return None


# =========================================
# GEMINI REWRITE
# =========================================

def rewrite_article(title, content):

    logging.info("Rewriting article with Gemini AI...")

    prompt = f"""
Rewrite berita berikut menjadi artikel baru yang unik,
natural, human readable, dan bukan hasil copy paste.

WAJIB:
- Tidak plagiarisme
- Gaya media online Indonesia
- SEO friendly
- Minimal 900 kata
- Gunakan heading H2 dan H3
- Tambahkan FAQ
- Tambahkan kesimpulan
- Tambahkan bullet points bila perlu
- Jangan menyebut rewrite AI
- Jangan copy struktur asli

Buat output JSON VALID seperti ini:

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

        try:

            client = genai.Client(api_key=key)

            for model in MODELS:

                try:

                    logging.info(f"Trying model: {model}")

                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.9,
                            max_output_tokens=7000,
                        )
                    )

                    text = response.text

                    # bersihkan markdown json
                    text = re.sub(r"```json", "", text)
                    text = re.sub(r"```", "", text)

                    data = json.loads(text)

                    logging.info("SUCCESS rewrite")

                    return data

                except Exception as e:

                    logging.error(
                        f"Gemini error ({model}): {e}"
                    )

                    time.sleep(10)

        except Exception as e:

            logging.error(f"API Key error: {e}")

    return None


# =========================================
# DOWNLOAD IMAGE
# =========================================

def download_image(url):

    if not url:
        return None

    try:

        logging.info("Downloading featured image...")

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        if response.status_code != 200:
            return None

        filename = "featured.jpg"

        with open(filename, "wb") as f:
            f.write(response.content)

        return filename

    except Exception as e:

        logging.error(f"Image download error: {e}")

        return None


# =========================================
# UPLOAD IMAGE TO WORDPRESS
# =========================================

def upload_image_to_wp(image_path):

    if not image_path:
        return None

    try:

        logging.info("Uploading image to WordPress...")

        headers = {
            "Content-Disposition": (
                f'attachment; filename={os.path.basename(image_path)}'
            )
        }

        with open(image_path, "rb") as img:

            response = requests.post(
                WORDPRESS_MEDIA_URL,
                headers=headers,
                data=img,
                auth=(WP_USERNAME, WP_APP_PASSWORD)
            )

        if response.status_code in [200, 201]:

            media_id = response.json()["id"]

            logging.info(f"SUCCESS upload image ID={media_id}")

            return media_id

        logging.error(response.text)

        return None

    except Exception as e:

        logging.error(f"Upload image error: {e}")

        return None


# =========================================
# CREATE TAGS
# =========================================

def create_tags(tags):

    tag_ids = []

    for tag in tags:

        try:

            response = requests.post(
                f"{WORDPRESS_URL.replace('/posts', '/tags')}",
                auth=(WP_USERNAME, WP_APP_PASSWORD),
                json={"name": tag}
            )

            if response.status_code in [200, 201]:

                tag_ids.append(response.json()["id"])

            elif response.status_code == 400:

                # tag sudah ada
                search = requests.get(
                    f"{WORDPRESS_URL.replace('/posts', '/tags')}",
                    params={"search": tag},
                    auth=(WP_USERNAME, WP_APP_PASSWORD)
                )

                results = search.json()

                if results:
                    tag_ids.append(results[0]["id"])

        except Exception as e:

            logging.error(f"Tag error: {e}")

    return tag_ids


# =========================================
# POST TO WORDPRESS
# =========================================

def post_to_wordpress(article_data, featured_media):

    try:

        logging.info("Posting article to WordPress...")

        slug = slugify(article_data["title"])

        tag_ids = create_tags(
            article_data.get("tags", [])
        )

        seo_content = f"""
<!-- SEO META -->
<meta name="description" content="{article_data.get('meta_description', '')}" />
<meta name="keywords" content="{', '.join(article_data.get('lsi_keywords', []))}" />

{article_data["content"]}
"""

        payload = {
            "title": article_data["title"],
            "slug": slug,
            "content": seo_content,
            "excerpt": article_data.get("excerpt", ""),
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

            logging.info("SUCCESS POST TO WORDPRESS")

            return True

        logging.error(response.text)

        return False

    except Exception as e:

        logging.error(f"Post WP error: {e}")

        return False


# =========================================
# MAIN
# =========================================

def main():

    entries = get_feed()

    posted = load_posted()

    for item in entries:

        try:

            url = item.link

            if url in posted:

                logging.info(f"SKIP already posted: {url}")

                continue

            logging.info(f"Processing: {url}")

            # =====================================
            # SCRAPE
            # =====================================

            data = scrape_article(url)

            if not data:
                continue

            if len(data["text"]) < 300:

                logging.error("Article content too short")

                continue

            # =====================================
            # REWRITE
            # =====================================

            rewritten = rewrite_article(
                data["title"],
                data["text"]
            )

            if not rewritten:

                logging.error("Rewrite failed")

                continue

            # =====================================
            # IMAGE
            # =====================================

            image_path = download_image(
                data.get("image")
            )

            media_id = upload_image_to_wp(
                image_path
            )

            # =====================================
            # POST
            # =====================================

            success = post_to_wordpress(
                rewritten,
                media_id
            )

            if success:

                save_posted(url)

                logging.info("SUCCESS FULL PROCESS")

            else:

                logging.error("FAILED POST")

            logging.info(
                f"Sleeping {DELAY_BETWEEN_POSTS} sec..."
            )

            time.sleep(DELAY_BETWEEN_POSTS)

        except Exception as e:

            logging.error(f"MAIN LOOP ERROR: {e}")

            time.sleep(10)


# =========================================
# START
# =========================================

if __name__ == "__main__":

    main()
