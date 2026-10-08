import os
import io
import sqlite3
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from PIL import Image
from color_utils import (
    extract_dominant_colors, hex_to_rgb, rgb_to_hex,
    nearest_matches, make_color_tile, make_color_card,
    load_palette
)

BASE = Path(__file__).parent
PALETTE_FILE = BASE / "pantone_colors.csv"
DB_FILE = BASE / "history.db"

PALETTE = load_palette(PALETTE_FILE)

def db():
    con = sqlite3.connect(DB_FILE)
    con.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        input_hex TEXT,
        pantone TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    return con

def save_history(user_id, input_hex, pantone):
    con = db()
    con.execute("INSERT INTO history(user_id,input_hex,pantone) VALUES(?,?,?)",
                (user_id, input_hex, pantone))
    con.commit()
    con.close()

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Image → Pantone", callback_data="image")],
        [InlineKeyboardButton("🔢 HEX → Pantone", callback_data="hex")],
        [InlineKeyboardButton("🌈 RGB → Pantone", callback_data="rgb")],
        [InlineKeyboardButton("🧵 TCX Match", callback_data="tcx")],
        [InlineKeyboardButton("🎨 Color Card", callback_data="card")],
        [InlineKeyboardButton("🕘 History", callback_data="history")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🎨 *MODEX PANTONE*\n\n"
        "Send an image or color value and I'll find the closest "
        "digital Pantone match.\n\n"
        "⚠️ Digital matching is an approximation. Verify against a "
        "physical swatch before production.",
        parse_mode="Markdown",
        reply_markup=menu()
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data

    if action == "image":
        context.user_data["mode"] = "image"
        await q.message.reply_text("📸 Send the image you want me to analyze.")
    elif action == "hex":
        context.user_data["mode"] = "hex"
        await q.message.reply_text("🔢 Send a HEX value, e.g. `#C41E3A`.", parse_mode="Markdown")
    elif action == "rgb":
        context.user_data["mode"] = "rgb"
        await q.message.reply_text("🌈 Send RGB as `186, 12, 47`.", parse_mode="Markdown")
    elif action == "tcx":
        context.user_data["collection"] = "TCX"
        context.user_data["mode"] = "hex"
        await q.message.reply_text("🧵 TCX mode enabled. Send a HEX value, or send an image.")
    elif action == "card":
        await q.message.reply_text("🎨 Send an image to generate a color card.")
        context.user_data["mode"] = "card"
    elif action == "history":
        con = db()
        rows = con.execute(
            "SELECT input_hex,pantone,created_at FROM history WHERE user_id=? "
            "ORDER BY id DESC LIMIT 10", (q.from_user.id,)
        ).fetchall()
        con.close()
        if not rows:
            await q.message.reply_text("🕘 No color matches yet.", reply_markup=menu())
        else:
            lines = ["🕘 *RECENT MATCHES*\n"]
            for h, p, d in rows:
                lines.append(f"• `{h}` → *{p}* ({d})")
            await q.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=menu())
    elif action == "help":
        await q.message.reply_text(
            "How to use:\n\n"
            "📸 Image → extracts dominant colors and matches them.\n"
            "🔢 HEX → matches a HEX color.\n"
            "🌈 RGB → matches an RGB color.\n"
            "🧵 TCX → filters the local dataset to TCX entries.\n"
            "🎨 Color Card → creates a PNG swatch card.\n\n"
            "Add your licensed/authorized Pantone dataset to "
            "`pantone_colors.csv` for production use.",
            reply_markup=menu()
        )

def result_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 New Match", callback_data="hex"),
         InlineKeyboardButton("🎨 Color Card", callback_data="card")],
        [InlineKeyboardButton("🕘 History", callback_data="history"),
         InlineKeyboardButton("🏠 Menu", callback_data="home")]
    ])

