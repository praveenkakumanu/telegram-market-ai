# Telegram Market AI - Fixed Latest

## Fixes
- Personal Telegram account is separate from reporting bot.
- Automatic group/channel discovery when `TELEGRAM_CHATS=` is empty.
- Old messages are processed before live monitoring.
- Phone number is normalized to international format.
- Clear error for invalid phone number.
- Clear error if API ID/API hash is invalid.
- Detects if the user session is accidentally a bot session.
- Supports optional `TELEGRAM_PHONE_NUMBER`.

## Install on Windows

```powershell
cd telegram-market-ai-fixed
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, then preserve your existing credentials.

Keep:
```env
TELEGRAM_CHATS=
```

This automatically discovers groups/channels accessible to your personal account.

## IMPORTANT: old bad session

If the previous version authenticated `telegram_market_user.session` as a bot:

```powershell
Remove-Item .\telegram_market_user.session -Force -ErrorAction SilentlyContinue
```

Then:

```powershell
python app.py
```

When asked for the phone number, use your PERSONAL Telegram phone number:

```text
+919876543210
```

Do NOT enter:
- Telegram bot token
- Telegram API ID
- Telegram API hash

The login code will be requested next. If 2FA is enabled, the app asks for the Telegram 2FA password.

## Phone number

Use international format:
- India: `+919876543210`
- US example: `+14155552671`

The code also accepts spaces/dashes and normalizes them.

If Telegram still says the number is invalid, verify that the number is actually the phone number attached to the Telegram account and that the API ID/API hash belong to the application from my.telegram.org.

## Security

Do not commit `.env` or `.session` files.
If a bot token has been exposed, revoke/regenerate it with BotFather and use the new token.

\n## v2 connection fix\n\nThis version explicitly connects the Telethon personal-account client before checking `is_user_authorized()`. This fixes `ConnectionError: Cannot send requests while disconnected`.\n