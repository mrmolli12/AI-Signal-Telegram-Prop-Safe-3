import os
import logging
import pandas as pd
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from datetime import datetime
import yfinance as yf
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FundedNext15KBot:
    def __init__(self):
        self.balance = ACCOUNT_SIZE
        self.daily_start = ACCOUNT_SIZE
        self.trades_per_pair = {}
        
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
        
        data = yf.download(f"{symbol}=X", period="20d", interval="1h")
        data['RSI'] = self.rsi(data['Close'])
        
        rsi = data['RSI'].iloc[-1]
        signal = "HOLD ⚪"
        if rsi < 28:
            signal = "BUY 🟢"
        elif rsi > 72:
            signal = "SELL 🔴"
        
        # WRITE TO MT5 (CRITICAL)
        mt5_signal = "HOLD"
        if "BUY" in signal: mt5_signal = "BUY"
        if "SELL" in signal: mt5_signal = "SELL"
        self.write_mt5_signal(mt5_signal)
        
        lot_size = RISK_PER_TRADE / (15 * 10)  # 15 pip SL
        return {
            'signal': signal, 'status': status, 'rsi': f"{rsi:.1f}",
            'lot_size': f"{lot_size:.2f}", 'risk': f"${RISK_PER_TRADE}"
        }
    
    def write_mt5_signal(self, signal):
        """🚨 THIS MAKES EA WORK"""
        with open('signals.txt', 'w') as f:
            f.write(signal)
        print(f"📡 MT5 Signal written: {signal}")
    
    def rsi(self, prices, period=14):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = -delta.where(delta < 0, 0).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

bot = FundedNext15KBot()

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = context.args[0].upper() if context.args else "EURUSD"
    sig = bot.generate_signal(symbol)
    
    if sig['signal'] == 'BLOCKED':
        await update.message.reply_text(sig['reason'])
        return
    
    message = (
        f"🚀 **$15K FUNDEDNEXT SIGNAL**\n\n"
        f"🎯 {sig['signal']} {symbol}\n"
        f"📊 RSI: {sig['rsi']} | {sig['status']}\n\n"
        f"📋 **MT5 AUTO-TRADE**:\n"
        f"💱 {symbol} | 📦 {sig['lot_size']} lots\n"
        f"💰 Risk: {sig['risk']} | 🛑 15pips | 🎯 30pips\n\n"
        f"✅ **EA EXECUTING NOW**"
    )
    await update.message.reply_text(message)

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 **FUNDEDNEXT $15K STATUS**\n\n"
        f"💼 Balance: ${bot.balance:,.0f}\n"
        f"📉 DD Used: ${(bot.daily_start-bot.balance):.0f}/$750\n"
        f"🔢 Active Pairs: {len(bot.trades_per_pair)}\n\n"
        f"🟢 **EA LIVE & AUTO-TRADING**"
    )

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("signal", signal))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("start", dashboard))
    print("🤖 FundedNext $15K Bot + EA Live!")
    app.run_polling()

if __name__ == '__main__':
    main()
