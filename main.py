# main.py
import os
import logging
import asyncio
from dotenv import load_dotenv

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp as ytdl
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.exceptions import GroupCallNotFoundError

# load .env
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "MyMusicBot")
START_IMAGE_URL = os.getenv("START_IMAGE_URL", "")
SESSION_NAME = os.getenv("SESSION_NAME", "yt_session")

if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("Set API_ID, API_HASH and BOT_TOKEN in environment variables or .env")

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# clients
app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pytgcalls = PyTgCalls(app)

# in-memory queue: {chat_id: [ {title, url, requested_by} ]}
QUEUES = {}

# yt-dlp options
YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "default_search": "auto",
    # use yt-dlp to output direct URL (-g behaviour)
    "skip_download": True,
}

def extract_stream(query: str):
    """
    Uses yt-dlp to get a direct playable stream URL and title.
    Returns (stream_url, title) or (None, None) on failure.
    """
    opts = YTDL_OPTS.copy()
    with ytdl.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            # if playlist/search returned entries
            if isinstance(info, dict) and info.get("entries"):
                info = info["entries"][0]
            # Try to obtain a direct URL field
            stream_url = info.get("url") or info.get("webpage_url") or info.get("formats", [{}])[-1].get("url")
            title = info.get("title", "Unknown Title")
            return stream_url, title
        except Exception as e:
            logger.exception("yt-dlp error: %s", e)
            return None, None

# keyboards
def start_keyboard():
    add_url = f"https://t.me/{BOT_USERNAME}?startgroup=true"
    buttons = [
        [InlineKeyboardButton("➕ Add Me To Your Group", url=add_url)],
        [InlineKeyboardButton("📜 Open Command Menu ⚡", callback_data="open_cmd_menu")]
    ]
    return InlineKeyboardMarkup(buttons)

def menu_keyboard():
    buttons = [
        [InlineKeyboardButton("▶️ Play (/play)", callback_data="cmd_play")],
        [InlineKeyboardButton("⏸ Pause", callback_data="cmd_pause"), InlineKeyboardButton("▶️ Resume", callback_data="cmd_resume")],
        [InlineKeyboardButton("⏹ Stop", callback_data="cmd_stop"), InlineKeyboardButton("⏏ Leave", callback_data="cmd_leave")],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")]
    ]
    return InlineKeyboardMarkup(buttons)

# handlers
@app.on_message(filters.command("start") & ~filters.private)
async def start_msg(client, message):
    caption = (
        "🎵 <b>Thanks for getting me started!</b>\n\n"
        "I am a <b>high-quality</b>, ⚡ <b>simple</b> and 🚀 <b>fast</b> music bot.\n\n"
        "To enjoy the 🎧 <b>highest quality audio/video</b>, click the ➕ button below and add me to your group now.\n\n"
        "You can 📚 <b>learn about all my commands</b> by clicking on the 📜 command menu button below."
    )
    try:
        if START_IMAGE_URL:
            await client.send_photo(message.chat.id, photo=START_IMAGE_URL, caption=caption, reply_markup=start_keyboard())
        else:
            await client.send_message(message.chat.id, caption, reply_markup=start_keyboard())
    except Exception as e:
        logger.exception(e)
        await client.send_message(message.chat.id, caption, reply_markup=start_keyboard())

@app.on_message(filters.private & filters.command("start"))
async def start_private(client, message):
    await start_msg(client, message)

@app.on_message(filters.command("help"))
async def help_cmd(client, message):
    text = (
        "<b>Help Menu</b>\n\n"
        "/play <url or search> - Play a track in group voice chat\n"
        "/pause - Pause playback\n"
        "/resume - Resume playback\n"
        "/stop - Stop and clear queue\n"
        "/leave - Leave the voice chat\n"
        "/ping - Check bot status\n\n"
        "Note: Bot must be added to the group and be an admin to join voice chat."
    )
    await message.reply_text(text)

@app.on_message(filters.command("ping"))
async def ping_cmd(client, message):
    await message.reply_text("🏓 Pong! I'm alive.")

