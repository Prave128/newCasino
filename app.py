import logging
import sqlite3
import random
import string
import re
import asyncio
import os
import shutil
import threading
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import warnings
warnings.filterwarnings("ignore")

# ============ FLASK WEB SERVER FOR RENDER ============
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running! 🚀"

@web_app.route('/health')
def health():
    return "OK", 200

def run_web():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# ============ REST OF YOUR BOT CODE ============

# ============ END FLASK WEB SERVER ============

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8895716035:AAFb4bRC-cwgb6IICsxE8ZWnSXMzK_4Qw_c"
BOT_USERNAME = "Casino_blazer_bot"
ADMIN_USER_ID = 5943318266
ADMIN_USERNAME = "@XTOP_879"
BRAND_NAME = "🎰 CASINO BLAZE"
DB_PATH = "masterdice.db"
BACKUP_DIR = "backups"

UPI_ID = "vardhan1@naviaxis"
QR_CODE_IMAGE = "qr-code.png"
THANK_YOU_IMAGE = "thankyou.png"

MIN_DEPOSIT = 40
MIN_WITHDRAW = 60

DICE_EMOJIS = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

# Create backup directory if not exists
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def get_brand_header():
    return """
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🎰 CASINO BLAZE  🎰              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
"""

def get_game_emoji(game_type):
    emojis = {
        'dice': '🎲',
        'dart': '🎯',
        'bowling': '🎳',
        'basketball': '🏀',
        'football': '⚽'
    }
    return emojis.get(game_type, '🎲')

def get_game_roll_emoji(game_type):
    emojis = {
        'dice': '🎲',
        'dart': '🎯',
        'bowling': '🎳',
        'basketball': '🏀',
        'football': '⚽'
    }
    return emojis.get(game_type, '🎲')

def get_game_name(game_type):
    names = {
        'dice': 'Dice',
        'dart': 'Dart',
        'bowling': 'Bowling',
        'basketball': 'Basketball',
        'football': 'Football'
    }
    return names.get(game_type, 'Game')