async def process_rgb(update, context, rgb, label=None):
    collection = context.user_data.get("collection")
    matches = nearest_matches(rgb, PALETTE, collection=collection, limit=3)
    if not matches:
        await update.message.reply_text("No matching colors found in the local palette.")
        return

    best = matches[0]
    save_history(update.effective_user.id, rgb_to_hex(rgb), best["name"])

    tile = make_color_tile(rgb, best)
    bio = io.BytesIO()
    tile.save(bio, "PNG")
    bio.seek(0)

    text = (
        "🎨 *CLOSEST DIGITAL MATCH*\n\n"
        f"*{best['name']}*\n"
        f"{best.get('description','')}\n\n"
        f"HEX: `{rgb_to_hex(rgb)}`\n"
        f"RGB: `{rgb[0]}, {rgb[1]}, {rgb[2]}`\n"
        f"Distance: `{best['distance']:.2f}`\n\n"
        "⚠️ Digital approximation — verify with a physical swatch before production."
    )
    await update.message.reply_photo(bio, caption=text, parse_mode="Markdown",
                                      reply_markup=result_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    mode = context.user_data.get("mode", "hex")

    try:
        if mode == "rgb":
            parts = [int(x.strip()) for x in text.replace("(", "").replace(")", "").split(",")]
            if len(parts) != 3 or any(x < 0 or x > 255 for x in parts):
                raise ValueError
            rgb = tuple(parts)
        else:
            rgb = hex_to_rgb(text)
    except Exception:
        await update.message.reply_text("I couldn't read that color. Try `#C41E3A` or `186, 12, 47`.",
                                        parse_mode="Markdown")
        return

    await process_rgb(update, context, rgb)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    data = await file.download_as_bytearray()
    img = Image.open(io.BytesIO(data)).convert("RGB")

    colors = extract_dominant_colors(img, 4)
    collection = context.user_data.get("collection")
    matches = []
    for rgb in colors:
        found = nearest_matches(rgb, PALETTE, collection=collection, limit=1)
        if found:
            matches.append((rgb, found[0]))

    if not matches:
        await update.message.reply_text("No colors could be matched. Check your palette dataset.")
        return

    card = make_color_card(matches)
    bio = io.BytesIO()
    card.save(bio, "PNG")
    bio.seek(0)

    lines = ["🎨 *COLORS DETECTED*\n"]
    for i, (rgb, m) in enumerate(matches, 1):
        lines.append(f"{i}. *{m['name']}* — `{rgb_to_hex(rgb)}` — distance `{m['distance']:.2f}`")
        save_history(update.effective_user.id, rgb_to_hex(rgb), m["name"])

    lines.append("\n⚠️ Digital approximation — verify with physical swatches before production.")
    await update.message.reply_photo(bio, caption="\n".join(lines), parse_mode="Markdown",
                                      reply_markup=result_keyboard())

async def on_button_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "home":
        await q.message.reply_text("🎨 MODEX PANTONE", reply_markup=menu())


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ *MODEX PANTONE SETTINGS*\n\nDigital color matching mode is active.\nUse the Telegram menu or buttons to choose a workflow.",
        parse_mode="Markdown", reply_markup=menu())

async def cmd_hex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "hex"; context.user_data["collection"] = None
    await update.message.reply_text("🔢 Send a HEX value, e.g. `#C41E3A`.", parse_mode="Markdown")

async def cmd_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "image"; context.user_data["collection"] = None
    await update.message.reply_text("📸 Send the image you want me to analyze.")

async def cmd_rgb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "rgb"; context.user_data["collection"] = None
    await update.message.reply_text("🌈 Send RGB as `186, 12, 47`.", parse_mode="Markdown")

async def cmd_cmyk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🖨️ CMYK matching will be added in the next matching-engine upgrade. For now use /hex or /rgb.")

async def cmd_tcx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["collection"] = "TCX"; context.user_data["mode"] = "hex"
    await update.message.reply_text("🧵 TCX mode enabled. Send a HEX value or an image.")

async def cmd_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "card"
    await update.message.reply_text("🎨 Send an image to generate a color card.")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con=db()
    rows=con.execute("SELECT input_hex,pantone,created_at FROM history WHERE user_id=? ORDER BY id DESC LIMIT 10", (update.effective_user.id,)).fetchall()
    con.close()
    if not rows:
        await update.message.reply_text("🕘 No color matches yet.", reply_markup=menu()); return
    lines=["🕘 *RECENT MATCHES*\n"]
    for h,p,d in rows: lines.append(f"• `{h}` → *{p}* ({d})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=menu())

async def set_commands(app):
    from telegram import BotCommand
    await app.bot.set_my_commands([
        BotCommand("start", "Bot main menu"), BotCommand("settings", "Bot settings"),
        BotCommand("hex", "HEX → Pantone"), BotCommand("image", "Image → Pantone"),
        BotCommand("rgb", "RGB → Pantone"), BotCommand("cmyk", "CMYK → Pantone"),
        BotCommand("tcx", "TCX match"), BotCommand("card", "Generate color card"),
        BotCommand("history", "Match history"), BotCommand("help", "How to use")])


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Set BOT_TOKEN in your environment.")
    app = Application.builder().token(token).post_init(set_commands).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("hex", cmd_hex))
    app.add_handler(CommandHandler("image", cmd_image))
    app.add_handler(CommandHandler("rgb", cmd_rgb))
    app.add_handler(CommandHandler("cmyk", cmd_cmyk))
    app.add_handler(CommandHandler("tcx", cmd_tcx))
    app.add_handler(CommandHandler("card", cmd_card))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CallbackQueryHandler(on_button_home, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("modexpantonebot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
