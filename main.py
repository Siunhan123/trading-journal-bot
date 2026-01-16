import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler, 
                          CallbackQueryHandler, ConversationHandler, filters, ContextTypes)
from config import BOT_TOKEN, ADMIN_USER_ID, TIMEZONE, REPORT_HOURS, REPORT_MINUTE
from sheets_handler import SheetsHandler
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
MARKET, STYLE, DIRECTION, INPUT_LINE, CHART, REASON = range(6)
UPDATE_SELECT, UPDATE_ACTION, UPDATE_INPUT = range(6, 9)
REPORT_PERIOD, REPORT_DETAIL = range(9, 11)

# Initialize sheets handler
sheets = SheetsHandler()

# Market mapping
MARKET_MAP = {
    'hanghoa': 'Hàng hóa',
    'tiente': 'Tiền tệ',
    'stockvn': 'Stock Việt',
    'stockus': 'Stock Mỹ'
}

STYLE_MAP = {
    'swing': 'Swing',
    'day': 'Daytrading',
    'scalp': 'Scalping'
}

# Keyboards
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Trade Mới", callback_data="new_trade")],
        [InlineKeyboardButton("✏️ Cập nhật Trade", callback_data="update_trade")],
        [InlineKeyboardButton("📊 Báo cáo", callback_data="report")],
        [InlineKeyboardButton("⚠️ Risk đang mở", callback_data="open_risk")]
    ])

MARKET_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("Hàng hóa", callback_data="market_hanghoa"),
     InlineKeyboardButton("Tiền tệ", callback_data="market_tiente")],
    [InlineKeyboardButton("Stock Việt", callback_data="market_stockvn"),
     InlineKeyboardButton("Stock Mỹ", callback_data="market_stockus")],
    [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
])

STYLE_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("Swing", callback_data="style_swing"),
     InlineKeyboardButton("Daytrading", callback_data="style_day"),
     InlineKeyboardButton("Scalping", callback_data="style_scalp")],
    [InlineKeyboardButton("🔙 Quay lại", callback_data="back_to_market")]
])

DIRECTION_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("🟢 BUY", callback_data="dir_buy"),
     InlineKeyboardButton("🔴 SELL", callback_data="dir_sell")],
    [InlineKeyboardButton("🔙 Quay lại", callback_data="back_to_style")]
])

def cancel_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Hủy", callback_data="cancel")
    ]])

def skip_chart_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ Bỏ qua", callback_data="skip_chart")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="back_to_direction")],
        [InlineKeyboardButton("❌ Hủy", callback_data="cancel")]
    ])

def confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Xác nhận", callback_data="confirm_trade"),
         InlineKeyboardButton("❌ Hủy", callback_data="cancel")]
    ])

# Helper function to check admin
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Bot này chỉ dành riêng cho chủ sở hữu.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🤖 *Trading Journal Bot*\n\n"
        "Chọn chức năng:",
        reply_markup=main_menu_kb(),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

# Main menu handler
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🤖 *Trading Journal Bot*\n\n"
        "Chọn chức năng:",
        reply_markup=main_menu_kb(),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

# === NEW TRADE FLOW ===

async def new_trade_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Clear previous data
    context.user_data.clear()
    
    await query.edit_message_text(
        "📊 *Bước 1/6:* Chọn thị trường:",
        reply_markup=MARKET_KB,
        parse_mode='Markdown'
    )
    return MARKET

async def market_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    market_key = query.data.split('_')[1]
    context.user_data['market'] = MARKET_MAP[market_key]
    
    await query.edit_message_text(
        f"✅ Thị trường: *{MARKET_MAP[market_key]}*\n\n"
        "⏱️ *Bước 2/6:* Chọn kiểu trade:",
        reply_markup=STYLE_KB,
        parse_mode='Markdown'
    )
    return STYLE

async def style_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    style_key = query.data.split('_')[1]
    context.user_data['style'] = STYLE_MAP[style_key]
    
    await query.edit_message_text(
        f"✅ Thị trường: *{context.user_data['market']}*\n"
        f"✅ Kiểu: *{STYLE_MAP[style_key]}*\n\n"
        "📈 *Bước 3/6:* Chọn hướng:",
        reply_markup=DIRECTION_KB,
        parse_mode='Markdown'
    )
    return DIRECTION

