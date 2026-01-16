import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import SHEET_ID, SHEET_NAME
from datetime import datetime
import json
import os
import base64

class SheetsHandler:
    def __init__(self):
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    
    # Load credentials from ENV VAR FIRST (Railway/Koyeb)
    creds_json = os.getenv('CREDENTIALS_JSON')
    if creds_json:
        try:
            # Try base64 first
            creds_dict = json.loads(base64.b64decode(creds_json).decode('utf-8'))
        except:
            try:
                # Try direct JSON
                creds_dict = json.loads(creds_json)
            except json.JSONDecodeError:
                raise ValueError("CREDENTIALS_JSON phải là JSON hợp lệ")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        print("✅ Loaded credentials from ENV var")
    else:
        # Fallback local file (dev only)
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        print("⚠️ Loaded from local credentials.json")
    
    client = gspread.authorize(creds)
    self.sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    self._setup_headers()
    
    def _setup_headers(self):
        headers = ['ID', 'Timestamp', 'Thị trường', 'Kiểu', 'Hướng', 'Ticker', 
                   'Entry', 'SL', 'Risk%', 'Chart', 'Lý do', 'TP', 
                   'Trạng thái', 'PnL_R', 'Ghi chú']
        try:
            existing = self.sheet.row_values(1)
            if not existing or existing[0] != 'ID':
                self.sheet.insert_row(headers, 1)
        except:
            self.sheet.append_row(headers)
    
    def add_trade(self, trade_data):
        all_rows = self.sheet.get_all_values()
        next_id = len(all_rows)  # ID tự động tăng
        
        row = [
            next_id,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            trade_data['market'],
            trade_data['style'],
            trade_data['direction'],
            trade_data['ticker'],
            trade_data['entry'],
            trade_data['sl'],
            trade_data['risk'],
            trade_data.get('chart', ''),
            trade_data.get('reason', ''),
            '',  # TP empty
            'Pending',
            '',  # PnL empty
            ''   # Note empty
        ]
        self.sheet.append_row(row)
        return next_id
    
    def get_pending_trades(self):
        records = self.sheet.get_all_records()
        return [r for r in records if r.get('Trạng thái') == 'Pending']
    
    def update_trade_by_id(self, trade_id, updates):
        """Update trade by ID"""
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
    
    def get_trade_by_id(self, trade_id):
        """Get trade details by ID"""
        records = self.sheet.get_all_records()
        for r in records:
            if r.get('ID') == trade_id:
                return r
        return None
    
    def calculate_new_risk(self, entry, old_sl, new_sl, old_risk, direction):
        """Calculate new risk% when SL is moved"""
        entry = float(entry)
        old_sl = float(old_sl)
        new_sl = float(new_sl)
        old_risk = float(old_risk)
        
        # Check if SL moved past entry (free risk)
        if direction == 'BUY' and new_sl >= entry:
            return 0
        if direction == 'SELL' and new_sl <= entry:
            return 0
        
        # Calculate proportional risk
        old_distance = abs(entry - old_sl)
        new_distance = abs(entry - new_sl)
        
        if old_distance == 0:
            return old_risk
        
        new_risk = old_risk * (new_distance / old_distance)
        return round(new_risk, 2)
    
    def get_stats(self, start_date=None, end_date=None):
        """Get trading statistics"""
        records = self.sheet.get_all_records()
        
        # Filter by date if provided
        if start_date:
            records = [r for r in records if r.get('Timestamp', '') >= start_date]
        if end_date:
            records = [r for r in records if r.get('Timestamp', '') <= end_date]
        
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
        
        wins = [r for r in closed if float(r.get('PnL_R', 0) or 0) > 0]
        losses = [r for r in closed if float(r.get('PnL_R', 0) or 0) < 0]
        be = [r for r in closed if float(r.get('PnL_R', 0) or 0) == 0]
        
        total_pnl = sum([float(r.get('PnL_R', 0) or 0) for r in closed])
        winrate = len(wins) / len(closed) * 100 if closed else 0
        
        return {
            'winrate': round(winrate, 1),
            'total_pnl': round(total_pnl, 2),
            'total_trades': len(closed),
            'wins': len(wins),
            'losses': len(losses),
            'be': len(be)
        }
    
    def get_stats_by_category(self, category, start_date=None, end_date=None):
        """Get stats breakdown by market or style"""
        records = self.sheet.get_all_records()
        
        if start_date:
            records = [r for r in records if r.get('Timestamp', '') >= start_date]
        if end_date:
            records = [r for r in records if r.get('Timestamp', '') <= end_date]
        
        closed = [r for r in records if r.get('Trạng thái') in ['Closed', 'BE']]
        
        stats = {}
        
        for trade in closed:
            key = trade.get(category, 'Unknown')
            if key not in stats:
                stats[key] = {'trades': [], 'wins': 0, 'losses': 0, 'be': 0, 'pnl': 0}
            
            stats[key]['trades'].append(trade)
            pnl = float(trade.get('PnL_R', 0) or 0)
            stats[key]['pnl'] += pnl
            
            if pnl > 0:
                stats[key]['wins'] += 1
            elif pnl < 0:
                stats[key]['losses'] += 1
            else:
                stats[key]['be'] += 1
        
        # Calculate winrate
        result = {}
        for key, data in stats.items():
            total = len(data['trades'])
            winrate = (data['wins'] / total * 100) if total > 0 else 0
            result[key] = {
                'winrate': round(winrate, 1),
                'pnl': round(data['pnl'], 2),
                'trades': total,
                'wins': data['wins'],
                'losses': data['losses'],
                'be': data['be']
            }
        
        return result
    
    def get_open_risk(self):
        """Get current open risk breakdown"""
        pending = self.get_pending_trades()
        
        if not pending:
            return {
                'total': 0,
                'count': 0,
                'by_market': {},
                'by_style': {},
                'trades': []
            }
        
        total_risk = sum([float(r.get('Risk%', 0) or 0) for r in pending])
        
        # By market
        by_market = {}
        for trade in pending:
            market = trade.get('Thị trường', 'Unknown')
            risk = float(trade.get('Risk%', 0) or 0)
            if market not in by_market:
                by_market[market] = {'risk': 0, 'count': 0}
            by_market[market]['risk'] += risk
            by_market[market]['count'] += 1
        
        # By style
        by_style = {}
        for trade in pending:
            style = trade.get('Kiểu', 'Unknown')
            risk = float(trade.get('Risk%', 0) or 0)
            if style not in by_style:
                by_style[style] = {'risk': 0, 'count': 0}
            by_style[style]['risk'] += risk
            by_style[style]['count'] += 1
        
        return {
            'total': round(total_risk, 2),
            'count': len(pending),
            'by_market': {k: round(v['risk'], 2) for k, v in by_market.items()},
            'by_style': {k: round(v['risk'], 2) for k, v in by_style.items()},
            'market_count': {k: v['count'] for k, v in by_market.items()},
            'style_count': {k: v['count'] for k, v in by_style.items()},
            'trades': pending
        }