@app.on_message(filters.command("play") & ~filters.private)
async def play_cmd(client, message):
    chat_id = message.chat.id
    user = message.from_user.first_name
    if len(message.command) < 2:
        await message.reply_text("Use: /play <YouTube URL or search term>")
        return
    query = " ".join(message.command[1:])
    status_msg = await message.reply_text(f"🔎 Searching for: <b>{query}</b>")
    stream_url, title = await asyncio.get_event_loop().run_in_executor(None, extract_stream, query)
    if not stream_url:
        await status_msg.edit("❌ Couldn't find or extract audio for that query.")
        return

    QU = QUEUES.setdefault(chat_id, [])
    QU.append({"title": title, "stream": stream_url, "requested_by": user})
    await status_msg.edit(f"✅ Queued: <b>{title}</b>\nPosition: {len(QU)}")

    # if only one item -> start playing
    if len(QU) == 1:
        await play_next(chat_id, client)

async def play_next(chat_id: int, client: Client):
    q = QUEUES.get(chat_id)
    if not q:
        return
    item = q[0]
    try:
        await pytgcalls.join_group_call(
            chat_id,
            AudioPiped(item["stream"]),
        )
        await client.send_message(chat_id, f"▶️ Now playing: <b>{item['title']}</b>")
    except GroupCallNotFoundError:
        # voice chat not started or bot lacks permission
        await client.send_message(chat_id, "❌ Can't join voice chat. Make sure group voice chat is active and bot is admin.")
    except Exception as e:
        logger.exception(e)
        # remove current and try next
        q.pop(0)
        if q:
            await play_next(chat_id, client)

@app.on_message(filters.command("pause") & ~filters.private)
async def pause_cmd(client, message):
    try:
        await pytgcalls.pause_stream(message.chat.id)
        await message.reply_text("⏸ Paused.")
    except Exception as e:
        await message.reply_text(f"⚠️ {e}")

@app.on_message(filters.command("resume") & ~filters.private)
async def resume_cmd(client, message):
    try:
        await pytgcalls.resume_stream(message.chat.id)
        await message.reply_text("▶️ Resumed.")
    except Exception as e:
        await message.reply_text(f"⚠️ {e}")

@app.on_message(filters.command("stop") & ~filters.private)
async def stop_cmd(client, message):
    try:
        await pytgcalls.stop_stream(message.chat.id)
        QUEUES.pop(message.chat.id, None)
        await message.reply_text("⏹ Stopped and cleared queue.")
    except Exception as e:
        await message.reply_text(f"⚠️ {e}")

@app.on_message(filters.command("leave") & ~filters.private)
async def leave_cmd(client, message):
    try:
        await pytgcalls.leave_group_call(message.chat.id)
        QUEUES.pop(message.chat.id, None)
        await message.reply_text("👋 Left the voice chat.")
    except Exception as e:
        await message.reply_text(f"⚠️ {e}")

# callback query handler for inline menu
@app.on_callback_query()
async def cb_handler(client, cq):
    data = cq.data or ""
    if data == "open_cmd_menu":
        try:
            await cq.message.edit_reply_markup(menu_keyboard())
            await cq.answer()
        except Exception:
            await client.send_message(cq.message.chat.id, "Menu:", reply_markup=menu_keyboard())
            await cq.answer()
    elif data == "close_menu":
        try:
            await cq.message.edit_reply_markup(None)
            await cq.answer("Closed.")
        except Exception:
            await cq.answer("Can't close.")
    elif data.startswith("cmd_"):
        await cq.answer("Use the text commands in the chat (e.g., /play)")
    else:
        await cq.answer()

# pytgcalls handler: when stream ends -> pop and play next
from pytgcalls import idle
from pytgcalls.types import StreamAudioEnded

@pytgcalls.on_stream_end()
async def _on_stream_end(_, update: StreamAudioEnded):
    chat_id = update.chat_id
    logger.info("Stream ended for chat %s", chat_id)
    q = QUEUES.get(chat_id, [])
    if q:
        # remove finished
        q.pop(0)
        if q:
            # play next
            next_item = q[0]
            try:
                await pytgcalls.join_group_call(chat_id, AudioPiped(next_item["stream"]))
                await app.send_message(chat_id, f"▶️ Now playing: <b>{next_item['title']}</b>")
            except Exception as e:
                logger.exception(e)
                await app.send_message(chat_id, f"⚠️ Failed to play next: {e}")
        else:
            # leave after short time
            try:
                await pytgcalls.leave_group_call(chat_id)
                await app.send_message(chat_id, "Queue finished. Left voice chat.")
            except Exception:
                pass

# start
async def run():
    await app.start()
    await pytgcalls.start()
    logger.info("Bot started.")
    await idle()
    await pytgcalls.stop()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(run())