async def direction_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    direction = 'BUY' if 'buy' in query.data else 'SELL'
    context.user_data['direction'] = direction
    
    await query.edit_message_text(
        f"✅ Thị trường: *{context.user_data['market']}*\n"
        f"✅ Kiểu: *{context.user_data['style']}*\n"
        f"✅ Hướng: *{direction}*\n\n"
        "💹 *Bước 4/6:* Nhập thông tin trade (1 dòng):\n\n"
        "*Format:* `Ticker Entry SL Risk`\n"
        "*VD:* `XAUUSD 2650 2640 1`\n\n"
        "_(Risk không cần dấu %)_",
        reply_markup=cancel_kb(),
        parse_mode='Markdown'
    )
    return INPUT_LINE

async def input_line_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split()
    
    if len(parts) != 4:
        await update.message.reply_text(
            "❌ *Sai format!*\n\n"
            "Nhập lại: `Ticker Entry SL Risk`\n"
            "*VD:* `XAUUSD 2650 2640 1`",
            reply_markup=cancel_kb(),
            parse_mode='Markdown'
        )
        return INPUT_LINE
    
    try:
        ticker, entry, sl, risk = parts
        entry_val = float(entry)
        sl_val = float(sl)
        risk_val = float(risk)
        
        context.user_data.update({
            'ticker': ticker.upper(),
            'entry': entry_val,
            'sl': sl_val,
            'risk': risk_val
        })
        
        await update.message.reply_text(
            f"✅ Ticker: *{ticker.upper()}*\n"
            f"✅ Entry: *{entry_val}*\n"
            f"✅ SL: *{sl_val}*\n"
            f"✅ Risk: *{risk_val}%*\n\n"
            "📸 *Bước 5/6:* Gửi ảnh chart hoặc link TradingView:",
            reply_markup=skip_chart_kb(),
            parse_mode='Markdown'
        )
        return CHART
        
    except ValueError:
        await update.message.reply_text(
            "❌ *Giá trị không hợp lệ!*\n\n"
            "Entry, SL, Risk phải là số.\n"
            "Nhập lại:",
            reply_markup=cancel_kb(),
            parse_mode='Markdown'
        )
        return INPUT_LINE

# Continue in next part...
# ... (phần trên)

async def chart_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle photo
    if update.message.photo:
        photo = update.message.photo[-1]  # Get highest resolution
        file_id = photo.file_id
        context.user_data['chart'] = f"telegram_photo:{file_id}"
        chart_text = "Ảnh chart đã nhận"
    # Handle text (link)
    elif update.message.text:
        chart_link = update.message.text.strip()
        context.user_data['chart'] = chart_link
        chart_text = f"Link: {chart_link}"
    else:
        await update.message.reply_text("❌ Vui lòng gửi ảnh hoặc link!")
        return CHART
    
    await update.message.reply_text(
        f"✅ Chart: {chart_text}\n\n"
        "📝 *Bước 6/6:* Nhập lý do vào lệnh:",
        reply_markup=cancel_kb(),
        parse_mode='Markdown'
    )
    return REASON

async def skip_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['chart'] = ''
    
    await query.edit_message_text(
        "⏭️ Bỏ qua chart\n\n"
        "📝 *Bước 6/6:* Nhập lý do vào lệnh:",
        reply_markup=cancel_kb(),
        parse_mode='Markdown'
    )
    return REASON

async def reason_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    context.user_data['reason'] = reason
    
    # Show preview
    data = context.user_data
    preview = (
        "📋 *XEM TRƯỚC TRADE*\n"
        "═══════════════════\n\n"
        f"📊 Thị trường: *{data['market']}*\n"
        f"⏱️ Kiểu: *{data['style']}*\n"
        f"📈 Hướng: *{data['direction']}*\n"
        f"💹 Ticker: *{data['ticker']}*\n"
        f"💰 Entry: *{data['entry']}*\n"
        f"🛑 SL: *{data['sl']}*\n"
        f"⚠️ Risk: *{data['risk']}%*\n"
        f"📝 Lý do: _{reason}_\n\n"
    )
    
    if data.get('chart'):
        preview += "📸 Chart: Có\n\n"
    
    await update.message.reply_text(
        preview + "Xác nhận lưu trade?",
        reply_markup=confirm_kb(),
        parse_mode='Markdown'
    )
    return REASON

