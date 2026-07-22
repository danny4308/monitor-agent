"""
monitor.py — Telegram Channel Monitor Agent
Checks only the LAST post from each channel.
Run manually when needed.
"""

import os
import json
import re
import requests
import anthropic
from datetime import datetime, timezone, timedelta
from pathlib import Path


ADMIN_ID = "5610144341"
HOURS_LOOKBACK = 12

TARGET_CHANNELS = [
    # Топ AI каналы
    "@hiaimedia",
    "@ai4telegram",
    "@neuraldvig",
    "@gpt_news",
    "@ai_machinelearning_big_data",
    "@ai_newz",
    "@data_secrets",
    "@JarvisNew",
    "@seeallochnaya",
    "@dailyprompts",
    "@studgpt",
    "@neuro_praxis",
    "@molyanov_blog",
    "@lama_channel_gpt",
    "@AI_Chad",
    "@notboring_tech",
    "@TochkiNadAI",
    "@ppprompt",
    "@prompt1_ru",
    "@olya_tashit",
    "@svodkaai_ai",
    "@LLMScience",
    "@Futuris",
    "@RixAiHub",

    # Инвестиции и финансы
    "@caprofit",
    "@smartlab",
    "@finside",
    "@TheEdinorog",

    # Крипта
    "@bit_novosti",
    "@criptovest",

    # Бизнес и стартапы
    "@razvedka_vc",
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


def get_last_post(channel: str) -> dict | None:
    """Fetch only the LAST post from public Telegram channel."""
    try:
        username = channel.lstrip("@")
        resp = requests.get(
            f"https://t.me/s/{username}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
        )

        if not resp.ok:
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_LOOKBACK)

        # Split into message blocks
        message_blocks = re.split(r'<div class="tgme_widget_message_wrap', resp.text)

        # Go through blocks from the end to find the last valid post
        for block in reversed(message_blocks[1:]):
            # Extract post ID
            id_match = re.search(r'data-post="([^"]+)"', block)
            if not id_match:
                continue
            post_id = id_match.group(1)
            msg_id = post_id.split("/")[-1] if "/" in post_id else post_id

            # Extract datetime
            time_match = re.search(r'datetime="([^"]+)"', block)
            if not time_match:
                continue

            try:
                post_dt = datetime.fromisoformat(time_match.group(1))
                if post_dt.tzinfo is None:
                    post_dt = post_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            # Skip if too old
            if post_dt < cutoff:
                return None

            # Extract text
            text_match = re.search(
                r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
                block,
                re.DOTALL
            )
            if not text_match:
                continue

            clean_text = re.sub(r'<[^>]+>', ' ', text_match.group(1)).strip()
            clean_text = clean_text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&#39;', "'").replace('&nbsp;', ' ')
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            if len(clean_text) < 30:
                continue

            return {
                "id": f"{channel}_{msg_id}",
                "text": clean_text[:800],
                "link": f"https://t.me/{username}/{msg_id}",
                "channel": channel,
                "date": post_dt.strftime("%d.%m %H:%M"),
            }

        return None

    except Exception as e:
        print(f"  Error fetching {channel}: {e}")
        return None


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
    message = f"""🔔 {post['channel']} | {post['date']}

📝 {post['text'][:250]}{'...' if len(post['text']) > 250 else ''}

💬 Идеи для комментария:
{comment_idea}

🔗 {post['link']}"""

    resp = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": ADMIN_ID, "text": message[:4096]},
        timeout=15,
    )
    if resp.ok:
        print(f"  ✓ Notification sent")
    else:
        print(f"  ✗ Error: {resp.text[:100]}")


def main():
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    seen_posts = load_seen_posts()
    new_seen = set()
    notifications_sent = 0

    cutoff_str = (datetime.now(timezone.utc) - timedelta(hours=HOURS_LOOKBACK)).strftime("%d.%m %H:%M")
    print(f"Monitoring {len(TARGET_CHANNELS)} channels (last {HOURS_LOOKBACK}h, since {cutoff_str} UTC)...")

    for channel in TARGET_CHANNELS:
        print(f"Checking {channel}...")
        post = get_last_post(channel)

        if not post:
            print(f"  No recent post")
            continue

        post_id = post["id"]
        new_seen.add(post_id)

        if post_id in seen_posts:
            print(f"  Already seen")
            continue

        if not is_relevant(post["text"]):
            print(f"  Not relevant")
            continue

        print(f"  Relevant! Generating comment idea...")
        try:
            comment_idea = generate_comment_idea(post)
            send_notification(bot_token, post, comment_idea)
            notifications_sent += 1
        except Exception as e:
            print(f"  Error: {e}")

    save_seen_posts(seen_posts | new_seen)
    print(f"\nDone! Notifications sent: {notifications_sent}")


if __name__ == "__main__":
    main()