# ============ DATABASE ============

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def backup_database():
    """Create a backup of the database"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(BACKUP_DIR, f"masterdice_backup_{timestamp}.db")
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"Database backed up to {backup_path}")
        
        # Keep only last 10 backups
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
        if len(backups) > 10:
            for old_backup in backups[:-10]:
                os.remove(os.path.join(BACKUP_DIR, old_backup))
        return True
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            currency TEXT DEFAULT 'INR',
            balance INTEGER DEFAULT 0,
            upi_address TEXT,
            total_games INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            total_losses INTEGER DEFAULT 0,
            referral_code TEXT,
            daily_bonus_claimed TIMESTAMP,
            daily_bonus_streak INTEGER DEFAULT 0,
            total_deposited INTEGER DEFAULT 0,
            total_withdrawn INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount INTEGER,
            currency TEXT,
            balance_after INTEGER,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            bet_amount INTEGER,
            currency TEXT,
            result TEXT,
            won_amount INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS challenges (
            challenge_id TEXT PRIMARY KEY,
            challenger_id INTEGER,
            challenged_id INTEGER,
            bet_amount INTEGER,
            game_type TEXT,
            rolls INTEGER,
            win_condition TEXT,
            status TEXT DEFAULT 'pending',
            challenger_name TEXT,
            challenged_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS active_games (
            game_id TEXT PRIMARY KEY,
            challenge_id TEXT,
            player1_id INTEGER,
            player2_id INTEGER,
            bet_amount INTEGER,
            game_type TEXT,
            rolls INTEGER,
            win_condition TEXT,
            current_turn INTEGER,
            player1_rolls TEXT,
            player2_rolls TEXT,
            player1_wins INTEGER DEFAULT 0,
            player2_wins INTEGER DEFAULT 0,
            current_round INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS bank_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount INTEGER,
            utr TEXT DEFAULT '',
            time_frame TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_user INTEGER,
            amount INTEGER,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized!")
    
    # Create initial backup
    backup_database()

def get_or_create_user(user_id, username, first_name, last_name=None):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    
    if not user:
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        c.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, referral_code, balance)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username or f"user_{user_id}", first_name or "User", last_name or "", referral_code, 0))
        conn.commit()
    
    conn.close()
    return get_user_profile(user_id)

def get_user_profile(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        return {
            'user_id': user[0],
            'username': user[1] or f"User{user[0]}",
            'first_name': user[2] or "User",
            'last_name': user[3] or "",
            'currency': user[4] or 'INR',
            'balance': user[5] or 0,
            'upi_address': user[6] or "",
            'total_games': user[7] or 0,
            'total_wins': user[8] or 0,
            'total_losses': user[9] or 0,
            'referral_code': user[10] or "",
            'daily_bonus_claimed': user[11],
            'daily_bonus_streak': user[12] or 0,
            'total_deposited': user[13] or 0,
            'total_withdrawn': user[14] or 0,
            'created_at': user[15]
        }
    return None

def update_wallet(user_id, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()
    backup_database()

def get_balance(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def set_upi_address(user_id, upi_address):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET upi_address = ? WHERE user_id = ?', (upi_address, user_id))
    conn.commit()
    conn.close()

def get_game_history(user_id, limit=20):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT game_type, bet_amount, currency, result, won_amount, created_at 
        FROM game_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
    ''', (user_id, limit))
    games = c.fetchall()
    conn.close()
    return games

def save_game_history(user_id, game_type, bet_amount, currency, result, won_amount):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO game_history (user_id, game_type, bet_amount, currency, result, won_amount)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, game_type, bet_amount, currency, result, won_amount))
    conn.commit()
    conn.close()
    backup_database()

def update_user_stats(user_id, result):
    conn = get_db()
    c = conn.cursor()
    if result == "win":
        c.execute('UPDATE users SET total_games = total_games + 1, total_wins = total_wins + 1 WHERE user_id = ?', (user_id,))
    elif result == "loss":
        c.execute('UPDATE users SET total_games = total_games + 1, total_losses = total_losses + 1 WHERE user_id = ?', (user_id,))
    else:
        c.execute('UPDATE users SET total_games = total_games + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    backup_database()

def create_challenge(challenger_id, challenged_id, bet_amount, game_type, rolls, win_condition):
    challenge_id = f"ch_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO challenges (challenge_id, challenger_id, challenged_id, bet_amount, game_type, rolls, win_condition, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    ''', (challenge_id, challenger_id, challenged_id, bet_amount, game_type, rolls, win_condition))
    conn.commit()
    conn.close()
    
    return challenge_id

def get_challenge(challenge_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM challenges WHERE challenge_id = ?', (challenge_id,))
    challenge = c.fetchone()
    conn.close()
    
    if challenge:
        return {
            'challenge_id': challenge[0],
            'challenger_id': challenge[1],
            'challenged_id': challenge[2],
            'bet_amount': challenge[3],
            'game_type': challenge[4],
            'rolls': challenge[5],
            'win_condition': challenge[6],
            'status': challenge[7],
            'challenger_name': challenge[8] or f"Player{challenge[1]}",
            'challenged_name': challenge[9] or f"Player{challenge[2]}",
            'created_at': challenge[10]
        }
    return None

def update_challenge_status(challenge_id, status):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE challenges SET status = ? WHERE challenge_id = ?', (status, challenge_id))
    conn.commit()
    conn.close()

def delete_challenge(challenge_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM challenges WHERE challenge_id = ?', (challenge_id,))
    conn.commit()
    conn.close()

def create_active_game(challenge_id, player1_id, player2_id, bet_amount, game_type, rolls, win_condition):
    game_id = f"game_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO active_games (
            game_id, challenge_id, player1_id, player2_id, bet_amount, game_type, 
            rolls, win_condition, current_turn, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
    ''', (game_id, challenge_id, player1_id, player2_id, bet_amount, game_type, 
          rolls, win_condition, player1_id))
    conn.commit()
    conn.close()
    
    return game_id

def get_user_active_game(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT * FROM active_games 
        WHERE (player1_id = ? OR player2_id = ?) AND status = 'active'
    ''', (user_id, user_id))
    game = c.fetchone()
    conn.close()
    
    if game:
        return {
            'game_id': game[0],
            'challenge_id': game[1],
            'player1_id': game[2],
            'player2_id': game[3],
            'bet_amount': game[4],
            'game_type': game[5],
            'rolls': game[6],
            'win_condition': game[7],
            'current_turn': game[8],
            'player1_rolls': game[9] if game[9] else '[]',
            'player2_rolls': game[10] if game[10] else '[]',
            'player1_wins': game[11] or 0,
            'player2_wins': game[12] or 0,
            'current_round': game[13] or 1,
            'status': game[14] or 'active',
            'created_at': game[15]
        }
    return None

def get_rolls_list(rolls_str):
    if rolls_str and rolls_str != '[]':
        try:
            return eval(rolls_str)
        except:
            return []
    return []

def update_game_rolls(game_id, player1_rolls, player2_rolls):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        UPDATE active_games SET 
            player1_rolls = ?, player2_rolls = ?
        WHERE game_id = ?
    ''', (str(player1_rolls), str(player2_rolls), game_id))
    conn.commit()
    conn.close()

def update_game_turn(game_id, current_turn):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE active_games SET current_turn = ? WHERE game_id = ?', (current_turn, game_id))
    conn.commit()
    conn.close()

def update_game_status_and_wins(game_id, status, player1_wins, player2_wins):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        UPDATE active_games SET 
            status = ?, player1_wins = ?, player2_wins = ?
        WHERE game_id = ?
    ''', (status, player1_wins, player2_wins, game_id))
    conn.commit()
    conn.close()

def update_game_round(game_id, current_round):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE active_games SET current_round = ? WHERE game_id = ?', (current_round, game_id))
    conn.commit()
    conn.close()

def delete_active_game(game_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM active_games WHERE game_id = ?', (game_id,))
    conn.commit()
    conn.close()

def delete_user_games(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM active_games WHERE player1_id = ? OR player2_id = ?', (user_id, user_id))
    c.execute('DELETE FROM challenges WHERE challenger_id = ? OR challenged_id = ?', (user_id, user_id))
    conn.commit()
    conn.close()

def add_bank_request(user_id, req_type, amount, utr='', time_frame=''):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO bank_requests (user_id, type, amount, utr, time_frame, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    ''', (user_id, req_type, amount, utr, time_frame))
    conn.commit()
    request_id = c.lastrowid
    conn.close()
    return request_id

def get_bank_request(req_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM bank_requests WHERE id = ?', (req_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0],
            'user_id': row[1],
            'type': row[2],
            'amount': row[3],
            'utr': row[4],
            'time_frame': row[5],
            'status': row[6],
            'created_at': row[7]
        }
    return None

def update_bank_request_status(req_id, status):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE bank_requests SET status = ? WHERE id = ?', (status, req_id))
    conn.commit()
    conn.close()
    backup_database()

def log_admin_action(admin_id, action, target_user, amount, description):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO admin_logs (admin_id, action, target_user, amount, description)
        VALUES (?, ?, ?, ?, ?)
    ''', (admin_id, action, target_user, amount, description))
    conn.commit()
    conn.close()

def get_top_players(limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT user_id, username, total_games, total_wins, total_losses, balance
        FROM users 
        WHERE total_games > 0
        ORDER BY total_wins DESC, total_games DESC
        LIMIT ?
    ''', (limit,))
    players = c.fetchall()
    conn.close()
    return players

# ============ UTILITY FUNCTIONS ============

def get_symbol(currency):
    return '₹' if currency == 'INR' else '$'

def is_valid_upi(upi):
    if not upi or '@' not in upi:
        return False
    parts = upi.split('@')
    return len(parts) == 2 and len(parts[0]) >= 3 and len(parts[1]) >= 2

def parse_game_command(text, game_type):
    text = text.replace(f'/{game_type}', '').strip()
    
    mention_pattern = r'^@(\w+)'
    mention_match = re.match(mention_pattern, text)
    
    if mention_match:
        username = mention_match.group(1)
        remaining = text.replace(f'@{username}', '').strip()
        parts = remaining.split()
        if len(parts) >= 2:
            try:
                amount = int(parts[0])
                rounds = parts[1]
                if rounds not in ['1d1w', '1d2w', '2d1w', '2d2w', '3d1w', '3d2w']:
                    return None
                return {'type': 'mention', 'username': username, 'amount': amount, 'rounds': rounds}
            except:
                return None
    else:
        parts = text.split()
        if len(parts) >= 2:
            try:
                amount = int(parts[0])
                rounds = parts[1]
                if rounds not in ['1d1w', '1d2w', '2d1w', '2d2w', '3d1w', '3d2w']:
                    return None
                return {'type': 'reply', 'amount': amount, 'rounds': rounds}
            except:
                return None
    return None

def parse_rounds(rounds_str):
    match = re.match(r'(\d+)d(\d+)w', rounds_str)
    if match:
        rolls = int(match.group(1))
        wins_needed = int(match.group(2))
        return {'rolls': rolls, 'win_condition': f'{wins_needed}w'}
    return None

def format_rolls_display(rolls, game_type='dice'):
    if game_type == 'dice':
        return ' '.join([f"{DICE_EMOJIS.get(r, '🎲')}" for r in rolls])
    elif game_type == 'dart':
        return ' '.join([f"🎯" for _ in rolls])
    elif game_type == 'bowling':
        return ' '.join([f"🎳" if r == 10 else f"🎳" for r in rolls])
    elif game_type == 'basketball':
        return ' '.join([f"🏀" for _ in rolls])
    elif game_type == 'football':
        return ' '.join([f"⚽" for _ in rolls])
    return ' '.join([str(r) for r in rolls])

def get_player_name(user_id):
    profile = get_user_profile(user_id)
    if profile:
        return f"@{profile['username']}" if profile['username'] else profile['first_name']
    return f"Player{user_id}"

def get_formatted_balance(user_id):
    profile = get_user_profile(user_id)
    if profile:
        symbol = get_symbol(profile['currency'])
        return f"{symbol}{profile['balance']/100:.2f}"
    return "₹0.00"

def calculate_withdrawal_charge(amount, time_frame):
    if time_frame == "10_12_min":
        factor = amount / 100.0
        charge = round(factor * 8)
    elif time_frame == "30_min":
        factor = amount / 100.0
        charge = round(factor * 5)
    elif time_frame == "1_hour":
        factor = amount / 100.0
        charge = round(factor * 3)
    else:
        charge = 0
    return charge

# ============ GENERIC GAME COMMAND HANDLER ============

async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    try:
        user = update.effective_user
        delete_user_games(user.id)
        
        parsed = parse_game_command(update.message.text, game_type)
        if not parsed:
            emoji = get_game_emoji(game_type)
            await update.message.reply_text(
                f"{emoji} Invalid format!\n\n"
                f"Usage:\n"
                f"• Reply: /{game_type} 500 1d1w\n"
                f"• Mention: /{game_type} @username 500 3d2w\n\n"
                f"Formats: 1d1w, 1d2w, 2d1w, 2d2w, 3d1w, 3d2w"
            )
            return
        
        challenger_profile = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
        if not challenger_profile:
            await update.message.reply_text("❌ Use /start first!")
            return
        
        bet_amount = parsed['amount']
        bet_paise = bet_amount * 100
        symbol = get_symbol(challenger_profile['currency'])
        
        if challenger_profile['balance'] < bet_paise:
            await update.message.reply_text(f"❌ Insufficient balance! Need {symbol}{bet_amount}")
            return
        
        rounds_str = parsed['rounds']
        rounds_info = parse_rounds(rounds_str)
        if not rounds_info:
            await update.message.reply_text("❌ Invalid format! Use: 1d1w, 1d2w, 2d1w, 2d2w, 3d1w, 3d2w")
            return
        
        rolls = rounds_info['rolls']
        win_condition = rounds_info['win_condition']
        
        if parsed['type'] == 'reply':
            if not update.message.reply_to_message:
                await update.message.reply_text("❌ Reply to a user's message!")
                return
            
            challenged_user = update.message.reply_to_message.from_user
            if challenged_user.id == user.id:
                await update.message.reply_text("❌ You cannot challenge yourself!")
                return
            
            challenged_id = challenged_user.id
            challenged_name = f"@{challenged_user.username}" if challenged_user.username else challenged_user.first_name
            
        else:
            username = parsed['username']
            try:
                challenged_user = await context.bot.get_user_by_username(username)
            except:
                await update.message.reply_text(f"❌ User @{username} not found!")
                return
            
            if challenged_user.id == user.id:
                await update.message.reply_text("❌ You cannot challenge yourself!")
                return
            
            challenged_id = challenged_user.id
            challenged_name = f"@{challenged_user.username}" if challenged_user.username else challenged_user.first_name
        
        delete_user_games(challenged_id)
        
        challenged_profile = get_or_create_user(challenged_id, challenged_user.username, challenged_user.first_name)
        if not challenged_profile:
            await update.message.reply_text("❌ Challenged user not found in database!")
            return
        
        if challenged_profile['balance'] < bet_paise:
            await update.message.reply_text(f"❌ {challenged_name} has insufficient balance!")
            return
        
        challenge_id = create_challenge(
            user.id, challenged_id, bet_amount, game_type, 
            rolls, win_condition
        )
        
        challenger_name = f"@{user.username}" if user.username else user.first_name
        
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE challenges SET challenger_name = ?, challenged_name = ? WHERE challenge_id = ?',
                  (challenger_name, challenged_name, challenge_id))
        conn.commit()
        conn.close()
        
        update_wallet(user.id, -bet_paise)
        
        emoji = get_game_emoji(game_type)
        game_name = get_game_name(game_type)
        
        challenge_text = f"""
{emoji} **{game_name} CHALLENGE!**

