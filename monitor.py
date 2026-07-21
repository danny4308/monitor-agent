"""
monitor.py — Telegram Channel Monitor Agent
Watches target channels, detects relevant posts, generates comment ideas,
sends notifications to admin.
"""

import os
import json
import requests
import anthropic
from datetime import datetime
from pathlib import Path


ADMIN_ID = "5610144341"

TARGET_CHANNELS = [
    # AI и нейросети
    "@AIhappens",
    "@AI_UD",
    "@tproger",
    "@deeptechnet",
    "@aiaiai",
    "@vistehno",
    "@pro_neiroset",
    "@gptpublic",
    "@chatgpt_neiro_news",
    "@chat_ai_bot_news",
    "@pro_ai_novosti",
    "@ipumpbrain",
    "@chatgpt_try",
    "@gpt4turbo",
    "@chatgptv",

    # Инвестиции и финансы
    "@caprofit",
    "@smartlab",
    "@finside",
    "@inflationinsights",
    "@etffocus",
    "@vc_journal",
    "@unicornfactory",
    "@angels_investing",
    "@smart_beta",
    "@passiveincome",

    # Крипта
    "@bit_novosti",
    "@criptovest",
    "@Bitcoin_Ethereum_Altcoins",
    "@stablediffusionbest",
    "@cryptosekta",

    # Венчур и стартапы
    "@TheEdinorog",
    "@rusven",
    "@razvedka_vc",
    "@startandwin",

    # Бизнес и технологии
    "@wylsacom",
    "@rozetked",
    "@Denis_sexy_it",
    "@neyroset_vidit",
    "@mgerkom",
]

KEYWORDS = [
    "ai", "ии", "искусственный интеллект", "нейросеть",
    "openai", "anthropic", "claude", "gpt", "llm",
    "nvidia", "apple", "microsoft", "google", "meta",
    "инвестиции", "крипта", "bitcoin", "ethereum", "btc",
    "стартап", "venture", "деньги", "рынок", "акции",
    "автоматизация", "будущее", "технологии", "чипы",
    "заработок", "бизнес", "монетизация", "продукт",
    "агент", "llama", "gemini", "midjourney",
]

YOUR_CHANNEL = "@thepulseai"
YOUR_CHANNEL_TOPIC = "AI, технологии и деньги — ежедневный дайджест"

SEEN_POSTS_FILE = "seen_posts.json"


def load_seen_posts() -> set:
    if Path(SEEN_POSTS_FILE).exists():
        try:
            with open(SEEN_POSTS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_seen_posts(seen: set):
    seen_list = list(seen)[-2000:]
    with open(SEEN_POSTS_FILE, "w") as f:
        json.dump(seen_list, f)


def get_channel_posts(channel: str) -> list[dict]:
    """Fetch recent posts from public Telegram channel."""
    try:
        import re
        username = channel.lstrip("@")
        resp = requests.get(
            f"https://t.me/s/{username}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
        )

        if not resp.ok:
            return []

        posts = []
        text_pattern = re.findall(
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            resp.text,
            re.DOTALL
        )
        id_pattern = re.findall(r'data-post="([^"]+)"', resp.text)

        for text_html, post_id in zip(text_pattern[:15], id_pattern[:15]):
            clean_text = re.sub(r'<[^>]+>', ' ', text_html).strip()
            clean_text = clean_text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&#39;', "'").replace('&nbsp;', ' ')
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            if len(clean_text) < 30:
                continue

            msg_id = post_id.split("/")[-1] if "/" in post_id else post_id
            posts.append({
                "id": f"{channel}_{msg_id}",
                "text": clean_text[:800],
                "link": f"https://t.me/{username}/{msg_id}",
                "channel": channel,
            })

        return posts

    except Exception as e:
        print(f"  Error fetching {channel}: {e}")
        return []


def is_relevant(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS)


def generate_comment_idea(post: dict) -> str:
    client = anthropic.Anthropic()

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": f"""Помоги написать умный комментарий под этот пост от имени автора канала "{YOUR_CHANNEL}" ({YOUR_CHANNEL_TOPIC}).

Пост из {post['channel']}:
{post['text']}

Напиши 2 варианта умного комментария:
- Добавляет ценность, показывает экспертизу в AI/технологиях/деньгах
- НЕ рекламирует канал напрямую
- 1-3 предложения, живой язык
- На русском языке

Вариант 1: [комментарий]
Вариант 2: [комментарий]"""
        }]
    )

    return message.content[0].text


def send_notification(bot_token: str, post: dict, comment_idea: str):
    message = f"""🔔 {post['channel']}

📝 {post['text'][:250]}{'...' if len(post['text']) > 250 else ''}

💬 Идеи для комментария:
{comment_idea}

🔗 {post['link']}"""

    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": ADMIN_ID, "text": message[:4096]},
        timeout=15,
    )
    print(f"  ✓ Notification sent")


def main():
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    seen_posts = load_seen_posts()
    new_seen = set()
    notifications_sent = 0

    print(f"Monitoring {len(TARGET_CHANNELS)} channels...")
    print(f"Already seen: {len(seen_posts)} posts")

    for channel in TARGET_CHANNELS:
        print(f"Checking {channel}...")
        posts = get_channel_posts(channel)

        for post in posts:
            post_id = post["id"]
            new_seen.add(post_id)

            if post_id in seen_posts:
                continue

            if not is_relevant(post["text"]):
                continue

            print(f"  Relevant! Generating comment idea...")
            try:
                comment_idea = generate_comment_idea(post)
                send_notification(bot_token, post, comment_idea)
                notifications_sent += 1
            except Exception as e:
                print(f"  Error: {e}")

    save_seen_posts(seen_posts | new_seen)
    print(f"\nDone! Notifications: {notifications_sent}")


if __name__ == "__main__":
    main()
