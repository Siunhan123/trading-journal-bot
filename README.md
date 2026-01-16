# Trading Journal Telegram Bot

Bot nhật ký trading với Google Sheets, tự động báo cáo risk 2 lần/ngày.

## Setup

1. Lấy Token từ @BotFather
2. Lấy User ID từ @userinfobot
3. Tạo Google Sheet API credentials
4. Deploy lên Fly.io

## Lệnh deploy

```bash
fly apps create trading-journal-bot
fly secrets set BOT_TOKEN="your_token"
fly secrets set ADMIN_USER_ID="your_id"
fly secrets set SHEET_ID="your_sheet_id"
fly secrets set CREDENTIALS_JSON="$(cat credentials.json | base64)"
fly deploy
