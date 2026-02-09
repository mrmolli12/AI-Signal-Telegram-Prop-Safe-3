import os
import logging
import pandas as pd
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from datetime import datetime, timedelta
import yfinance as yf

# ========== FUNDEDNEXT $15K SETTINGS ==========
ACCOUNT_BALANCE = 15000
MAX_DAILY_DD = 750      # $750 (5%)
MAX_OVERALL_DD = 1500   # $1,500 (10%)
RISK_PER_TRADE = 75     # $75 (0.5%)
MAX_TRADES_PER_PAIR = 5 # Your custom rule
MIN_SL_PIPS = 15
MAX_SPREAD = 25

class FundedNext15KBot:
    def __init__(self):
        self.balance = ACCOUNT_BALANCE
        self.daily_start = ACCOUNT_BALANCE
        self.trades_per_pair = {}  # {"EURUSD": 2}
        
    def check_15k_rules(self, symbol):
        """FundedNext $15K + 5 trades/pair"""
        
        # DAILY DD ($750 max)
        daily_pnl = self.balance - self.daily_start
        if daily_pnl <= -MAX_DAILY_DD * 0.98:
            return False, f"❌ **DAILY DD: ${-daily_pnl:.0f}/$750**"
        
        # OVERALL DD ($1500 max)  
        overall_pnl = self.balance - ACCOUNT_BALANCE
        if overall_pnl <= -MAX_OVERALL_DD * 0.95:
            return False, f"❌ **OVERALL DD: ${-overall_pnl:.0f}/$1,500**"
        
        # MAX 5 TRADES PER PAIR (YOUR RULE)
        trades_count = self.trades_per_pair.get(symbol, 0)
        if trades_count >= MAX_TRADES_PER_PAIR:
            return False, f"❌ **MAX 5 TRADES/PAIR** - {symbol}: {trades_count}/5"
        
        return True, f"✅ **$15K SAFE** | {symbol}: {trades_count}/5"
    
    def calculate_position(self):
        """FundedNext $15K sizing"""
        sl_pips = MIN_SL_PIPS
        pip_value = 10  # Standard forex
        lot_size = RISK_PER_TRADE / (sl_pips * pip_value)
        return round(lot_size, 2)
    
    def generate_signal(self, symbol="EURUSD"):
        is_safe, status = self.check_15k_rules(symbol)
        
        if not is_safe:
            return {'signal': 'BLOCKED', 'reason': status}
        
        # AI Signal (Conservative for FundedNext)
        data = yf.download(f"{symbol}=X", period="20d", interval="1h")
        data['RSI'] = self.rsi(data['Close'])
        data['SMA10'] = data['Close'].rolling(10).mean()
        
        rsi = data['RSI'].iloc[-1]
        momentum = data['Close'].iloc[-1] > data['SMA10'].iloc[-1]
        
        signal = "HOLD ⚪"
        if rsi < 28 and momentum:
            signal = "BUY 🟢"
        elif rsi > 72 and not momentum:
            signal = "SELL 🔴"
        
        lot_size = self.calculate_position()
        
        return {
            'signal': signal,
            'status': status,
            'rsi': f"{rsi:.1f}",
            'lot_size': lot_size,
            'risk_amount': f"${RISK_PER_TRADE}",
            'sl_pips': MIN_SL_PIPS,
            'trades_left': MAX_TRADES_PER_PAIR - self.trades_per_pair.get(symbol, 0)
        }
    
    def record_trade(self, symbol):
        """Track trades per pair"""
        if symbol not in self.trades_per_pair:
            self.trades_per_pair[symbol] = 0
        self.trades_per_pair[symbol] += 1
    
    def rsi(self, prices, period=14):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = -delta.where(delta < 0, 0).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

# Global bot instance
fn15k = FundedNext15KBot()

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = (context.args[0].upper() if context.args else "EURUSD")
    sig = fn15k.generate_signal(symbol)
    
    if sig['signal'] == 'BLOCKED':
        keyboard = [[InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(sig['reason'], reply_markup=reply_markup)
        return
    
    # Success message with MT5 copy-paste
    message = (
        f"🚀 **FUNDEDNEXT $15K SIGNAL**\n\n"
        f"🎯 **{sig['signal']} {symbol}**\n"
        f"📊 RSI: {sig['rsi']} | {sig['status']}\n\n"
        f"📋 **MT5 TRADE SETUP**:\n"
        f"💱 Symbol: {symbol}\n"
        f"📦 Lots: {sig['lot_size']}\n"
        f"💰 Risk: {sig['risk_amount']} (0.5%)\n"
        f"🛑 SL: {sig['sl_pips']} pips\n"
        f"🎯 TP: 30 pips\n"
        f"🔢 Trades left: {sig['trades_left']}/5\n\n"
        f"✅ **15K ACCOUNT SAFE**"
    )
    
    keyboard = [[InlineKeyboardButton("✅ Trade Executed", callback_data=f"trade_{symbol}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    daily_pnl = fn15k.balance - fn15k.daily_start
    overall_pnl = fn15k.balance - ACCOUNT_BALANCE
    
    pairs_status = "\n".join([f"{pair}: {count}/5" for pair, count in list(fn15k.trades_per_pair.items())[:5]])
    
    message = (
        f"📊 **FUNDEDNEXT $15K DASHBOARD**\n\n"
        f"💼 Balance: ${fn15k.balance:,.0f}\n"
        f"📈 Daily P&L: ${daily_pnl:+,.0f} (-{min(0,daily_pnl)/MAX_DAILY_DD*100:.1f}%)\n"
        f"📉 Overall P&L: ${overall_pnl:+,.0f}\n\n"
        f"🎯 **PAIRS STATUS**:\n{pairs_status or 'No trades'}\n\n"
        f"🟢 **CHALLENGE ACTIVE**"
    )
    
    await update.message.reply_text(message)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("trade_"):
        symbol = query.data.replace("trade_", "")
        fn15k.record_trade(symbol)
        await query.edit_message_text(f"✅ **Trade recorded**: {symbol}\n📊 Use /dashboard")
    elif query.data == "dashboard":
        await dashboard(query, context)

def main():
    TOKEN = os.getenv('TELEGRAM_TOKEN')
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("start", dashboard))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🚀 FundedNext $15K Bot Live!")
    app.run_polling()

if __name__ == '__main__':
    main()