async def confirm_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = context.user_data
    
    # Save to sheet
    try:
        trade_id = sheets.add_trade(data)
        
        await query.edit_message_text(
            "✅ *Đã lưu trade!*\n\n"
            f"📊 {data['ticker']} {data['direction']}\n"
            f"💰 Entry: {data['entry']} | SL: {data['sl']}\n"
            f"⚠️ Risk: {data['risk']}%\n\n"
            f"🆔 Trade ID: #{trade_id}",
            parse_mode='Markdown'
        )
        
        # Clear data
        context.user_data.clear()
        
        # Show main menu after 2 seconds
        await query.message.reply_text(
            "Chọn chức năng tiếp theo:",
            reply_markup=main_menu_kb()
        )
        
    except Exception as e:
        logger.error(f"Error saving trade: {e}")
        await query.edit_message_text(
            f"❌ Lỗi khi lưu trade: {str(e)}\n\n"
            "Vui lòng thử lại.",
            reply_markup=main_menu_kb()
        )
    
    return ConversationHandler.END

# === UPDATE TRADE FLOW ===

async def update_trade_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Get pending trades
    pending = sheets.get_pending_trades()
    
    if not pending:
        await query.edit_message_text(
            "✅ Không có lệnh đang mở",
            reply_markup=main_menu_kb()
        )
        return ConversationHandler.END
    
    # Create buttons for each trade
    buttons = []
    for trade in pending:
        trade_id = trade.get('ID')
        ticker = trade.get('Ticker', 'N/A')
        direction = trade.get('Hướng', 'N/A')
        entry = trade.get('Entry', 'N/A')
        risk = trade.get('Risk%', 'N/A')
        
        button_text = f"#{trade_id} {ticker} {direction} @ {entry} (Risk: {risk}%)"
        buttons.append([InlineKeyboardButton(button_text, callback_data=f"select_{trade_id}")])
    
    buttons.append([InlineKeyboardButton("🔙 Menu", callback_data="main_menu")])
    
    await query.edit_message_text(
        "✏️ *Chọn trade cần cập nhật:*",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )
    return UPDATE_SELECT

async def trade_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    trade_id = int(query.data.split('_')[1])
    context.user_data['selected_trade_id'] = trade_id
    
    # Get trade details
    trade = sheets.get_trade_by_id(trade_id)
    
    if not trade:
        await query.edit_message_text(
            "❌ Không tìm thấy trade",
            reply_markup=main_menu_kb()
        )
        return ConversationHandler.END
    
    # Show trade details
    details = (
        f"📋 *TRADE #{trade_id}*\n"
        "═══════════════════\n\n"
        f"📊 Thị trường: *{trade.get('Thị trường')}*\n"
        f"⏱️ Kiểu: *{trade.get('Kiểu')}*\n"
        f"📈 Hướng: *{trade.get('Hướng')}*\n"
        f"💹 Ticker: *{trade.get('Ticker')}*\n"
        f"💰 Entry: *{trade.get('Entry')}*\n"
        f"🛑 SL: *{trade.get('SL')}*\n"
        f"⚠️ Risk: *{trade.get('Risk%')}%*\n"
        f"📝 Lý do: _{trade.get('Lý do', 'N/A')}_\n\n"
    )
    
    # Quick action buttons
    action_buttons = [
        [InlineKeyboardButton("✅ Thắng full", callback_data="action_win"),
         InlineKeyboardButton("💰 Chốt 1 phần", callback_data="action_partial")],
        [InlineKeyboardButton("❌ Thua", callback_data="action_loss"),
         InlineKeyboardButton("⚖️ BE", callback_data="action_be")],
        [InlineKeyboardButton("📈 Nâng SL", callback_data="action_movesl"),
         InlineKeyboardButton("🎯 Set TP", callback_data="action_settp")],
        [InlineKeyboardButton("📝 Sửa lý do", callback_data="action_editreason"),
         InlineKeyboardButton("🚫 Hủy lệnh", callback_data="action_cancel")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="update_trade")]
    ]
    
    await query.edit_message_text(
        details + "Chọn hành động:",
        reply_markup=InlineKeyboardMarkup(action_buttons),
        parse_mode='Markdown'
    )
    return UPDATE_ACTION