👤 **Challenger:** {challenger_name}
👤 **Opponent:** {challenged_name}
💰 **Bet:** {symbol}{bet_amount}
🎯 **Game:** {rolls}d{win_condition[0]}w

⏳ {challenged_name}, you have 60 seconds!
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"accept_{challenge_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{challenge_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(challenge_text, reply_markup=reply_markup)
        
        try:
            await context.bot.send_message(
                chat_id=challenged_id,
                text=f"""
{emoji} **New {game_name} Challenge!**
👤 {challenger_name}
💰 {symbol}{bet_amount}
🎯 {rolls}d{win_condition[0]}w

Accept or reject:
                """,
                reply_markup=reply_markup
            )
        except:
            pass
        
        asyncio.create_task(auto_reject_challenge(context, challenge_id, user.id, bet_paise, update.message.chat.id))
        
    except Exception as e:
        logger.error(f"Error in {game_type}: {e}")
        await update.message.reply_text("❌ Something went wrong. Please try again.")

# ============ SPECIFIC GAME COMMANDS ============

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await game_command(update, context, 'dice')

async def dart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await game_command(update, context, 'dart')

async def bowling_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await game_command(update, context, 'bowling')

async def basketball_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await game_command(update, context, 'basketball')

async def football_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await game_command(update, context, 'football')

async def auto_reject_challenge(context, challenge_id, challenger_id, bet_paise, chat_id):
    await asyncio.sleep(60)
    challenge = get_challenge(challenge_id)
    if challenge and challenge['status'] == 'pending':
        update_challenge_status(challenge_id, 'expired')
        update_wallet(challenger_id, bet_paise)
        delete_challenge(challenge_id)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ Challenge expired! Money refunded."
            )
        except:
            pass

# ============ DICE DETECTION ============

async def handle_dice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        message = update.message
        
        if not message.dice:
            return
        
        game = get_user_active_game(user.id)
        
        if not game:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT * FROM challenges WHERE (challenger_id = ? OR challenged_id = ?) AND status = "accepted"', (user.id, user.id))
            challenge = c.fetchone()
            conn.close()
            
            if not challenge:
                return
            
            challenge_data = get_challenge(challenge[0])
            if not challenge_data:
                return
            
            create_active_game(
                challenge_data['challenge_id'],
                challenge_data['challenger_id'],
                challenge_data['challenged_id'],
                challenge_data['bet_amount'],
                challenge_data['game_type'],
                challenge_data['rolls'],
                challenge_data['win_condition']
            )
            
            update_challenge_status(challenge_data['challenge_id'], 'playing')
            delete_challenge(challenge_data['challenge_id'])
            game = get_user_active_game(user.id)
            if not game:
                return
        
        if game['status'] != 'active':
            return
        
        dice_value = message.dice.value
        if dice_value == 0:
            return
        
        if game['current_turn'] != user.id:
            current_name = get_player_name(game['current_turn'])
            await message.reply_text(f"❌ Not your turn! Wait for {current_name} to roll.")
            return
        
        p1 = get_user_profile(game['player1_id'])
        p2 = get_user_profile(game['player2_id'])
        player1_name = f"@{p1['username']}" if p1 else f"Player{game['player1_id']}"
        player2_name = f"@{p2['username']}" if p2 else f"Player{game['player2_id']}"
        
        rolls_per_round = game['rolls']
        wins_needed = int(game['win_condition'][0])
        current_round = game['current_round']
        
        player1_rolls = get_rolls_list(game['player1_rolls'])
        player2_rolls = get_rolls_list(game['player2_rolls'])
        game_type = game['game_type']
        
        emoji = get_game_emoji(game_type)
        
        if user.id == game['player1_id']:
            player1_rolls.append(dice_value)
            update_game_rolls(game['game_id'], player1_rolls, player2_rolls)
            
            expected_p1_rolls = current_round * rolls_per_round
            if len(player1_rolls) >= expected_p1_rolls:
                update_game_turn(game['game_id'], game['player2_id'])
                round_rolls = player1_rolls[-rolls_per_round:]
                await message.reply_text(
                    f"{emoji} {player1_name} completed Round {current_round}!\n\n"
                    f"📊 {game_type.capitalize()} Results: {format_rolls_display(round_rolls, game_type)}\n"
                    f"📈 Total: **{sum(round_rolls)}**\n\n"
                    f"🔄 Now {player2_name}'s turn for Round {current_round}!"
                )
            else:
                rolls_left = expected_p1_rolls - len(player1_rolls)
                await message.reply_text(
                    f"{emoji} {player1_name} threw: **{dice_value}**\n\n"
                    f"📊 Round {game_type.capitalize()}s: {format_rolls_display(player1_rolls[-(rolls_per_round - rolls_left):], game_type)}\n"
                    f"📈 Total: **{sum(player1_rolls[-rolls_per_round:])}**\n"
                    f"⚡ {rolls_left} {'throws' if game_type == 'dart' else 'rolls' if game_type == 'dice' else 'turns'} left\n"
                    f"🔄 Throw again!"
                )
                
        elif user.id == game['player2_id']:
            player2_rolls.append(dice_value)
            update_game_rolls(game['game_id'], player1_rolls, player2_rolls)
            
            expected_p2_rolls = current_round * rolls_per_round
            if len(player2_rolls) >= expected_p2_rolls:
                p1_round_rolls = player1_rolls[-rolls_per_round:]
                p2_round_rolls = player2_rolls[-rolls_per_round:]
                p1_round_total = sum(p1_round_rolls)
                p2_round_total = sum(p2_round_rolls)
                
                p1_wins = game['player1_wins']
                p2_wins = game['player2_wins']
                
                if p1_round_total > p2_round_total:
                    p1_wins += 1
                    round_text = f"🎉 {player1_name} wins Round {current_round}!"
                elif p2_round_total > p1_round_total:
                    p2_wins += 1
                    round_text = f"🎉 {player2_name} wins Round {current_round}!"
                else:
                    round_text = f"🤝 Round {current_round} is a Draw!"
                
                await message.reply_text(
                    f"🏆 **ROUND {current_round} COMPLETE!**\n\n"
                    f"📊 {player1_name}: {format_rolls_display(p1_round_rolls, game_type)} = **{p1_round_total}**\n"
                    f"📊 {player2_name}: {format_rolls_display(p2_round_rolls, game_type)} = **{p2_round_total}**\n\n"
                    f"{round_text}\n\n"
                    f"📊 **Match Score:** {player1_name} {p1_wins} - {p2_wins} {player2_name}"
                )
                
                if p1_wins >= wins_needed or p2_wins >= wins_needed:
                    update_game_status_and_wins(game['game_id'], 'completed', p1_wins, p2_wins)
                    
                    if p1_wins > p2_wins:
                        winner_id = game['player1_id']
                        winner_name = player1_name
                        loser_id = game['player2_id']
                        win_amount = game['bet_amount'] * 2
                        update_wallet(winner_id, win_amount * 100)
                        update_user_stats(winner_id, 'win')
                        update_user_stats(loser_id, 'loss')
                        save_game_history(winner_id, game_type, game['bet_amount'], 'INR', 'win', win_amount)
                        save_game_history(loser_id, game_type, game['bet_amount'], 'INR', 'loss', 0)
                        
                        result_text = f"""
{get_brand_header()}

📊 Final Results:

{emoji} {player1_name} wins {p1_wins} rounds
{emoji} {player2_name} wins {p2_wins} rounds

🎉 **{winner_name.upper()} WINS THE MATCH!** 🎉

💰 Each Bet: ₹{game['bet_amount']}
💰 Total Pot: ₹{game['bet_amount'] * 2}
🏆 Winner Gets: ₹{win_amount}

💰 Winner Balance: {get_formatted_balance(winner_id)}

📌 Play again with /{game_type}
"""
                    else:
                        winner_id = game['player2_id']
                        winner_name = player2_name
                        loser_id = game['player1_id']
                        win_amount = game['bet_amount'] * 2
                        update_wallet(winner_id, win_amount * 100)
                        update_user_stats(winner_id, 'win')
                        update_user_stats(loser_id, 'loss')
                        save_game_history(winner_id, game_type, game['bet_amount'], 'INR', 'win', win_amount)
                        save_game_history(loser_id, game_type, game['bet_amount'], 'INR', 'loss', 0)
                        
                        result_text = f"""
{get_brand_header()}

📊 Final Results:

{emoji} {player1_name} wins {p1_wins} rounds
{emoji} {player2_name} wins {p2_wins} rounds

🎉 **{winner_name.upper()} WINS THE MATCH!** 🎉

💰 Each Bet: ₹{game['bet_amount']}
💰 Total Pot: ₹{game['bet_amount'] * 2}
🏆 Winner Gets: ₹{win_amount}

💰 Winner Balance: {get_formatted_balance(winner_id)}

📌 Play again with /{game_type}
"""
                    await message.reply_text(result_text)
                    delete_active_game(game['game_id'])
                    return
                
                if wins_needed == 2 and current_round >= 2:
                    update_game_status_and_wins(game['game_id'], 'completed', p1_wins, p2_wins)
                    
                    if p1_wins > p2_wins:
                        winner_id = game['player1_id']
                        winner_name = player1_name
                        loser_id = game['player2_id']
                        win_amount = game['bet_amount'] * 2
                        update_wallet(winner_id, win_amount * 100)
                        update_user_stats(winner_id, 'win')
                        update_user_stats(loser_id, 'loss')
                        save_game_history(winner_id, game_type, game['bet_amount'], 'INR', 'win', win_amount)
                        save_game_history(loser_id, game_type, game['bet_amount'], 'INR', 'loss', 0)
                        result_text = f"🎉 {winner_name} wins by point lead! Pot: ₹{win_amount}"
                    elif p2_wins > p1_wins:
                        winner_id = game['player2_id']
                        winner_name = player2_name
                        loser_id = game['player1_id']
                        win_amount = game['bet_amount'] * 2
                        update_wallet(winner_id, win_amount * 100)
                        update_user_stats(winner_id, 'win')
                        update_user_stats(loser_id, 'loss')
                        save_game_history(winner_id, game_type, game['bet_amount'], 'INR', 'win', win_amount)
                        save_game_history(loser_id, game_type, game['bet_amount'], 'INR', 'loss', 0)
                        result_text = f"🎉 {winner_name} wins by point lead! Pot: ₹{win_amount}"
                    else:
                        update_wallet(game['player1_id'], game['bet_amount'] * 100)
                        update_wallet(game['player2_id'], game['bet_amount'] * 100)
                        update_user_stats(game['player1_id'], 'draw')
                        update_user_stats(game['player2_id'], 'draw')
                        result_text = "🤝 Match ended in a Draw! Bets refunded."
                        
                    await message.reply_text(result_text)
                    delete_active_game(game['game_id'])
                    return
                
                current_round += 1
                update_game_status_and_wins(game['game_id'], 'active', p1_wins, p2_wins)
                update_game_round(game['game_id'], current_round)
                update_game_turn(game['game_id'], game['player1_id'])
                
                await message.reply_text(
                    f"🔄 **ROUND {current_round} STARTING!**\n\n"
                    f"📊 Score: {player1_name} {p1_wins} - {p2_wins} {player2_name}\n\n"
                    f"🔄 {player1_name}'s turn! Throw again."
                )
            else:
                rolls_left = expected_p2_rolls - len(player2_rolls)
                await message.reply_text(
                    f"{emoji} {player2_name} threw: **{dice_value}**\n\n"
                    f"📊 Round {game_type.capitalize()}s: {format_rolls_display(player2_rolls[-(rolls_per_round - rolls_left):], game_type)}\n"
                    f"📈 Total: **{sum(player2_rolls[-rolls_per_round:])}**\n"
                    f"⚡ {rolls_left} {'throws' if game_type == 'dart' else 'rolls' if game_type == 'dice' else 'turns'} left\n"
                    f"🔄 Throw again!"
                )
        
    except Exception as e:
        logger.error(f"Error handling dice: {e}")

