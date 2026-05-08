import feedparser
import time

feed = feedparser.parse("https://dpntimes.com/feed")

for entry in feed.entries[:5]:
    print(entry.title)
    print(entry.link)
    print("-" * 50)

time.sleep(5)