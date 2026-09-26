import asyncio
import getpass
import json
import logging
import os
import re
from datetime import datetime, timezone

from telethon import TelegramClient, events
from telethon.errors import PhoneNumberInvalidError, ApiIdInvalidError

from config import (
    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN,
    REPORT_CHAT_ID, TELEGRAM_CHATS, BACKFILL_MESSAGES,
    MEDIA_DIR, TELEGRAM_PHONE_NUMBER
)
from database import init_db, message_exists, save_message, stats
from ai import analyze_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger=logging.getLogger("telegram-market-ai")
os.makedirs(MEDIA_DIR, exist_ok=True)

user_client=TelegramClient(
    "telegram_market_user",
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH
)
bot_client=TelegramClient(
    "telegram_market_bot",
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH
)

def normalize_phone(value: str) -> str:
    """
    Telegram expects international/E.164-style input.
    Accepts:
      +91 98765 43210
      +91-9876543210
      +919876543210
    Also accepts 919876543210 and adds '+'.
    """
    value=(value or "").strip()
    value=re.sub(r"[()\s\-.]", "", value)

    if value.startswith("00"):
        value="+" + value[2:]
    elif not value.startswith("+"):
        value="+" + value

    if not re.fullmatch(r"\+[1-9]\d{7,14}", value):
        raise ValueError(
            "Invalid phone format. Use international format, "
            "for example +919876543210."
        )
    return value

def allowed_entity(entity):
    if not TELEGRAM_CHATS:
        return True
    username=(getattr(entity,"username",None) or "").lower().replace("@","")
    title=(getattr(entity,"title",None) or "").strip().lower()
    return username in TELEGRAM_CHATS or title in TELEGRAM_CHATS

async def sender_name_from_message(message):
    try:
        sender=await message.get_sender()
        if not sender:
            return "Unknown"
        first=getattr(sender,"first_name",None) or ""
        last=getattr(sender,"last_name",None) or ""
        username=getattr(sender,"username",None) or ""
        full=f"{first} {last}".strip()
        return full or (f"@{username}" if username else "Unknown")
    except Exception:
        return "Unknown"

def format_report(analysis, chat_name, sender_name, historical=False):
    lines=[
        "📚 HISTORICAL MARKET INTELLIGENCE" if historical else "🚨 MARKET INTELLIGENCE",
        "",
        f"📌 {analysis.get('title','Market Intelligence')}",
        "",
        f"Category: {analysis.get('category','other')}",
        f"Importance: {analysis.get('importance','low')}",
        f"Sentiment: {analysis.get('sentiment','unknown')}",
        f"Confidence: {analysis.get('confidence',0)}",
        "",
        "📝 Summary",
        analysis.get("summary","")
    ]
    entities=analysis.get("entities",[])
    if entities:
        lines += ["","🏷 Entities",", ".join(map(str,entities))]
    impact=analysis.get("market_impact","")
    if impact:
        lines += ["","📊 Potential Market Impact",impact]
    trade=analysis.get("trade_information") or {}
    if isinstance(trade,dict):
        fields=[
            ("Instrument",trade.get("instrument","")),
            ("Direction",trade.get("direction","")),
            ("Entry",trade.get("entry","")),
            ("Target",trade.get("target","")),
            ("Stop Loss",trade.get("stop_loss",""))
        ]
        if any(v for _,v in fields):
            lines += ["","📈 Trading Information"]
            lines += [f"{k}: {v}" for k,v in fields if v]
    lines += [
        "","📡 Source",f"Chat: {chat_name}",f"Sender: {sender_name}",
        "","⚠️ AI-generated interpretation. Verify information before making financial decisions."
    ]
    return "\n".join(lines)

async def send_report(report):
    if not REPORT_CHAT_ID:
        logger.info("REPORT_CHAT_ID=0; report sending disabled.")
        return
    for i in range(0,len(report),3500):
        await bot_client.send_message(REPORT_CHAT_ID,report[i:i+3500])

async def analyze_and_store(message,chat,historical=False):
    chat_id=getattr(chat,"id",None)
    if chat_id is None or message_exists(chat_id,message.id):
        return

    chat_name=getattr(chat,"title",None) or getattr(chat,"username",None) or str(chat_id)
    sender_name=await sender_name_from_message(message)
    text=message.message or ""
    media_path=None

    if message.photo:
        try:
            media_path=os.path.join(MEDIA_DIR,f"{chat_id}_{message.id}.jpg")
            await message.download_media(file=media_path)
        except Exception as exc:
            logger.exception("Media download failed: %s",exc)
            media_path=None

    if not text.strip() and not media_path:
        return

    logger.info(
        "Analyzing %s message %s from %s",
        "historical" if historical else "live",message.id,chat_name
    )

    try:
        analysis=await asyncio.to_thread(analyze_message,text,media_path)
    except Exception as exc:
        logger.exception("AI analysis failed: %s",exc)
        return

    created_at=message.date.isoformat() if message.date else datetime.now(timezone.utc).isoformat()

    save_message(
        message.id,chat_id,chat_name,sender_name,text,media_path,
        analysis.get("category","other"),
        analysis.get("importance","low"),
        analysis.get("title",""),
        analysis.get("summary",""),
        analysis.get("sentiment","unknown"),
        analysis.get("market_impact",""),
        json.dumps(analysis,ensure_ascii=False),
        created_at
    )

    if analysis.get("important",False):
        await send_report(format_report(analysis,chat_name,sender_name,historical))
    else:
        logger.info("Ignored irrelevant message %s from %s",message.id,chat_name)

