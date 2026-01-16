import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import base64
import os
from config import SHEET_ID, SHEET_NAME
from datetime import datetime

class SheetsHandler:
    def __init__(self):
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # ALWAYS load from ENV VAR (Railway/Koyeb/Fly)
        creds_json = os.getenv('CREDENTIALS_JSON')
        if not creds_json:
            raise ValueError("❌ CREDENTIALS_JSON environment variable KHÔNG TỒN TẠI!")
        
        try:
            # Try direct JSON first (Railway thường dùng cách này)
            creds_dict = json.loads(creds_json)
            print("✅ Credentials loaded from JSON ENV")
        except json.JSONDecodeError:
            try:
                # Try base64 decode
                creds_dict = json.loads(base64.b64decode(creds_json).decode('utf-8'))
                print("✅ Credentials loaded from base64 ENV")
            except:
                raise ValueError("❌ CREDENTIALS_JSON format sai! Phải là JSON hợp lệ.")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        print(f"✅ Connected to Google Sheet: {SHEET_NAME}")
        self._setup_headers()
    
    def _setup_headers(self):
        headers = [
            'ID', 'Timestamp', 'Thị trường', 'Kiểu', 'Hướng', 'Ticker', 
            'Entry', 'SL', 'Risk%', 'Chart', 'Lý do', 'TP', 
            'Trạng thái', 'PnL_R', 'Ghi chú'
        ]
        try:
            existing = self.sheet.row
