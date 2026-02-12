import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
import yfinance as yf
import numpy as np
from config import *

class FundedNext15KBot:
    def __init__(self):
        self.balance = ACCOUNT_SIZE
        self.daily_start = ACCOUNT_SIZE
        self.trades_per_pair = {}
        
    def rsi_simple(self, closes, period=14):
        """Pure numpy RSI - NO PANDAS NEEDED"""
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        return 100 - (100 / (1 + rs))
    
    def check_rules(self, symbol):
        daily_pnl = self.balance - self.daily_start
        if daily_pnl <= -MAX_DAILY_DD * 0.98:
            return False, f"❌ DAILY DD: ${-daily_pnl:.0f}/$750"
        
        trades = self.trades_per_pair.get(symbol, 0)
        if trades >= MAX_TRADES_PER_PAIR:
            return False, f"❌ MAX 5 TRADES - {symbol}: {trades}/5"
        
        return True, f"✅ $15K SAFE | {trades}/5"
    
    def generate_signal(self, symbol="EURUSD"):
        is_safe, status = self.check_rules(symbol)
        if not is_safe:
            return {'signal': 'BLOCKED', 'reason': status}
        
        # yfinance → numpy array (NO PANDAS)
        data = yf.download(f"{symbol}=X", period="20d", interval="1h", progress=False)
        closes = data['Close'].values
        
        rsi = self.rsi_simple(closes)
        signal = "HOLD ⚪"
        if rsi < 28:
            signal = "BUY 🟢"
        elif rsi > 72:
            signal = "SELL 🔴"
        
        # MT5 SIGNAL FILE
        mt5_signal = "HOLD"
        if "BUY" in signal: mt5_signal = "BUY"
        if "SELL" in signal: mt5_signal = "SELL"
        self.write_mt5_signal(mt5_signal)
        
        lot_size = 0.50  # Fixed for $15K
        return {
            'signal': signal, 'status': status, 'rsi': f"{rsi:.1f}",
            'lot_size': f"{lot_size:.2f}", 'risk': f"$75"
        }
    
    def write_mt5_signal(self, signal):
        with open('signals.txt', 'w') as f:
            f.write(signal)
        print(f"📡 MT5 → {signal}")

bot = FundedNext15KBot()

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = (context.args[0].upper() if context.args else "EURUSD")
    sig = bot.generate_signal(symbol)
    
    if sig['signal'] == 'BLOCKED':
        await update.message.reply_text(sig['reason'])
        return
    
    message = (
        f"🚀 **$15K SIGNAL**\n\n"
        f"🎯 {sig['signal']} {symbol}\n"
        f"📊 RSI: {sig['rsi']} | {sig['status']}\n\n"
        f"💱 {symbol} H1\n"
        f"📦 0.50 lots | 🛑 15pips | 🎯 30pips\n"
        f"💰 Risk: {sig['risk']}\n\n"
        f"✅ **EA AUTO-TRADING**"
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 **$15K STATUS**\n\n"
        f"💼 Balance: ${bot.balance:,.0f}\n"
        f"📉 DD: ${(bot.daily_start-bot.balance):.0f}/$750\n"
        f"🔢 Pairs: {len(bot.trades_per_pair)}\n\n"
        f"🟢 **LIVE & AUTO**"
    )

if __name__ == '__main__':
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("start", dashboard))
    print("🤖 $15K Bot LIVE!")
    app.run_polling()
