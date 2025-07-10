
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# Стани
DATE, TIME, LOCATION, DESCRIPTION = range(4)

ADMIN_ID = 491394375  # Заміни на свій Telegram ID

# Ініціалізація БД
conn = sqlite3.connect("acts.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS acts (
        user_id INTEGER,
        name TEXT,
        date TEXT,
        time TEXT,
        location TEXT,
        description TEXT
    )
""")
conn.commit()
conn.close()

# Стартове меню з кнопками
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Почати", callback_data="add_act")],
        [InlineKeyboardButton("📋 Звіт", callback_data="view_reports")],
    ]
    if update.effective_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("📊 Аналіз", callback_data="weekly_analysis")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Оберіть дію:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_act":
        await query.message.reply_text("Введіть дату виконання робіт (наприклад: 07.07):")
        return DATE

    elif data == "view_reports":
        return await reports(update, context, query.message)

    elif data == "weekly_analysis":
        return await weekly_analysis(update, context, query.message)

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['date'] = update.message.text
    await update.message.reply_text("Введіть час виконання (наприклад: 08:00-18:00):")
    return TIME

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['time'] = update.message.text
    await update.message.reply_text("Вкажіть місце виконання робіт:")
    return LOCATION

async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['location'] = update.message.text
    await update.message.reply_text("Опишіть коротко суть виконаних робіт:")
    return DESCRIPTION

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.full_name
    date = context.user_data['date']
    time = context.user_data['time']
    location = context.user_data['location']
    description = update.message.text

    conn = sqlite3.connect("acts.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO acts (user_id, name, date, time, location, description) VALUES (?, ?, ?, ?, ?, ?)",
                   (user_id, name, date, time, location, description))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Дані збережено.")

    message = f"🔔 Новий акт від {name}\n📅 {date} 🕒 {time}\n📍 {location}\n📄 {description}"
    await context.bot.send_message(chat_id=ADMIN_ID, text=message)

    return ConversationHandler.END

async def reports(update: Update, context: ContextTypes.DEFAULT_TYPE, message=None):
    if update.effective_user.id != ADMIN_ID:
        await (message or update.message).reply_text("⛔️ У вас немає доступу до звітів.")
        return

    conn = sqlite3.connect("acts.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, date, time, location, description FROM acts ORDER BY date DESC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await (message or update.message).reply_text("Записів немає.")
        return

    for row in rows:
        name, date, time, location, desc = row
        text = f"👤 {name}\n📅 {date} 🕒 {time}\n📍 {location}\n📄 {desc}"
        await (message or update.message).reply_text(text)

async def weekly_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, message=None):
    if update.effective_user.id != ADMIN_ID:
        await (message or update.message).reply_text("⛔️ У вас немає доступу.")
        return

    conn = sqlite3.connect("acts.db")
    df = pd.read_sql_query("SELECT * FROM acts", conn)
    conn.close()

    if df.empty:
        await (message or update.message).reply_text("Немає даних для аналізу.")
        return

    df['date'] = pd.to_datetime(df['date'])
    end_date = datetime.today()
    start_date = end_date - timedelta(days=7)
    weekly_df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

    if weekly_df.empty:
        await (message or update.message).reply_text("За останній тиждень немає записів.")
        return

    summary = weekly_df.groupby(['name']).size().reset_index(name='Кількість записів')
    summary_text = "📊 Аналіз за останній тиждень:\n" + "\n".join([f"{row['name']}: {row['Кількість записів']}" for _, row in summary.iterrows()])
    await (message or update.message).reply_text(summary_text)

    filename = f"weekly_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    weekly_df.to_excel(filename, index=False)

    with open(filename, "rb") as file:
        await (message or update.message).reply_document(file, filename=filename)

def main():
    app = ApplicationBuilder().token("7630920412:AAG41qE4TbBLUUXN3NAU-KbEW_wxXYI2Fao").build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^add_act$")],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_location)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Бот запущено...")
    app.run_polling()

if __name__ == "__main__":
    main()
