# Trading Journal Telegram Bot

Bot nhật ký trading với Google Sheets, tự động báo cáo risk 2 lần/ngày.

## Setup

1. Lấy Token từ @BotFather
2. Lấy User ID từ @userinfobot
3. Tạo Google Sheet API credentials
4. Deploy lên Fly.io

## Lệnh deploy

bash
fly apps create trading-journal-bot
fly secrets set BOT_TOKEN="your_token"
fly secrets set ADMIN_USER_ID="your_id"
fly secrets set SHEET_ID="your_sheet_id"
fly secrets set CREDENTIALS_JSON="$(cat credentials.json | base64)"
fly deploy


***

## Bước 3: Lấy thông tin cần thiết

### 3.1 Lấy BOT_TOKEN
1. Telegram → tìm `@BotFather`
2. Gửi `/newbot`
3. Đặt tên và username
4. Copy TOKEN

### 3.2 Lấy ADMIN_USER_ID
1. Telegram → tìm `@userinfobot`
2. Gửi `/start`
3. Copy số ID (VD: 123456789)

### 3.3 Google Sheet Credentials (đã hướng dẫn ở trên)
- File `credentials.json` đã download

***

## Bước 4: Deploy lên Fly.io (KHÔNG CẦN Python)

### 4.1 Cài Fly CLI

**Windows:**
```powershell
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
