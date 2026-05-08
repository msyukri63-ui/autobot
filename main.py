from openai import OpenAI
import feedparser

client = OpenAI()

feed = feedparser.parse("https://dpntimes.com/feed")

for entry in feed.entries[:1]:

    prompt = f"Rewrite berita ini:\n{entry.title}"

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    print(response.choices[0].message.content)
