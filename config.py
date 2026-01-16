import os

# Telegram Bot Token
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Your Telegram User ID (thay số này bằng ID của bạn)
# Lấy ID từ @userinfobot trên Telegram
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '123456789'))

# Google Sheet ID
SHEET_ID = os.getenv('SHEET_ID')
SHEET_NAME = 'Trades'

# Timezone
TIMEZONE = 'Asia/Tokyo'

# Report times
REPORT_HOURS = [12, 20]  # 12:30 và 20:30
REPORT_MINUTE = 30
