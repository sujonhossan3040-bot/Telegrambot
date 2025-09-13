# 🎵 Telegram Music Bot

একটি টেলিগ্রাম মিউজিক বট, যা **YouTube থেকে গান বাজাতে পারে** এবং গ্রুপ ভয়েস চ্যাটে লাইভ মিউজিক চালায়।  
(ঠিক Yukki Tune Bot-এর মতো কাজ করবে)

---

## 🚀 কিভাবে সেটআপ করবেন

### 1. Requirements
- Python 3.10+
- FFmpeg
- Telegram API_ID & API_HASH (my.telegram.org থেকে)
- Bot Token (BotFather থেকে)

### 2. `.env` ফাইল কনফিগার করুন
একই ফোল্ডারে `.env` নামে ফাইল তৈরি করে এরকম লিখুন:

```env
BOT_TOKEN=আপনার_টেলিগ্রাম_বট_টোকেন
API_ID=আপনার_api_id
API_HASH=আপনার_api_hash
BOT_USERNAME=আপনারবটusername
START_IMAGE_URL=https://i.imgur.com/6mKJQ6Z.png
SESSION_NAME=yt_session