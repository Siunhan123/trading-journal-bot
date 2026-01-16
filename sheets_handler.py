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
        
        # Load credentials from ENV VAR (Railway/Koyeb)
        creds_json = os.getenv('CREDENTIALS_JSON')
        if not creds_json:
            raise ValueError("❌ CREDENTIALS_JSON environment variable not found!")
        
        try:
            # Try direct JSON first (Railway default)
            creds_dict = json.loads(creds_json)
            print("✅ Credentials loaded from JSON ENV")
        except json.JSONDecodeError:
            try:
                # Try base64 decode
                creds_dict = json.loads(base64.b64decode(creds_json).decode('utf-8'))
                print("✅ Credentials loaded from base64 ENV")
            except:
                raise ValueError("❌ CREDENTIALS_JSON format invalid!")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        print(f"✅ Connected to Google Sheet: {SHEET_NAME}")
        self._setup_headers()
    
    def _setup_headers(self):
        """Setup header row if not exists"""
        headers = [
            'ID', 'Timestamp', 'Thị trường', 'Kiểu', 'Hướng', 'Ticker', 
            'Entry', 'SL', 'Risk%', 'Chart', 'Lý do', 'TP', 
            'Trạng thái', 'PnL_R', 'Ghi chú'
        ]
        try:
            existing = self.sheet.row_values(1)
            if not existing or existing[0] != 'ID':
                self.sheet.insert_row(headers, 1)
        except:
            self.sheet.append_row(headers)
    
    def add_trade(self, trade_data):
        """Add new trade to sheet"""
        all_rows = self.sheet.get_all_values()
        next_id = len(all_rows)
        
        row = [
            next_id,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            trade_data['market'],
            trade_data['style'],
            trade_data['direction'],
            trade_data['ticker'],
            trade_data['entry'],
            trade_data['sl'],
            trade_data['risk'],  # GHI SỐ THUẦN, VÍ DỤ: 2.5
            trade_data.get('chart', ''),
            trade_data.get('reason', ''),
            '',  # TP
            'Pending',
            '',  # PnL_R
            ''   # Ghi chú
        ]
        self.sheet.append_row(row)
        return next_id
    
    def get_pending_trades(self):
        """Get all pending trades"""
        try:
            records = self.sheet.get_all_records()
            pending = []
            for r in records:
                if r.get('Trạng thái') == 'Pending':
                    # FIX: Convert Risk% to float
                    try:
                        r['Risk%'] = float(r.get('Risk%', 0) or 0)
                    except:
                        r['Risk%'] = 0.0
                    pending.append(r)
            return pending
        except Exception as e:
            print(f"❌ Error getting pending trades: {e}")
            return []
    
    def get_trade_by_id(self, trade_id):
        """Get trade details by ID"""
        all_values = self.sheet.get_all_values()
        headers = all_values[0]
        
        for row in all_values[1:]:
            if row[0] == str(trade_id):
                trade = {}
                for i, header in enumerate(headers):
                    trade[header] = row[i] if i < len(row) else ''
                return trade
        
        return None
    
    def update_trade_by_id(self, trade_id, updates):
        """Update trade by ID with dict of updates"""
        all_values = self.sheet.get_all_values()
        headers = all_values[0]
        
        # Find row by ID
        row_num = None
        for idx, row in enumerate(all_values[1:], start=2):
            if row[0] == str(trade_id):
                row_num = idx
                break
        
        if not row_num:
            return False
        
        # Update columns
        for col_name, value in updates.items():
            try:
                col_index = headers.index(col_name) + 1
                self.sheet.update_cell(row_num, col_index, value)
            except ValueError:
                continue
        
        return True
    
    def calculate_new_risk(self, entry, old_sl, new_sl, old_risk, direction):
        """Calculate new risk when SL is moved"""
        entry = float(entry)
        old_sl = float(old_sl)
        new_sl = float(new_sl)
        old_risk = float(old_risk)
        
        # Free risk if SL moved past entry
        if direction == 'BUY' and new_sl >= entry:
            return 0.0
        if direction == 'SELL' and new_sl <= entry:
            return 0.0
        
        # Calculate risk based on distance
        old_distance = abs(entry - old_sl)
        new_distance = abs(entry - new_sl)
        
        if old_distance == 0:
            return old_risk
        
        new_risk = old_risk * (new_distance / old_distance)
        return round(new_risk, 2)
    
    def get_stats(self, start_date=None, end_date=None):
        """Get trading statistics for a period"""
        records = self.sheet.get_all_records()
        
        # Filter by date range
        if start_date:
            records = [r for r in records if r.get('Timestamp', '') >= start_date]
        if end_date:
            records = [r for r in records if r.get('Timestamp', '') <= end_date]
        
        # Get closed trades only
        closed = [r for r in records if r.get('Trạng thái') in ['Closed', 'BE']]
        
        if not closed:
            return {
                'winrate': 0,
                'total_pnl': 0,
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'be': 0
            }
        
        # Calculate stats
        wins = [r for r in closed if float(r.get('PnL_R', 0) or 0) > 0]
        losses = [r for r in closed if float(r.get('PnL_R', 0) or 0) < 0]
        be_trades = [r for r in closed if r.get('Trạng thái') == 'BE']
        
        total_pnl = sum([float(r.get('PnL_R', 0) or 0) for r in closed])
        winrate = len(wins) / len(closed) * 100 if closed else 0
        
        return {
            'winrate': round(winrate, 1),
            'total_pnl': round(total_pnl, 2),
            'total_trades': len(closed),
            'wins': len(wins),
            'losses': len(losses),
            'be': len(be_trades)
        }
    
    def get_stats_by_category(self, category, start_date=None, end_date=None):
        """Get stats breakdown by category (Thị trường or Kiểu)"""
        records = self.sheet.get_all_records()
        
        # Filter by date
        if start_date:
            records = [r for r in records if r.get('Timestamp', '') >= start_date]
        if end_date:
            records = [r for r in records if r.get('Timestamp', '') <= end_date]
        
        closed = [r for r in records if r.get('Trạng thái') in ['Closed', 'BE']]
        
        # Group by category
        grouped = {}
        for trade in closed:
            key = trade.get(category, 'Unknown')
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(trade)
        
        # Calculate stats for each group
        result = {}
        for key, trades in grouped.items():
            wins = [t for t in trades if float(t.get('PnL_R', 0) or 0) > 0]
            total_pnl = sum([float(t.get('PnL_R', 0) or 0) for t in trades])
            winrate = len(wins) / len(trades) * 100 if trades else 0
            
            result[key] = {
                'winrate': round(winrate, 1),
                'pnl': round(total_pnl, 2),
                'trades': len(trades)
            }
        
        return result
    
    def get_open_risk(self):
        """Get total open risk and breakdown by market/style"""
        pending = self.get_pending_trades()
        total_risk = sum([float(r.get('Risk%', 0) or 0) for r in pending])
        
        # Calculate risk by market and style
        by_market = {}
        by_style = {}
        for trade in pending:
            market = trade.get('Thị trường', 'Unknown')
            style = trade.get('Kiểu', 'Unknown')
            risk = float(trade.get('Risk%', 0) or 0)
            
            by_market[market] = by_market.get(market, 0) + risk
            by_style[style] = by_style.get(style, 0) + risk
        
        return {
            'total': round(total_risk, 2),
            'count': len(pending),
            'market_count': {k: round(v, 2) for k, v in by_market.items()},
            'style_count': {k: round(v, 2) for k, v in by_style.items()},
            'trades': pending  # ← THÊM TRADES LIST
        }
