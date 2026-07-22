"""
monitor.py — Telegram Channel Monitor Agent
Checks only the LAST post from each channel.
Generates human-like comments, not AI templates.
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
    # Топ AI каналы с активными комментариями
    "@hiaimedia",           # 2.5М — главный AI канал
    "@neuraldvig",          # 304К — культовый, активные комменты
    "@ai_machinelearning_big_data",  # 290К — ML
    "@ai_newz",             # 95К — авторская аналитика
    "@data_secrets",        # 91К — ML
    "@seeallochnaya",       # 76К — NLP, живое обсуждение
    "@dailyprompts",        # 41К — промпты
    "@neuro_praxis",        # 30К — нейросети
    "@molyanov_blog",       # 28К — ИИ и бизнес, много дискуссий
    "@AI_Chad",             # 21К — нейросети и маркетинг
    "@notboring_tech",      # 20К — технологии и стартапы
    "@TochkiNadAI",         # 15К — активные комменты
    "@ppprompt",            # 14К — AI и технологии
    "@olya_tashit",         # 13К — технологии
    "@svodkaai_ai",         # 10К — сводка AI
    "@LLMScience",          # 8К — LLM
    "@Futuris",             # 5К — AI инструменты
    "@neural_houses",       # нейросетевые покои
    "@aioftheday",          # AI of the day
    "@AI_UD",               # дайджест AI

    # Инвестиции и финансы (с комментами)
    "@caprofit",
    "@TheEdinorog",
    "@notboring_tech",

    # Крипта
    "@bit_novosti",
    "@criptovest",

    # Бизнес
    "@razvedka_vc",
    "@rusven",
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
        message_blocks = re.split(r'<div class="tgme_widget_message_wrap', resp.text)

        for block in reversed(message_blocks[1:]):
            id_match = re.search(r'data-post="([^"]+)"', block)
            if not id_match:
                continue
            post_id = id_match.group(1)
            msg_id = post_id.split("/")[-1] if "/" in post_id else post_id

            time_match = re.search(r'datetime="([^"]+)"', block)
            if not time_match:
                continue

            try:
                post_dt = datetime.fromisoformat(time_match.group(1))
                if post_dt.tzinfo is None:
                    post_dt = post_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if post_dt < cutoff:
                return None

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
        print(f"  Error: {e}")
        return None


def is_relevant(text: str) -> bool:
    keywords = [
        "ai", "ии", "искусственный интеллект", "нейросеть",
        "openai", "anthropic", "claude", "gpt", "llm",
        "nvidia", "apple", "microsoft", "google", "meta",
        "инвестиции", "крипта", "bitcoin", "ethereum",
        "стартап", "деньги", "рынок", "акции",
        "автоматизация", "технологии", "чипы",
        "заработок", "бизнес", "монетизация",
        "агент", "llama", "gemini",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def generate_comment_idea(post: dict) -> str:
    client = anthropic.Anthropic()

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Ты помогаешь написать живой комментарий в Telegram под пост.

Автор комментария ведёт канал {YOUR_CHANNEL} про AI и деньги — но это НЕ надо упоминать напрямую.

Пост из {post['channel']}:
{post['text']}

Напиши 3 варианта комментария. Каждый должен быть:
- Живым и человечным — как пишут умные люди в Telegram, не боты
- Разным по стилю: один короткий и острый, один с личным мнением, один с уточняющим вопросом
- Без шаблонных фраз типа "отличный пост", "согласен", "интересно"
- Иногда можно не соглашаться или добавить нюанс который упустили
- 1-2 предложения максимум
- На русском, без смайликов если не нужны

Примеры хорошего стиля:
- "тут ключевое что никто не замечает — [конкретное наблюдение]"
- "сам сталкивался с этим, но в реальности оказалось [опыт]"
- "а что с [конкретный аспект темы]? это же меняет картину"

Вариант 1 (короткий и острый):
Вариант 2 (личное мнение/опыт):
Вариант 3 (вопрос или нюанс):"""
        }]
    )

    return message.content[0].text


def send_notification(bot_token: str, post: dict, comment_idea: str):
    message = f"""🔔 {post['channel']} | {post['date']}

📝 {post['text'][:300]}{'...' if len(post['text']) > 300 else ''}

💬 Варианты комментария:
{comment_idea}

🔗 {post['link']}

💡 Выбери вариант → отредактируй под себя → опубликуй"""

    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": ADMIN_ID, "text": message[:4096]},
        timeout=15,
    )
    print(f"  ✓ Sent")


def main():
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    seen_posts = load_seen_posts()
    new_seen = set()
    notifications_sent = 0

    print(f"Checking {len(TARGET_CHANNELS)} channels (last {HOURS_LOOKBACK}h)...")

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

        print(f"  Relevant! Generating...")
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