async def action_win(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['action'] = 'win'
    
    await query.edit_message_text(
        "✅ *Thắng full*\n\n"
        "Nhập PnL (R):\n"
        "*VD:* `2.5` hoặc `3`",
        reply_markup=cancel_kb(),
        parse_mode='Markdown'
    )
    return UPDATE_INPUT

async def action_loss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['action'] = 'loss'
    
    await query.edit_message_text(
        "❌ *Thua*\n\n"
        "Nhập PnL (R):\n"
        "*VD:* `-1` hoặc `-0.5`",
        reply_markup=cancel_kb(),
        parse_mode='Markdown'
    )
    return UPDATE_INPUT

async def action_be(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    trade_id = context.user_data.get('selected_trade_id')
    
    # Update sheet
    sheets.update_trade_by_id(trade_id, {
        'Trạng thái': 'Closed',
        'PnL_R': 0
    })
    
    await query.edit_message_text(
        f"⚖️ *Trade #{trade_id} đã đóng ở BE*\n"
        "PnL: 0R",
        reply_markup=main_menu_kb(),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def action_movesl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['action'] = 'movesl'
    
    await query.edit_message_text(
        "📈 *Nâng Stop Loss*\n\n"
        "Nhập SL mới:\n"
        "*VD:* `2655`",
        reply_markup=cancel_kb(),
        parse_mode='Markdown'
    )
    return UPDATE_INPUT

async def action_settp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['action'] = 'settp'
    
    await query.edit_message_text(
        "🎯 *Set Take Profit*\n\n"
        "Nhập TP:\n"
        "*VD:* `2680`",
        reply_markup=cancel_kb(),
        parse_mode='Markdown'
    )
    return UPDATE_INPUT

async def action_partial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['action'] = 'partial'
    
    await query.edit_message_text(
        "💰 *Chốt 1 phần*\n\n"
        "Nhập: `% đóng PnL(R)`\n"
        "*VD:* `50 1.2` (đóng 50%, lời 1.2R)",
        reply_markup=cancel_kb(),
        parse_mode='Markdown'
    )
    return UPDATE_INPUT

async def action_editreason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['action'] = 'editreason'
    
    await query.edit_message_text(
        "📝 *Sửa lý do*\n\n"
        "Nhập lý do mới:",
        reply_markup=cancel_kb(),
        parse_mode='Markdown'
    )
    return UPDATE_INPUT

async def action_cancel_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    trade_id = context.user_data.get('selected_trade_id')
    
    sheets.update_trade_by_id(trade_id, {
        'Trạng thái': 'Cancelled'
    })
    
    await query.edit_message_text(
        f"🚫 *Trade #{trade_id} đã hủy*",
        reply_markup=main_menu_kb(),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

# Continue in next part...
# ... (phần trên)

async def update_input_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    action = context.user_data.get('action')
    trade_id = context.user_data.get('selected_trade_id')
    
    try:
        if action == 'win' or action == 'loss':
            pnl = float(text)
            sheets.update_trade_by_id(trade_id, {
                'Trạng thái': 'Closed',
                'PnL_R': pnl * 10  # ← LỖI: NHÂN 10
            })

            
        elif action == 'movesl':
            new_sl = float(text)
            trade = sheets.get_trade_by_id(trade_id)
            
            # Calculate new risk
            entry = float(trade['Entry'])
            old_sl = float(trade['SL'])
            old_risk = float(trade['Risk%'])
            direction = trade['Hướng']
            
            new_risk = sheets.calculate_new_risk(entry, old_sl, new_sl, old_risk, direction)
            
            sheets.update_trade_by_id(trade_id, {
                'SL': new_sl,
                'Risk%': new_risk
            })
            
            risk_status = "🎉 Free risk!" if new_risk == 0 else f"Risk mới: {new_risk}%"
            
            await update.message.reply_text(
                f"📈 *SL đã nâng lên {new_sl}*\n\n"
                f"{risk_status}",
                reply_markup=main_menu_kb(),
                parse_mode='Markdown'
            )
            
        elif action == 'settp':
            tp = float(text)
            sheets.update_trade_by_id(trade_id, {'TP': tp})
            await update.message.reply_text(
                f"🎯 *TP đã set: {tp}*",
                reply_markup=main_menu_kb(),
                parse_mode='Markdown'
            )
            
        elif action == 'partial':
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text(
                    "❌ Sai format! Nhập: `% PnL`\nVD: `50 1.2`",
                    parse_mode='Markdown'
                )
                return UPDATE_INPUT
            
            percent = float(parts[0])
            pnl = float(parts[1])
            
            trade = sheets.get_trade_by_id(trade_id)
            note = trade.get('Ghi chú', '')
            new_note = f"{note}\nChốt {percent}%: +{pnl}R".strip()
            
            sheets.update_trade_by_id(trade_id, {'Ghi chú': new_note})
            
            await update.message.reply_text(
                f"💰 *Đã chốt {percent}% với +{pnl}R*\n\n"
                f"Trade #{trade_id} vẫn đang mở",
                reply_markup=main_menu_kb(),
                parse_mode='Markdown'
            )
            
        elif action == 'editreason':
            new_reason = text
            sheets.update_trade_by_id(trade_id, {'Lý do': new_reason})
            await update.message.reply_text(
                "📝 *Lý do đã cập nhật*",
                reply_markup=main_menu_kb(),
                parse_mode='Markdown'
            )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ Giá trị không hợp lệ! Nhập lại:",
            reply_markup=cancel_kb()
        )
        return UPDATE_INPUT
    except Exception as e:
        logger.error(f"Error updating trade: {e}")
        await update.message.reply_text(
            f"❌ Lỗi: {str(e)}",
            reply_markup=main_menu_kb()
        )
        return ConversationHandler.END

# === REPORT FLOW ===

async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    period_buttons = [
        [InlineKeyboardButton("Hôm nay", callback_data="period_today"),
         InlineKeyboardButton("Tuần này", callback_data="period_week")],
        [InlineKeyboardButton("Tháng này", callback_data="period_month"),
         InlineKeyboardButton("Tùy chỉnh", callback_data="period_custom")],
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "📊 *Chọn khoảng thời gian:*",
        reply_markup=InlineKeyboardMarkup(period_buttons),
        parse_mode='Markdown'
    )
    return REPORT_PERIOD

async def period_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    period = query.data.split('_')[1]
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
        end = now.strftime('%Y-%m-%d %H:%M:%S')
        period_text = "HÔM NAY"
    elif period == 'week':
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
        end = now.strftime('%Y-%m-%d %H:%M:%S')
        period_text = "TUẦN NÀY"
    elif period == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
        end = now.strftime('%Y-%m-%d %H:%M:%S')
        period_text = "THÁNG NÀY"
    else:
        await query.edit_message_text(
            "🗓️ Tùy chỉnh chưa hỗ trợ\n\nQuay lại menu:",
            reply_markup=main_menu_kb()
        )
        return ConversationHandler.END
    
    # Get stats
    stats = sheets.get_stats(start, end)
    
    report = f"📊 BÁO CÁO {period_text}\n\n"
    report += f"Winrate: {stats['winrate']}%\n"
    report += f"{stats['wins']}W-{stats['losses']}L-{stats['be']}BE\n"
    report += f"Tổng PnL: {stats['total_pnl']}R\n"  # ← FIX: Bỏ .2f nếu đã round
    report += f"Số lệnh: {stats['total_trades']}\n"

    
    detail_buttons = [
        [InlineKeyboardButton("📊 Chi tiết Thị trường", callback_data=f"detail_market_{period}"),
         InlineKeyboardButton("⏱️ Chi tiết Kiểu trade", callback_data=f"detail_style_{period}")],
        [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        report,
        reply_markup=InlineKeyboardMarkup(detail_buttons),
        parse_mode='Markdown'
    )
    return REPORT_DETAIL

async def detail_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    detail_type = parts[1]  # market or style
    period = parts[2]
    
    # Get date range (same logic as above)
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
    elif period == 'week':
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
    
    end = now.strftime('%Y-%m-%d %H:%M:%S')
    
    # Get breakdown stats
    if detail_type == 'market':
        category = 'Thị trường'
        title = "📊 THEO THỊ TRƯỜNG"
    else:
        category = 'Kiểu'
        title = "⏱️ THEO KIỂU TRADE"
    
    stats = sheets.get_stats_by_category(category, start, end)
    
    detail_text = f"{title}\n────────────────────\n\n"
    
    for key, data in stats.items():
        detail_text += (
            f"• *{key}:* {data['winrate']}% WR, "
            f"{data['pnl']:+.2f}R ({data['trades']} lệnh)\n"
        )
    
    await query.edit_message_text(
        detail_text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Quay lại", callback_data="report")
        ]]),
        parse_mode='Markdown'
    )
    return REPORT_DETAIL

# === OPEN RISK ===

async def open_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current open risk - with refresh button"""
    query = update.callback_query
    await query.answer()  # Always answer callback first
    
    try:
        risk_data = sheets.get_open_risk()
        pending_trades = risk_data.get('trades', [])
        
        if risk_data['count'] == 0:
            msg = "📊 RISK ĐANG MỞ\n\n"
            msg += "✅ Không có lệnh đang mở\n"
            msg += "TỔNG RISK: 0%"
        else:
            msg = "📊 RISK ĐANG MỞ\n\n"
            msg += f"🎯 TỔNG RISK: {risk_data['total']}%\n"
            msg += f"📝 Số lệnh: {risk_data['count']}\n\n"
            
            # Theo thị trường
            if risk_data.get('market_count'):
                msg += "📍 THEO THỊ TRƯỜNG:\n"
                for market, risk in risk_data['market_count'].items():
                    msg += f"  • {market}: {risk}%\n"
                msg += "\n"
            
            # Theo kiểu trade
            if risk_data.get('style_count'):
                msg += "📊 THEO KIỂU TRADE:\n"
                for style, risk in risk_data['style_count'].items():
                    msg += f"  • {style}: {risk}%\n"
                msg += "\n"
            
            # Chi tiết trades (giới hạn 10)
            if pending_trades:
                msg += "📋 CHI TIẾT LỆNH:\n"
                for idx, trade in enumerate(pending_trades[:10], 1):
                    ticker = trade.get('Ticker', 'N/A')
                    direction = trade.get('Hướng', 'N/A')
                    risk = trade.get('Risk%', 0)
                    msg += f"{idx}. {ticker} {direction} - {risk}%\n"
                
                if len(pending_trades) > 10:
                    msg += f"\n... và {len(pending_trades) - 10} lệnh khác"
        
        # Add timestamp to force message difference on refresh
        from datetime import datetime
        import pytz
        from config import TIMEZONE
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz).strftime('%H:%M:%S')
        msg += f"\n\n🔄 Cập nhật: {now}"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data='open_risk')],
            [InlineKeyboardButton("« Menu", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Try to edit message, catch if not modified
        try:
            await query.edit_message_text(
                text=msg,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            if "message is not modified" in str(e).lower():
                # Silently ignore - user already has the latest data
                pass
            else:
                # Re-raise other errors
                raise
        
    except Exception as e:
        print(f"❌ Error in open_risk: {e}")
        try:
            await query.edit_message_text(
                text=f"❌ Lỗi: {e}\n\nQuay lại /start",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Menu", callback_data='main_menu')]
                ])
            )
        except:
            # If can't edit, send new message
            await query.message.reply_text(
                text=f"❌ Lỗi: {e}\n\nQuay lại /start",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Menu", callback_data='main_menu')]
                ])
            )


# === SCHEDULED RISK REPORT ===

async def send_scheduled_risk_report(application: Application):
    """Send risk report at scheduled times - Show PENDING trades"""
    try:
        risk_data = sheets.get_open_risk()
        pending_trades = risk_data.get('trades', [])  # Get pending trades list
        
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        time_str = now.strftime("%d/%m/%Y - %H:%M JST")
        
        if risk_data['count'] == 0:
            report = "📊 BÁO CÁO RISK ĐANG MỞ\n"
            report += f"🕒 {time_str}\n\n"
            report += "✅ Không có lệnh đang mở\n"
            report += "TỔNG RISK: 0%"
        else:
            report = "📊 BÁO CÁO RISK ĐANG MỞ\n"
            report += f"🕒 {time_str}\n\n"
            report += f"🎯 TỔNG RISK: {risk_data['total']}%\n"
            report += f"📝 Số lệnh đang mở: {risk_data['count']}\n\n"
            
            # Theo thị trường
            report += "📍 THEO THỊ TRƯỜNG:\n"
            for market, risk in risk_data.get('market_count', {}).items():
                report += f"  • {market}: {risk}%\n"
            
            report += "\n📊 THEO KIỂU TRADE:\n"
            for style, risk in risk_data.get('style_count', {}).items():
                report += f"  • {style}: {risk}%\n"
            
            # CHI TIẾT LỆNH ĐANG MỞ (PENDING)
            report += "\n📋 CÁC LỆNH ĐANG MỞ:\n"
            for idx, trade in enumerate(pending_trades[:10], 1):
                ticker = trade.get('Ticker', 'N/A')
                direction = trade.get('Hướng', 'N/A')
                entry = trade.get('Entry', 'N/A')
                sl = trade.get('SL', 'N/A')
                risk = trade.get('Risk%', 0)
                
                report += f"{idx}. {ticker} {direction} @ {entry}\n"
                report += f"   SL: {sl} | Risk: {risk}%\n"
            
            if len(pending_trades) > 10:
                report += f"\n... và {len(pending_trades) - 10} lệnh khác"
        
        # Send to admin
        await application.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=report,
            parse_mode='Markdown'
        )
        logger.info(f"✅ Scheduled risk report sent at {time_str}")
        
    except Exception as e:
        logger.error(f"❌ Error sending scheduled report: {e}")



# === CANCEL HANDLER ===

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "❌ Đã hủy",
            reply_markup=main_menu_kb()
        )
    else:
        await update.message.reply_text(
            "❌ Đã hủy",
            reply_markup=main_menu_kb()
        )
    context.user_data.clear()
    return ConversationHandler.END

# === MAIN ===

def main():
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for new trade
    new_trade_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(new_trade_start, pattern='^new_trade$')],
        states={
            MARKET: [CallbackQueryHandler(market_selected, pattern='^market_')],
            STYLE: [CallbackQueryHandler(style_selected, pattern='^style_')],
            DIRECTION: [CallbackQueryHandler(direction_selected, pattern='^dir_')],
            INPUT_LINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_line_received)],
            CHART: [
                MessageHandler(filters.PHOTO, chart_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, chart_received),
                CallbackQueryHandler(skip_chart, pattern='^skip_chart$')
            ],
            REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reason_received),
                CallbackQueryHandler(confirm_trade, pattern='^confirm_trade$')
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern='^cancel$')]
       
    )
    
    # Conversation handler for update trade
    update_trade_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(update_trade_start, pattern='^update_trade$')],
        states={
            UPDATE_SELECT: [CallbackQueryHandler(trade_selected, pattern='^select_')],
            UPDATE_ACTION: [
                CallbackQueryHandler(action_win, pattern='^action_win$'),
                CallbackQueryHandler(action_loss, pattern='^action_loss$'),
                CallbackQueryHandler(action_be, pattern='^action_be$'),
                CallbackQueryHandler(action_movesl, pattern='^action_movesl$'),
                CallbackQueryHandler(action_settp, pattern='^action_settp$'),
                CallbackQueryHandler(action_partial, pattern='^action_partial$'),
                CallbackQueryHandler(action_editreason, pattern='^action_editreason$'),
                CallbackQueryHandler(action_cancel_trade, pattern='^action_cancel$'),
                CallbackQueryHandler(update_trade_start, pattern='^update_trade$')
            ],
            UPDATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_input_received)]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern='^cancel$')]
      
    )
    
    # Conversation handler for report
    report_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(report_start, pattern='^report$')],
        states={
            REPORT_PERIOD: [CallbackQueryHandler(period_selected, pattern='^period_')],
            REPORT_DETAIL: [
                CallbackQueryHandler(detail_selected, pattern='^detail_'),
                CallbackQueryHandler(report_start, pattern='^report$')
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern='^cancel$')]
        
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("risk", lambda u, c: open_risk(u, c)))
    application.add_handler(new_trade_conv)
    application.add_handler(update_trade_conv)
    application.add_handler(report_conv)
    application.add_handler(CallbackQueryHandler(open_risk, pattern='^open_risk$'))
    application.add_handler(CallbackQueryHandler(main_menu, pattern='^main_menu$'))
    
    # Setup scheduler for automatic reports
    scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))
    for hour in REPORT_HOURS:
        scheduler.add_job(
            send_scheduled_risk_report,
            'cron',
            hour=hour,
            minute=REPORT_MINUTE,
            args=[application]
        )
    scheduler.start()
    
    # Start bot
    logger.info("Bot started!")
    application.run_polling()

if __name__ == '__main__':
    main()