# ============ WALLET & BANKING MODULES ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        profile = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
        
        if not profile:
            await update.message.reply_text("❌ Error loading profile.")
            return
        
        if not profile['currency']:
            keyboard = [
                [InlineKeyboardButton("🇮🇳 INR (₹)", callback_data="set_currency_INR")],
                [InlineKeyboardButton("🇺🇸 USD ($)", callback_data="set_currency_USD")]
            ]
            await update.message.reply_text("🌍 Select your currency:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        text = f"""
{get_brand_header()}
🎮 Welcome to Casino Blaze!

💳 Account:
• /wallet - Open wallet
• /setupi - Set UPI
• /deposit - Deposit
• /withdraw - Withdraw
• /balance or /bal - Check balance

🎲 Games:
• /dice - Play Dice game
• /dart - Play Dart game  
• /bowling - Play Bowling game
• /basketball - Play Basketball game
• /football - Play Football game

🏆 Leaderboard:
• /leaderboard - Top players

💝 Tip:
• Reply: /tip 50
• Mention: /tip @username 50
"""
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Error in start: {e}")

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        profile = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
        
        if not profile:
            await update.message.reply_text("❌ Error loading profile.")
            return
        
        currency = profile['currency']
        symbol = get_symbol(currency)
        balance = profile['balance'] / 100
        upi = profile['upi_address'] or "Not Set"
        
        text = f"""
{get_brand_header()}
Casino Blaze
User Wallet Profile & Forms

Username: @{profile['username']}
Available Balance: {symbol}{balance:.2f}
Linked UPI Address: {upi}

Select a form action button below:
{datetime.now().strftime('%I:%M %p')}
        """
        
        keyboard = [
            [InlineKeyboardButton("📜 View Game History", callback_data="view_history")],
            [InlineKeyboardButton("⚙️ Setup/Change UPI", callback_data="setup_upi")],
            [InlineKeyboardButton("💳 Deposit Form", callback_data="deposit_form")],
            [InlineKeyboardButton("📤 Withdraw Form", callback_data="withdraw_form")]
        ]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error in wallet: {e}")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        profile = get_user_profile(user.id)
        
        if not profile:
            await update.message.reply_text("❌ Profile not found! Use /start first.")
            return
        
        currency = profile['currency']
        symbol = get_symbol(currency)
        balance = profile['balance'] / 100
        upi = profile['upi_address'] or "Not Set"
        
        text = f"""
💰 **Your Balance**

👤 @{profile['username']}
💳 **Currency:** {currency}
💰 **Balance:** {symbol}{balance:.2f}
📱 **UPI:** {upi}

📌 Use /deposit to add funds
📌 Use /withdraw to cash out
"""
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Error in balance: {e}")

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        players = get_top_players(10)
        
        if not players:
            await update.message.reply_text("📊 No players found. Start playing to appear on the leaderboard!")
            return
        
        text = "🏆 **CASINO BLAZE TOP 10 PLAYERS** 🏆\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for idx, player in enumerate(players):
            user_id, username, total_games, total_wins, total_losses, balance = player
            
            if total_games > 0:
                win_rate = (total_wins / total_games) * 100
            else:
                win_rate = 0
            
            display_name = f"@{username}" if username else f"User{user_id}"
            balance_rs = balance / 100
            
            medal = medals[idx] if idx < len(medals) else f"{idx+1}️⃣"
            
            text += f"{medal} {display_name}\n"
            text += f" └ 🎮 Bets: {total_games} | ✅ Won: {total_wins} | ❌ Lost: {total_losses}\n"
            text += f" └ 🔥 Win Rate: {win_rate:.1f}% | 💰 Bal: ₹{balance_rs:.2f}\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "⚡ Challenge others to climb up the ranking grid!"
        
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Error in leaderboard: {e}")
        await update.message.reply_text("❌ Error loading leaderboard. Please try again.")

async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        
        if update.message.reply_to_message:
            if not context.args or len(context.args) < 1:
                await update.message.reply_text("❌ Reply with /tip amount")
                return
            try:
                amount = int(context.args[0])
            except ValueError:
                await update.message.reply_text("❌ Invalid amount!")
                return
            
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be greater than 0!")
                return
            
            recipient_user = update.message.reply_to_message.from_user
            if recipient_user.id == user.id:
                await update.message.reply_text("❌ You cannot tip yourself!")
                return
            recipient_id = recipient_user.id
        else:
            if len(context.args) < 2:
                await update.message.reply_text("❌ Usage: /tip @username amount or reply with /tip amount")
                return
            
            username = context.args[0]
            if not username.startswith('@'):
                await update.message.reply_text("❌ Please mention the user with @username")
                return
            username = username[1:]
            
            try:
                amount = int(context.args[1])
            except (IndexError, ValueError):
                await update.message.reply_text("❌ Invalid amount!")
                return
            
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be greater than 0!")
                return
            
            try:
                recipient_user = await context.bot.get_user_by_username(username)
                recipient_id = recipient_user.id
            except:
                await update.message.reply_text(f"❌ User @{username} not found!")
                return
            
            if recipient_id == user.id:
                await update.message.reply_text("❌ You cannot tip yourself!")
                return
        
        sender_profile = get_user_profile(user.id)
        if not sender_profile:
            await update.message.reply_text("❌ Use /start first!")
            return
        
        recipient_profile = get_user_profile(recipient_id)
        if not recipient_profile:
            await update.message.reply_text("❌ Recipient not found! Ask them to use /start.")
            return
        
        amount_paise = amount * 100
        if sender_profile['balance'] < amount_paise:
            symbol = get_symbol(sender_profile['currency'])
            await update.message.reply_text(f"❌ Insufficient balance! You have {symbol}{sender_profile['balance']/100:.2f}")
            return
        
        update_wallet(user.id, -amount_paise)
        update_wallet(recipient_id, amount_paise)
        
        symbol = get_symbol(sender_profile['currency'])
        recipient_name = f"@{recipient_profile['username']}" if recipient_profile['username'] else recipient_profile['first_name']
        sender_name = f"@{sender_profile['username']}" if sender_profile['username'] else sender_profile['first_name']
        
        sender_new = get_user_profile(user.id)['balance'] / 100
        recipient_new = get_user_profile(recipient_id)['balance'] / 100
        
        await update.message.reply_text(
            f"💝 **TIP SENT!**\n\n"
            f"👤 {sender_name} → 👤 {recipient_name}\n"
            f"💰 Amount: {symbol}{amount}\n\n"
            f"📊 **Updated Balances:**\n"
            f"👤 {sender_name}: {symbol}{sender_new:.2f}\n"
            f"👤 {recipient_name}: {symbol}{recipient_new:.2f}"
        )
        try:
            await context.bot.send_message(chat_id=recipient_id, text=f"💝 You received {symbol}{amount} from {sender_name}!")
        except:
            pass
    except Exception as e:
        logger.error(f"Error in tip: {e}")
        await update.message.reply_text("❌ Something went wrong. Please try again.")

async def setupi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if context.args:
            upi = context.args[0]
            if not is_valid_upi(upi):
                await update.message.reply_text("❌ Invalid UPI! Use: /setupi address@upi")
                return
            set_upi_address(user.id, upi)
            await update.message.reply_text(f"✅ UPI Address Updated!\n\n📱 New UPI: `{upi}`")
            return
        await update.message.reply_text("⚙️ Type: /setupi value@upi\nExample: /setupi example@paytm")
    except Exception as e:
        logger.error(f"Error in setupi: {e}")

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if update.message.chat.type != 'private':
            await update.message.reply_text("❌ Open bot in private DM for banking forms!")
            return
        
        text = f"""
{get_brand_header()}
Casino Blaze
💰 DEPOSIT FORM

Select deposit amount:
(Minimum Deposit is ₹{MIN_DEPOSIT})
        """
        keyboard = []
        amounts = [40, 100, 200, 500, 1000, 2000, 5000]
        for amt in amounts:
            keyboard.append([InlineKeyboardButton(f"₹{amt}", callback_data=f"deposit_{amt}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Wallet", callback_data="wallet_menu")])
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error in deposit: {e}")

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        if update.message.chat.type != 'private':
            await update.message.reply_text("❌ Open bot in private DM for banking forms!")
            return
        
        profile = get_user_profile(user.id)
        if not profile:
            await update.message.reply_text("❌ Profile not found!")
            return
        
        currency = profile['currency']
        symbol = get_symbol(currency)
        balance = profile['balance'] / 100
        upi = profile['upi_address']
        
        if not upi:
            await update.message.reply_text("❌ No UPI set! Use /setupi your-id@upi")
            return
        
        if balance < MIN_WITHDRAW:
            await update.message.reply_text(f"❌ Minimum withdrawal is ₹{MIN_WITHDRAW}! Your balance: {symbol}{balance:.2f}")
            return
        
        text = f"""
{get_brand_header()}
Casino Blaze
📤 WITHDRAW FORM

💰 Balance: {symbol}{balance:.2f}
📱 UPI: `{upi}`

Select amount to withdraw:
        """
        keyboard = []
        amounts = [60, 100, 200, 500, 1000, 2000, 5000]
        for amt in amounts:
            if amt <= balance:
                keyboard.append([InlineKeyboardButton(f"₹{amt}", callback_data=f"withdraw_select_{amt}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Wallet", callback_data="wallet_menu")])
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error in withdraw: {e}")


# ============ UPGRADED INTERACTIVE ADMIN PORTAL ============

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_USER_ID or update.message.chat.type != 'private':
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bank_requests WHERE type='deposit' AND status='pending'")
    dep_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM bank_requests WHERE type='withdraw' AND status='pending'")
    wd_count = c.fetchone()[0]
    conn.close()

    admin_text = f"""
👑 **CASINO BLAZE CONTROL PANEL**

👋 Welcome Admin @XTOP_879! 
Use the console buttons below to manage the casino.

📊 **Pending Traffic Summary:**
📥 Deposits Pending: **{dep_count}**
📤 Withdrawals Pending: **{wd_count}**
    """
    
    keyboard = [
        [
            InlineKeyboardButton(f"📥 View Deposits ({dep_count})", callback_data="adm_view_deposits"),
            InlineKeyboardButton(f"📤 View Withdraws ({wd_count})", callback_data="adm_view_withdraws")
        ],
        [InlineKeyboardButton("🔄 Refresh Statistics", callback_data="adm_refresh_stats")],
        [InlineKeyboardButton("👤 Manage Player Balance", callback_data="adm_manage_balance")]
    ]
    await update.message.reply_text(admin_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def add_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_USER_ID or update.message.chat.type != 'private':
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addbalance <user_id> <amount>")
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        update_wallet(target_id, amount * 100)
        log_admin_action(user.id, "add_balance", target_id, amount, f"Added ₹{amount}")
        await update.message.reply_text(f"✅ Added ₹{amount} to player balance (ID: {target_id})")
        try:
            await context.bot.send_message(chat_id=target_id, text=f"💰 Admin credited ₹{amount} to your wallet.")
        except:
            pass
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def remove_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_USER_ID or update.message.chat.type != 'private':
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /removebalance <user_id> <amount>")
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        update_wallet(target_id, -amount * 100)
        log_admin_action(user.id, "remove_balance", target_id, amount, f"Deducted ₹{amount}")
        await update.message.reply_text(f"✅ Deducted ₹{amount} from player balance (ID: {target_id})")
        try:
            await context.bot.send_message(chat_id=target_id, text=f"⚠️ Admin deducted ₹{amount} from your wallet.")
        except:
            pass
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def set_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_USER_ID or update.message.chat.type != 'private':
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setbalance <user_id> <amount>")
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        profile = get_user_profile(target_id)
        if not profile:
            await update.message.reply_text("❌ User not found!")
            return
        current_balance = profile['balance']
        update_wallet(target_id, (amount * 100) - current_balance)
        log_admin_action(user.id, "set_balance", target_id, amount, f"Set balance to ₹{amount}")
        await update.message.reply_text(f"✅ Set balance of player (ID: {target_id}) to ₹{amount}")
        try:
            await context.bot.send_message(chat_id=target_id, text=f"💰 Admin updated your balance to ₹{amount}")
        except:
            pass
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_USER_ID or update.message.chat.type != 'private':
        return
    if not context.args:
        await update.message.reply_text("Usage: /approve <request_id>")
        return
    try:
        req_id = int(context.args[0])
        req = get_bank_request(req_id)
        if not req or req['status'] != 'pending':
            await update.message.reply_text("Request not found or resolved already.")
            return
            
        update_bank_request_status(req_id, 'approved')
        target_user_id = req['user_id']
        
        if req['type'] == 'deposit':
            update_wallet(target_user_id, req['amount'] * 100)
            conn = get_db()
            c = conn.cursor()
            c.execute('UPDATE users SET total_deposited = total_deposited + ? WHERE user_id = ?', (req['amount'] * 100, target_user_id))
            conn.commit()
            conn.close()
            log_admin_action(user.id, "approve_deposit", target_user_id, req['amount'], f"Approved deposit ₹{req['amount']}")
            await update.message.reply_text(f"✅ Approved deposit of ₹{req['amount']} for user {target_user_id}")
            try:
                # Send thank you image with approval message (only once)
                try:
                    await context.bot.send_photo(
                        chat_id=target_user_id,
                        photo=open(THANK_YOU_IMAGE, 'rb'),
                        caption=f"🎉 **DEPOSIT APPROVED!**\n\n"
                               f"💰 Amount: ₹{req['amount']}\n"
                               f"📊 New Balance: {get_formatted_balance(target_user_id)}\n\n"
                               f"Thank you for depositing! 🎰\n"
                               f"Good luck and have fun playing! 🍀"
                    )
                except Exception as e:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"🎉 **DEPOSIT APPROVED!**\n\n"
                             f"💰 Amount: ₹{req['amount']}\n"
                             f"📊 New Balance: {get_formatted_balance(target_user_id)}\n\n"
                             f"Thank you for depositing! 🎰\n"
                             f"Good luck and have fun playing! 🍀"
                    )
            except:
                pass
        else:
            conn = get_db()
            c = conn.cursor()
            c.execute('UPDATE users SET total_withdrawn = total_withdrawn + ? WHERE user_id = ?', (req['amount'] * 100, target_user_id))
            conn.commit()
            conn.close()
            log_admin_action(user.id, "approve_withdraw", target_user_id, req['amount'], f"Approved withdrawal ₹{req['amount']}")
            await update.message.reply_text(f"✅ Approved withdrawal of ₹{req['amount']} for user {target_user_id}")
            try:
                await context.bot.send_message(chat_id=target_user_id, text=f"✅ Your withdrawal request of ₹{req['amount']} has been processed successfully!")
            except:
                pass
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_USER_ID or update.message.chat.type != 'private':
        return
    if not context.args:
        await update.message.reply_text("Usage: /reject <request_id>")
        return
    try:
        req_id = int(context.args[0])
        req = get_bank_request(req_id)
        if not req or req['status'] != 'pending':
            await update.message.reply_text("Request not found or resolved already.")
            return
            
        update_bank_request_status(req_id, 'rejected')
        target_user_id = req['user_id']
        
        if req['type'] == 'deposit':
            log_admin_action(user.id, "reject_deposit", target_user_id, req['amount'], f"Rejected deposit ₹{req['amount']}")
            await update.message.reply_text(f"❌ Rejected deposit for user {target_user_id}")
            try:
                await context.bot.send_message(chat_id=target_user_id, text=f"❌ Your deposit request of ₹{req['amount']} was rejected by the admin. Contact support.")
            except:
                pass
        else:
            update_wallet(target_user_id, req['amount'] * 100)
            log_admin_action(user.id, "reject_withdraw", target_user_id, req['amount'], f"Rejected withdrawal ₹{req['amount']}")
            await update.message.reply_text(f"❌ Rejected withdrawal for user {target_user_id}. Refunded to wallet.")
            try:
                await context.bot.send_message(chat_id=target_user_id, text=f"❌ Your withdrawal of ₹{req['amount']} was rejected. Your balance has been refunded.")
            except:
                pass
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# ============ PROOF, UTR & SCREENSHOT HANDLING ============

async def handle_user_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.message.chat.type != 'private':
        return
        
    text = update.message.text
    photo = update.message.photo
    caption = update.message.caption
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, amount FROM bank_requests WHERE user_id = ? AND type = 'deposit' AND status = 'pending' AND utr = '' ORDER BY id DESC LIMIT 1", (user.id,))
    row = c.fetchone()
    conn.close()
    
    # Process UTR Code
    if text and re.match(r'^\d{12}$', text.strip()):
        if not row:
            await update.message.reply_text("❌ No active deposit form found awaiting a UTR code. Please use `/deposit` first.")
            return
            
        req_id, amt = row
        utr = text.strip()
        
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE bank_requests SET utr = ? WHERE id = ?", (utr, req_id))
        conn.commit()
        conn.close()
        
        user_info = f"@{user.username}" if user.username else user.first_name
        
        await update.message.reply_text(
            f"✅ **UTR RECEIVED!**\n\n"
            f"💰 Amount: ₹{amt}\n"
            f"🔢 Reference Code: `{utr}`\n\n"
            f"📸 **Now please upload the payment screenshot** here to complete verification."
        )
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"📥 **Deposit Update [DP-{req_id}]**\n👤 User: {user_info} (ID: {user.id})\n💰 Amount: ₹{amt}\n🔢 UTR: `{utr}`\n*(Awaiting screenshot verification)*"
            )
        except:
            pass
        return

    # Process Screenshot Upload
    if photo:
        file_id = photo[-1].file_id
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, amount, utr FROM bank_requests WHERE user_id = ? AND type = 'deposit' AND status = 'pending' ORDER BY id DESC LIMIT 1", (user.id,))
        dep_row = c.fetchone()
        conn.close()
        
        if not dep_row:
            await update.message.reply_text("❌ No active deposit request was found to map this screenshot to. Please choose `/deposit` first.")
            return
            
        rid, d_amt, d_utr = dep_row
        user_info = f"@{user.username}" if user.username else user.first_name
        
        await update.message.reply_text(
            f"📥 **SCREENSHOT SUBMITTED SUCCESSFULLY!**\n\n"
            f"📁 Your transaction proof has been delivered to the finance department.\n"
            f"⏳ Status: **Pending Admin Verification**\n\n"
            f"Our administrator will review the payment. You will be messaged instantly upon approval!"
        )
        
        try:
            admin_caption = f"""
📥 **Deposit Verification [DP-{rid}]**
👤 User: {user_info} (ID: {user.id})
💰 Amount: ₹{d_amt}
🔢 UTR: `{d_utr or 'Not Provided'}`
"""
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"adm_approve_{rid}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"adm_reject_{rid}")
                ]
            ]
            await context.bot.send_photo(
                chat_id=ADMIN_USER_ID,
                photo=file_id,
                caption=admin_caption,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Failed to forward proof to admin: {e}")
        return

# ============ CALLBACK HANDLERS ============

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        
        if query.from_user.id != user_id:
            await query.answer("🚫 Not your menu!", show_alert=True)
            return
        
        data = query.data
        logger.info(f"Callback received: {data}")
        
        # Admin Specific Callbacks
        if data.startswith("adm_"):
            if user_id != ADMIN_USER_ID:
                await query.answer("🚫 Admin actions only!", show_alert=True)
                return
            
            # View deposit list
            if data == "adm_view_deposits":
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT id, user_id, amount, utr FROM bank_requests WHERE type='deposit' AND status='pending'")
                rows = c.fetchall()
                conn.close()
                
                if not rows:
                    await query.answer("No pending deposits!", show_alert=True)
                    return
                
                text = "📥 **Pending Deposit Queue**\n\n"
                keyboard = []
                for row in rows:
                    rid, uid, amt, utr = row
                    text += f"▪️ **[DP-{rid}]** ID: `{uid}` - **₹{amt}** (UTR: `{utr}`)\n"
                    keyboard.append([
                        InlineKeyboardButton(f"✅ Appr {rid}", callback_data=f"adm_approve_{rid}"),
                        InlineKeyboardButton(f"❌ Rej {rid}", callback_data=f"adm_reject_{rid}")
                    ])
                keyboard.append([InlineKeyboardButton("🔙 Back to Console", callback_data="adm_back_console")])
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                return
                
            # View withdrawal list
            if data == "adm_view_withdraws":
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT id, user_id, amount, time_frame FROM bank_requests WHERE type='withdraw' AND status='pending'")
                rows = c.fetchall()
                conn.close()
                
                if not rows:
                    await query.answer("No pending withdrawals!", show_alert=True)
                    return
                
                text = "📤 **Pending Withdrawal Queue**\n\n"
                keyboard = []
                for row in rows:
                    rid, uid, amt, tf = row
                    text += f"▪️ **[WD-{rid}]** ID: `{uid}` - **₹{amt}** ({tf.replace('_', ' ').title()})\n"
                    keyboard.append([
                        InlineKeyboardButton(f"✅ Appr {rid}", callback_data=f"adm_approve_{rid}"),
                        InlineKeyboardButton(f"❌ Rej {rid}", callback_data=f"adm_reject_{rid}")
                    ])
                keyboard.append([InlineKeyboardButton("🔙 Back to Console", callback_data="adm_back_console")])
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                return
                
            if data == "adm_refresh_stats":
                await query.answer("Refreshing Statistics...")
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM bank_requests WHERE type='deposit' AND status='pending'")
                dep_count = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM bank_requests WHERE type='withdraw' AND status='pending'")
                wd_count = c.fetchone()[0]
                conn.close()
                
                admin_text = f"""
👑 **CASINO BLAZE CONTROL PANEL**

👋 Welcome Admin @XTOP_879! 
Use the console buttons below to view and resolve incoming banking requests.

📊 **Pending Traffic Summary:**
📥 Deposits Pending: **{dep_count}**
📤 Withdrawals Pending: **{wd_count}**
                """
                keyboard = [
                    [
                        InlineKeyboardButton(f"📥 View Deposits ({dep_count})", callback_data="adm_view_deposits"),
                        InlineKeyboardButton(f"📤 View Withdraws ({wd_count})", callback_data="adm_view_withdraws")
                    ],
                    [InlineKeyboardButton("🔄 Refresh Statistics", callback_data="adm_refresh_stats")],
                    [InlineKeyboardButton("👤 Manage Player Balance", callback_data="adm_manage_balance")]
                ]
                await query.edit_message_text(admin_text, reply_markup=InlineKeyboardMarkup(keyboard))
                return
                
            if data == "adm_back_console":
                await query.answer()
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM bank_requests WHERE type='deposit' AND status='pending'")
                dep_count = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM bank_requests WHERE type='withdraw' AND status='pending'")
                wd_count = c.fetchone()[0]
                conn.close()
                
                admin_text = f"""
👑 **CASINO BLAZE CONTROL PANEL**

👋 Welcome Admin @XTOP_879! 
Use the console buttons below to view and resolve incoming banking requests.

📊 **Pending Traffic Summary:**
📥 Deposits Pending: **{dep_count}**
📤 Withdrawals Pending: **{wd_count}**
                """
                keyboard = [
                    [
                        InlineKeyboardButton(f"📥 View Deposits ({dep_count})", callback_data="adm_view_deposits"),
                        InlineKeyboardButton(f"📤 View Withdraws ({wd_count})", callback_data="adm_view_withdraws")
                    ],
                    [InlineKeyboardButton("🔄 Refresh Statistics", callback_data="adm_refresh_stats")],
                    [InlineKeyboardButton("👤 Manage Player Balance", callback_data="adm_manage_balance")]
                ]
                await query.edit_message_text(admin_text, reply_markup=InlineKeyboardMarkup(keyboard))
                return

            if data == "adm_manage_balance":
                text = """
👤 **Manage Player Balance**

Use these commands to manage player balances:

/addbalance <user_id> <amount> - Add balance
/removebalance <user_id> <amount> - Remove balance  
/setbalance <user_id> <amount> - Set exact balance

Example:
/addbalance 123456789 1000
"""
                await query.edit_message_text(text)
                return
                
            # Inline Approval
            if data.startswith("adm_approve_"):
                rid = int(data.replace("adm_approve_", ""))
                req = get_bank_request(rid)
                if not req or req['status'] != 'pending':
                    await query.answer("Resolved or non-existent request!", show_alert=True)
                    return
                
                update_bank_request_status(rid, 'approved')
                target_user_id = req['user_id']
                
                if req['type'] == 'deposit':
                    update_wallet(target_user_id, req['amount'] * 100)
                    conn = get_db()
                    c = conn.cursor()
                    c.execute('UPDATE users SET total_deposited = total_deposited + ? WHERE user_id = ?', (req['amount'] * 100, target_user_id))
                    conn.commit()
                    conn.close()
                    log_admin_action(ADMIN_USER_ID, "approve_deposit", target_user_id, req['amount'], f"Approved deposit ₹{req['amount']}")
                    await query.answer(f"Approved deposit DP-{rid}!", show_alert=True)
                    try:
                        # Send thank you image with approval message (only once)
                        try:
                            await context.bot.send_photo(
                                chat_id=target_user_id,
                                photo=open(THANK_YOU_IMAGE, 'rb'),
                                caption=f"🎉 **DEPOSIT APPROVED!**\n\n"
                                       f"💰 Amount: ₹{req['amount']}\n"
                                       f"📊 New Balance: {get_formatted_balance(target_user_id)}\n\n"
                                       f"Thank you for depositing! 🎰\n"
                                       f"Good luck and have fun playing! 🍀"
                            )
                        except Exception as e:
                            await context.bot.send_message(
                                chat_id=target_user_id,
                                text=f"🎉 **DEPOSIT APPROVED!**\n\n"
                                     f"💰 Amount: ₹{req['amount']}\n"
                                     f"📊 New Balance: {get_formatted_balance(target_user_id)}\n\n"
                                     f"Thank you for depositing! 🎰\n"
                                     f"Good luck and have fun playing! 🍀"
                            )
                    except:
                        pass
                else:
                    conn = get_db()
                    c = conn.cursor()
                    c.execute('UPDATE users SET total_withdrawn = total_withdrawn + ? WHERE user_id = ?', (req['amount'] * 100, target_user_id))
                    conn.commit()
                    conn.close()
                    log_admin_action(ADMIN_USER_ID, "approve_withdraw", target_user_id, req['amount'], f"Approved withdrawal ₹{req['amount']}")
                    await query.answer(f"Approved withdraw WD-{rid}!", show_alert=True)
                    try:
                        await context.bot.send_message(chat_id=target_user_id, text=f"✅ Your withdrawal request of ₹{req['amount']} has been processed successfully!")
                    except:
                        pass
                
                await query.edit_message_text(f"✅ Request #{rid} was successfully approved.")
                return
                
            # Inline Rejection
            if data.startswith("adm_reject_"):
                rid = int(data.replace("adm_reject_", ""))
                req = get_bank_request(rid)
                if not req or req['status'] != 'pending':
                    await query.answer("Resolved or non-existent request!", show_alert=True)
                    return
                
                update_bank_request_status(rid, 'rejected')
                target_user_id = req['user_id']
                
                if req['type'] == 'deposit':
                    log_admin_action(ADMIN_USER_ID, "reject_deposit", target_user_id, req['amount'], f"Rejected deposit ₹{req['amount']}")
                    await query.answer(f"Rejected deposit DP-{rid}", show_alert=True)
                    try:
                        await context.bot.send_message(chat_id=target_user_id, text=f"❌ Your deposit request of ₹{req['amount']} was rejected by the admin. Contact support.")
                    except:
                        pass
                else:
                    update_wallet(target_user_id, req['amount'] * 100)
                    log_admin_action(ADMIN_USER_ID, "reject_withdraw", target_user_id, req['amount'], f"Rejected withdrawal ₹{req['amount']}")
                    await query.answer(f"Rejected withdraw WD-{rid}. Refunded.", show_alert=True)
                    try:
                        await context.bot.send_message(chat_id=target_user_id, text=f"❌ Your withdrawal of ₹{req['amount']} was rejected. Your balance has been refunded.")
                    except:
                        pass
                        
                await query.edit_message_text(f"❌ Request #{rid} was successfully rejected.")
                return

        if data.startswith("accept_"):
            challenge_id = data.replace("accept_", "")
            challenge = get_challenge(challenge_id)
            
            if not challenge:
                await query.answer("❌ Challenge expired!", show_alert=True)
                await query.edit_message_text("❌ Challenge expired or not found!")
                return
            if challenge['status'] != 'pending':
                await query.answer("❌ Challenge already handled!", show_alert=True)
                return
            if challenge['challenged_id'] != user_id:
                await query.answer("🚫 This challenge is not for you!", show_alert=True)
                return
            
            update_challenge_status(challenge_id, 'accepted')
            await query.answer("✅ Challenge accepted!")
            
            challenger_profile = get_user_profile(challenge['challenger_id'])
            challenger_name = f"@{challenger_profile['username']}" if challenger_profile else f"Player{challenge['challenger_id']}"
            challenged_name = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
            
            bet_paise = challenge['bet_amount'] * 100
            update_wallet(challenge['challenged_id'], -bet_paise)
            
            symbol = get_symbol(challenger_profile['currency'] if challenger_profile else 'INR')
            rolls_needed = challenge['rolls']
            wins_needed = challenge['win_condition'][0]
            game_type = challenge['game_type']
            emoji = get_game_emoji(game_type)
            roll_emoji = get_game_roll_emoji(game_type)
            
            delete_user_games(challenge['challenger_id'])
            delete_user_games(challenge['challenged_id'])
            
            create_active_game(
                challenge_id,
                challenge['challenger_id'],
                challenge['challenged_id'],
                challenge['bet_amount'],
                game_type,
                challenge['rolls'],
                challenge['win_condition']
            )
            
            await query.edit_message_text(
                f"""
{emoji} **GAME STARTED!**

👤 {challenger_name} vs 👤 {challenged_name}
💰 **Bet:** {symbol}{challenge['bet_amount']}
🎯 **Game:** {rolls_needed}d{wins_needed}w

🔄 **{challenger_name}'s turn!**

📌 Roll {roll_emoji} from emoji box!
            """
            )
            return
        
        if data.startswith("reject_"):
            challenge_id = data.replace("reject_", "")
            challenge = get_challenge(challenge_id)
            
            if not challenge:
                await query.answer("❌ Challenge expired!", show_alert=True)
                return
            if challenge['status'] != 'pending':
                await query.answer("❌ Challenge already handled!", show_alert=True)
                return
            if challenge['challenged_id'] != user_id:
                await query.answer("🚫 This challenge is not for you!", show_alert=True)
                return
            
            update_challenge_status(challenge_id, 'rejected')
            bet_paise = challenge['bet_amount'] * 100
            update_wallet(challenge['challenger_id'], bet_paise)
            delete_challenge(challenge_id)
            
            await query.answer("❌ Challenge rejected!")
            await query.edit_message_text(
                f"❌ Challenge rejected by {challenge['challenged_name']}!\n\n"
                f"💰 Funds have been refunded."
            )
            return
        
        if data.startswith("set_currency_"):
            currency = data.replace("set_currency_", "")
            conn = get_db()
            c = conn.cursor()
            c.execute('UPDATE users SET currency = ? WHERE user_id = ?', (currency, user_id))
            conn.commit()
            conn.close()
            await query.edit_message_text(f"✅ Currency set to {currency}!")
            await start(update, context)
            return
        
        if data == "wallet_menu":
            profile = get_user_profile(user_id)
            if not profile:
                await query.edit_message_text("❌ Profile not found!")
                return
            
            currency = profile['currency']
            symbol = get_symbol(currency)
            balance = profile['balance'] / 100
            upi = profile['upi_address'] or "Not Set"
            
            text = f"""
{get_brand_header()}
Casino Blaze
User Wallet Profile & Forms

Username: @{profile['username']}
Available Balance: {symbol}{balance:.2f}
Linked UPI Address: {upi}

Select a form action button below:
{datetime.now().strftime('%I:%M %p')}
            """
            keyboard = [
                [InlineKeyboardButton("📜 View Game History", callback_data="view_history")],
                [InlineKeyboardButton("⚙️ Setup/Change UPI", callback_data="setup_upi")],
                [InlineKeyboardButton("💳 Deposit Form", callback_data="deposit_form")],
                [InlineKeyboardButton("📤 Withdraw Form", callback_data="withdraw_form")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == "setup_upi":
            await query.answer()
            await query.edit_message_text("⚙️ Type: /setupi value@upi\nExample: /setupi example@paytm")
            return
        
        if data == "deposit_form":
            if chat_type != 'private':
                await query.answer("❌ Open bot in private DM!", show_alert=True)
                return
            
            await query.answer()
            profile = get_user_profile(user_id)
            currency = profile['currency'] if profile else 'INR'
            symbol = get_symbol(currency)
            
            text = f"""
{get_brand_header()}
Casino Blaze
💰 DEPOSIT FORM

Select amount:
(Minimum Deposit is ₹{MIN_DEPOSIT})
            """
            keyboard = []
            amounts = [40, 100, 200, 500, 1000, 2000, 5000]
            for amt in amounts:
                keyboard.append([InlineKeyboardButton(f"₹{amt}", callback_data=f"deposit_{amt}")])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="wallet_menu")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == "withdraw_form":
            if chat_type != 'private':
                await query.answer("❌ Open bot in private DM!", show_alert=True)
                return
            
            await query.answer()
            profile = get_user_profile(user_id)
            if not profile:
                await query.edit_message_text("❌ Profile not found!")
                return
            
            currency = profile['currency']
            symbol = get_symbol(currency)
            balance = profile['balance'] / 100
            upi = profile['upi_address']
            
            if not upi:
                await query.edit_message_text("❌ No UPI set! Use /setupi")
                return
            
            if balance < MIN_WITHDRAW:
                await query.edit_message_text(f"❌ Minimum withdrawal is ₹{MIN_WITHDRAW}! Balance: {symbol}{balance:.2f}")
                return
            
            text = f"""
{get_brand_header()}
Casino Blaze
📤 WITHDRAW FORM

💰 Balance: {symbol}{balance:.2f}
📱 UPI: `{upi}`

Select amount:
            """
            keyboard = []
            amounts = [60, 100, 200, 500, 1000, 2000, 5000]
            for amt in amounts:
                if amt <= balance:
                    keyboard.append([InlineKeyboardButton(f"₹{amt}", callback_data=f"withdraw_select_{amt}")])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="wallet_menu")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data.startswith("deposit_"):
            await query.answer()
            amount = int(data.replace("deposit_", ""))
            
            if amount < MIN_DEPOSIT:
                await query.edit_message_text(f"❌ Minimum deposit limit is ₹{MIN_DEPOSIT}!")
                return
                
            req_id = add_bank_request(user_id, "deposit", amount)
            
            text = f"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃        📥 DEPOSIT INTERFACE       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

💰 **Deposit Amount:** ₹{amount}

📱 **Pay to UPI ID (Tap to Copy):**
`{UPI_ID}`

QR Code is enclosed below:
📸 **File Name:** `{QR_CODE_IMAGE}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ **Steps to Complete Deposit:**
1. Copy UPI or scan QR Code.
2. Complete transaction in your UPI app.
3. **Send the 12-digit UTR/UPI Ref number here as text.**
4. **Upload payment proof/screenshot.**
"""
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=open(QR_CODE_IMAGE, 'rb'),
                    caption=text,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="wallet_menu")]])
                )
            except Exception as e:
                await query.edit_message_text(
                    text + f"\n\n*(Error finding '{QR_CODE_IMAGE}'. Please make sure to save it in your directory!)*",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data="wallet_menu")]])
                )
            return
            
        if data.startswith("withdraw_select_"):
            await query.answer()
            amount = int(data.replace("withdraw_select_", ""))
            
            text = f"""
⌛ **Select Withdrawal Processing Speed**

Requested Amount: ₹{amount}

Select duration options:
• **10-12 Min** *(Charge: ₹8 per ₹100)*
• **30 Min** *(Charge: ₹5 per ₹100)*
• **1 Hour** *(Charge: ₹3 per ₹100)*
            """
            keyboard = [
                [InlineKeyboardButton("⚡ Fast (10-12 Mins)", callback_data=f"withdraw_tf_{amount}_10_12_min")],
                [InlineKeyboardButton("⚖️ Medium (30 Mins)", callback_data=f"withdraw_tf_{amount}_30_min")],
                [InlineKeyboardButton("🐢 Regular (1 Hour)", callback_data=f"withdraw_tf_{amount}_1_hour")],
                [InlineKeyboardButton("🔙 Back", callback_data="withdraw_form")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        if data.startswith("withdraw_tf_"):
            await query.answer()
            parts = data.split("_")
            amount = int(parts[2])
            time_frame = "_".join(parts[3:])
            
            profile = get_user_profile(user_id)
            if not profile or (profile['balance'] / 100) < amount:
                await query.edit_message_text("❌ Insufficient balance!")
                return
                
            charge = calculate_withdrawal_charge(amount, time_frame)
            payable = amount - charge
            
            update_wallet(user_id, -amount * 100)
            req_id = add_bank_request(user_id, "withdraw", amount, time_frame=time_frame)
            new_balance = get_user_profile(user_id)['balance'] / 100
            
            await query.edit_message_text(
                f"""
✅ **WITHDRAW REQUEST SUBMITTED**

📤 **Request ID:** [WD-{req_id}]
💰 **Requested Amount:** ₹{amount}
💸 **Withdrawal Fees:** ₹{charge}
💵 **Net payout:** ₹{payable}
📱 **Target UPI:** `{profile['upi_address']}`
⏳ **Expected Processing Time:** {time_frame.replace('_', ' ').title()}

⚖️ Updated Wallet Balance: ₹{new_balance:.2f}

📌 Admin has been notified for transaction approval!
                """,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="wallet_menu")]])
            )
            
            try:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Approve Payout", callback_data=f"adm_approve_{req_id}"),
                        InlineKeyboardButton("❌ Reject Payout", callback_data=f"adm_reject_{req_id}")
                    ]
                ]
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=f"📤 **Pending Payout Request [WD-{req_id}]**\n👤 User: {user_id} (@{profile['username']})\n💰 Amount: ₹{amount}\n💸 Charges: ₹{charge}\n💵 Net payout: ₹{payable}\n📱 UPI target: `{profile['upi_address']}`",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                pass
            return
        
        if data == "view_history":
            await query.answer()
            games = get_game_history(user_id)
            
            if not games:
                await query.edit_message_text("📜 No history found!")
                return
            
            text = "📜 GAME HISTORY\n━━━━━━━━━━━━━━━━━━━━━━\n"
            for game in games:
                gtype, bet, currency, result, won, date = game
                symbol = get_symbol(currency)
                emoji = "🏆" if result == "win" else "❌" if result == "loss" else "🤝"
                text += f"\n{emoji} {gtype.upper()} | {symbol}{bet} | {date[:10]}"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="wallet_menu")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if data == "back_to_main":
            await query.answer()
            await start(update, context)
            return
        
        await query.answer("❌ Invalid action.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in callback: {e}")