async def process_old_messages(limit):
    logger.info("Automatically discovering Telegram groups/channels...")
    dialogs=await user_client.get_dialogs()
    discovered=0
    processed=0

    for dialog in dialogs:
        if dialog.is_user:
            continue
        if not (dialog.is_group or dialog.is_channel):
            continue

        entity=dialog.entity
        if not allowed_entity(entity):
            continue

        discovered+=1
        chat_name=dialog.name or getattr(entity,"username",None) or str(dialog.id)
        logger.info("Backfill: %s",chat_name)

        try:
            messages=[]
            async for message in user_client.iter_messages(entity,limit=limit):
                messages.append(message)
            messages.reverse()

            for message in messages:
                await analyze_and_store(message,entity,historical=True)
            processed+=1
        except Exception as exc:
            logger.exception("Failed processing %s: %s",chat_name,exc)

    logger.info("Historical processing finished. Discovered=%s Processed=%s",discovered,processed)

@user_client.on(events.NewMessage(incoming=True))
async def new_message(event):
    try:
        if not (event.is_group or event.is_channel):
            return
        chat=await event.get_chat()
        if not allowed_entity(chat):
            return
        asyncio.create_task(analyze_and_store(event.message,chat,False))
    except Exception as exc:
        logger.exception("Live message handler failed: %s",exc)

def authorized_report_user(event):
    return REPORT_CHAT_ID==0 or event.sender_id==REPORT_CHAT_ID

@bot_client.on(events.NewMessage(pattern=r"^/start$"))
async def start_command(event):
    if not authorized_report_user(event):
        return
    await event.respond(
        "🤖 Telegram Market Intelligence Bot\n\n"
        "/status\n/backfill\n/backfill 50\n\n"
        "TELEGRAM_CHATS empty = automatic group/channel discovery."
    )

@bot_client.on(events.NewMessage(pattern=r"^/status$"))
async def status_command(event):
    if not authorized_report_user(event):
        return
    total,important=stats()
    await event.respond(
        f"📊 Status\n\nMessages analyzed: {total}\n"
        f"Important: {important}\n"
        f"Automatic discovery: {'ON' if not TELEGRAM_CHATS else 'OFF'}"
    )

@bot_client.on(events.NewMessage(pattern=r"^/backfill(?:\s+(\d+))?$"))
async def backfill_command(event):
    if not authorized_report_user(event):
        return
    requested=event.pattern_match.group(1)
    limit=min(max(int(requested) if requested else BACKFILL_MESSAGES,1),200)
    await event.respond(f"📚 Starting backfill: {limit} messages per group/channel.")
    asyncio.create_task(process_old_messages(limit))

async def start_personal_user():
    if getattr(user_client,"session",None) is None:
        pass

    # Connect first. Telethon cannot answer is_user_authorized()
    # while the MTProto connection is disconnected.
    await user_client.connect()

    # Existing valid session: Telethon will reuse it without prompting.
    if await user_client.is_user_authorized():
        me=await user_client.get_me()
        if getattr(me,"bot",False):
            raise RuntimeError(
                "telegram_market_user.session belongs to a BOT. "
                "Delete that session file and restart."
            )
        return me

    phone=TELEGRAM_PHONE_NUMBER
    while True:
        if not phone:
            raw=input(
                "\nEnter your PERSONAL Telegram phone number "
                "in international format (example +919876543210): "
            )
        else:
            raw=phone

        try:
            phone=normalize_phone(raw)
            break
        except ValueError as exc:
            print(f"\n❌ {exc}")
            phone=""

    try:
        # Explicit callbacks avoid Telethon receiving an unexpected value.
        await user_client.start(
            phone=phone,
            code_callback=lambda: input("Enter the Telegram login code: ").strip(),
            password=lambda: getpass.getpass("Enter your Telegram 2FA password: ")
        )
    except PhoneNumberInvalidError:
        raise RuntimeError(
            f"Telegram rejected {phone} as invalid. "
            "Verify that it is your real Telegram number in international format "
            "(example +919876543210), with the correct country code. "
            "Do not enter your bot token, API ID, or API hash."
        )
    except ApiIdInvalidError:
        raise RuntimeError(
            "Telegram rejected TELEGRAM_API_ID/API_HASH. "
            "Use the API ID and API hash from my.telegram.org for your Telegram account."
        )

    me=await user_client.get_me()
    if getattr(me,"bot",False):
        raise RuntimeError(
            "The authenticated session is a BOT. Delete telegram_market_user.session "
            "and sign in with your personal Telegram phone number."
        )
    return me

async def main():
    init_db()

    logger.info("Starting PERSONAL Telegram user account...")
    me=await start_personal_user()
    logger.info("Personal Telegram connected: id=%s username=%s",me.id,me.username)

    logger.info("Starting separate Telegram report bot...")
    await bot_client.start(bot_token=TELEGRAM_BOT_TOKEN)
    logger.info("Report bot started.")

    logger.info("Processing historical messages first...")
    await process_old_messages(BACKFILL_MESSAGES)

    logger.info("Historical processing complete. Monitoring live group/channel messages...")
    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected()
    )

if __name__=="__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped.")