# ============ MAIN ============

async def set_commands(app):
    commands = [
        BotCommand("start", "Open main menu"),
        BotCommand("wallet", "Show wallet"),
        BotCommand("balance", "Check balance"),
        BotCommand("bal", "Check balance"),
        BotCommand("leaderboard", "Top 10 players"),
        BotCommand("tip", "Tip another user"),
        BotCommand("setupi", "Set UPI address"),
        BotCommand("deposit", "Deposit funds (Private Bot)"),
        BotCommand("depo", "Deposit funds (Private Bot)"),
        BotCommand("withdraw", "Withdraw funds (Private Bot)"),
        BotCommand("dice", "Play Dice game"),
        BotCommand("dart", "Play Dart game"),
        BotCommand("bowling", "Play Bowling game"),
        BotCommand("basketball", "Play Basketball game"),
        BotCommand("football", "Play Football game"),
    ]
    await app.bot.set_my_commands(commands)

def main():
    init_db()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.post_init = set_commands
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("wallet", wallet_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("bal", balance_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("tip", tip_command))
    app.add_handler(CommandHandler("setupi", setupi_command))
    app.add_handler(CommandHandler("deposit", deposit_command))
    app.add_handler(CommandHandler("depo", deposit_command))
    app.add_handler(CommandHandler("withdraw", withdraw_command))
    
    # Admin commands
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("addbalance", add_balance_command))
    app.add_handler(CommandHandler("removebalance", remove_balance_command))
    app.add_handler(CommandHandler("setbalance", set_balance_command))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("reject", reject_command))
    
    app.add_handler(CommandHandler("dice", dice_command))
    app.add_handler(CommandHandler("dart", dart_command))
    app.add_handler(CommandHandler("bowling", bowling_command))
    app.add_handler(CommandHandler("basketball", basketball_command))
    app.add_handler(CommandHandler("football", football_command))
    
    app.add_handler(MessageHandler(filters.Dice.ALL, handle_dice_message))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_user_proof))
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    print(f"{BRAND_NAME} - Bot is running!")
    print(f"👑 Admin: {ADMIN_USERNAME}")
    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )

if __name__ == '__main__':
    # Start Flask web server in background for Render
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Start the bot
    main()
