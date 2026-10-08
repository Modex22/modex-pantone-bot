import os
import io
import sqlite3
import threading
import traceback
from pathlib import Path

from flask import Flask
from PIL import Image

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from color_utils import (
    extract_dominant_colors,
    hex_to_rgb,
    nearest_matches,
    make_color_tile,
    make_color_card,
    load_palette,
)


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "history.db"
PALETTE_PATH = BASE_DIR / "pantone_colors.csv"

BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")


# ============================================================
# LOAD PALETTE
# ============================================================

print("🎨 Loading Pantone palette...", flush=True)

try:
    PALETTE = load_palette(PALETTE_PATH)

    print(
        f"✅ Palette loaded: {len(PALETTE)} colors",
        flush=True
    )

except Exception as e:
    print(
        f"❌ Palette loading failed: {e}",
        flush=True
    )

    traceback.print_exc()
    raise


# ============================================================
# DATABASE
# ============================================================

def init_db():

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            input_type TEXT,
            input_value TEXT,
            pantone_name TEXT,
            rgb TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    print(
        "✅ Database initialized",
        flush=True
    )


def save_history(
    user_id,
    input_type,
    input_value,
    pantone_name,
    rgb
):

    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        """
        INSERT INTO history
        (user_id, input_type, input_value, pantone_name, rgb)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            input_type,
            input_value,
            pantone_name,
            str(rgb),
        ),
    )

    conn.commit()
    conn.close()


def get_history(user_id, limit=10):

    conn = sqlite3.connect(DB_PATH)

    rows = conn.execute(
        """
        SELECT input_type, input_value, pantone_name, rgb, created_at
        FROM history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            user_id,
            limit,
        ),
    ).fetchall()

    conn.close()

    return rows


# ============================================================
# RENDER WEB SERVER
# ============================================================

web_app = Flask(__name__)


@web_app.route("/")
def home():

    return "MODEX PANTONE BOT IS ONLINE", 200


@web_app.route("/health")
def health():

    return "OK", 200


def run_web_server():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    print(
        f"🌐 Starting Render web server on port {port}",
        flush=True
    )

    web_app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


# ============================================================
# TELEGRAM COMMAND MENU
# ============================================================

async def set_commands(application):

    commands = [

        BotCommand(
            "start",
            "Bot main menu"
        ),

        BotCommand(
            "settings",
            "Bot settings"
        ),

        BotCommand(
            "hex",
            "HEX → Pantone"
        ),

        BotCommand(
            "image",
            "Image → Pantone"
        ),

        BotCommand(
            "rgb",
            "RGB → Pantone"
        ),

        BotCommand(
            "cmyk",
            "CMYK → Pantone"
        ),

        BotCommand(
            "tcx",
            "TCX match"
        ),

        BotCommand(
            "card",
            "Generate color card"
        ),

        BotCommand(
            "history",
            "Match history"
        ),

        BotCommand(
            "help",
            "How to use"
        ),
    ]

    await application.bot.set_my_commands(
        commands
    )

    print(
        "✅ Telegram command menu configured",
        flush=True
    )


# ============================================================
# MAIN MENU
# ============================================================

def main_menu():

    keyboard = [

        [
            InlineKeyboardButton(
                "🎨 Image → Pantone",
                callback_data="image"
            ),

            InlineKeyboardButton(
                "🔢 HEX → Pantone",
                callback_data="hex"
            ),
        ],

        [
            InlineKeyboardButton(
                "🌈 RGB → Pantone",
                callback_data="rgb"
            ),

            InlineKeyboardButton(
                "👕 TCX Match",
                callback_data="tcx"
            ),
        ],

        [
            InlineKeyboardButton(
                "🖼 Color Card",
                callback_data="card"
            ),

            InlineKeyboardButton(
                "📜 History",
                callback_data="history"
            ),
        ],

        [
            InlineKeyboardButton(
                "⚙️ Settings",
                callback_data="settings"
            ),

            InlineKeyboardButton(
                "❓ Help",
                callback_data="help"
            ),
        ],
    ]

    return InlineKeyboardMarkup(
        keyboard
    )


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        f"👤 /start from {update.effective_user.id}",
        flush=True
    )

    await update.message.reply_text(
        "🎨 *MODEX PANTONE*\n\n"
        "Match colors to the closest Pantone reference.\n\n"
        "Choose an option below:",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


# ============================================================
# /HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🎨 *MODEX PANTONE — HOW TO USE*\n\n"
        "• `/hex` — Match a HEX color\n"
        "• `/rgb` — Match an RGB color\n"
        "• `/image` — Match colors from an image\n"
        "• `/tcx` — Search TCX colors\n"
        "• `/card` — Generate a color card\n"
        "• `/history` — View previous matches\n"
        "• `/settings` — Bot settings\n\n"
        "You can also simply send me an image.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


# ============================================================
# /SETTINGS
# ============================================================

async def settings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "⚙️ *SETTINGS*\n\n"
        "Color matching: Lab distance\n"
        "Image extraction: Dominant colors\n"
        "Palette: Local dataset",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


# ============================================================
# /HEX
# ============================================================

async def hex_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["mode"] = "hex"

    if context.args:

        value = context.args[0]

        await process_hex(
            update,
            context,
            value,
        )

        return

    await update.message.reply_text(
        "🔢 *HEX → Pantone*\n\n"
        "Send a HEX color.\n\n"
        "Example:\n"
        "`#FF0000`",
        parse_mode="Markdown",
    )


# ============================================================
# /RGB
# ============================================================

async def rgb_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["mode"] = "rgb"

    if context.args:

        value = " ".join(
            context.args
        )

        await process_rgb(
            update,
            context,
            value,
        )

        return

    await update.message.reply_text(
        "🌈 *RGB → Pantone*\n\n"
        "Send RGB values.\n\n"
        "Example:\n"
        "`255 0 0`",
        parse_mode="Markdown",
    )


# ============================================================
# /CMYK
# ============================================================

async def cmyk_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🖨 *CMYK → Pantone*\n\n"
        "CMYK matching is not enabled yet.\n\n"
        "Use `/hex` or `/rgb` for now.",
        parse_mode="Markdown",
    )


# ============================================================
# /IMAGE
# ============================================================

async def image_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["mode"] = "image"

    print(
        f"🖼 /image requested by "
        f"{update.effective_user.id}",
        flush=True
    )

    await update.message.reply_text(
        "🎨 Send me an image and I'll extract its "
        "dominant colors and find the closest Pantone references."
    )


# ============================================================
# /TCX
# ============================================================

async def tcx_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["mode"] = "tcx"

    await update.message.reply_text(
        "👕 *TCX MATCH*\n\n"
        "Send a HEX color.\n\n"
        "Example:\n"
        "`#C6233A`",
        parse_mode="Markdown",
    )


# ============================================================
# /CARD
# ============================================================

async def card_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["mode"] = "card"

    await update.message.reply_text(
        "🖼 *COLOR CARD*\n\n"
        "Send an image and I'll generate a color card "
        "from its dominant colors.",
        parse_mode="Markdown",
    )


# ============================================================
# /HISTORY
# ============================================================

async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    rows = get_history(
        update.effective_user.id
    )

    if not rows:

        await update.message.reply_text(
            "📜 You don't have any match history yet."
        )

        return

    text = "📜 *YOUR MATCH HISTORY*\n\n"

    for row in rows:

        (
            input_type,
            input_value,
            pantone_name,
            rgb,
            created_at,
        ) = row

        text += (
            f"• `{input_value}` → "
            f"*{pantone_name}*\n"
            f"  {created_at}\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


# ============================================================
# HEX PROCESSING
# ============================================================

async def process_hex(
    update,
    context,
    value,
):

    print(
        f"🔢 Processing HEX: {value}",
        flush=True
    )

    try:

        rgb = hex_to_rgb(
            value
        )

    except Exception as e:

        print(
            f"❌ HEX ERROR: {e}",
            flush=True
        )

        await update.message.reply_text(
            "❌ Invalid HEX color.\n\n"
            "Example:\n"
            "`#FF0000`",
            parse_mode="Markdown",
        )

        return

    collection = None

    if context.user_data.get(
        "mode"
    ) == "tcx":

        collection = "TCX"

    try:

        matches = nearest_matches(
            rgb,
            PALETTE,
            n=3,
            collection=collection,
        )

    except Exception as e:

        print(
            f"❌ MATCHING ERROR: {e}",
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ Error matching this color."
        )

        return

    if not matches:

        await update.message.reply_text(
            "❌ No matching colors found."
        )

        return

    best = matches[0]

    pantone_name = best["name"]

    pantone_rgb = (
        best["r"],
        best["g"],
        best["b"],
    )

    save_history(
        update.effective_user.id,
        "HEX",
        value,
        pantone_name,
        pantone_rgb,
    )

    text = (
        "🎨 *COLOR MATCH*\n\n"
        f"Input: `{value}`\n"
        f"RGB: `{rgb}`\n\n"
        "🏆 *Closest Match*\n"
        f"*{pantone_name}*\n"
        f"RGB: `{pantone_rgb}`\n\n"
        "Other close matches:\n"
    )

    for match in matches[1:]:

        text += (
            f"• {match['name']} — "
            f"RGB {match['r']}, "
            f"{match['g']}, "
            f"{match['b']}\n"
        )

    try:

        tile = make_color_tile(
            pantone_name,
            pantone_rgb,
        )

        output = io.BytesIO()

        tile.save(
            output,
            format="PNG"
        )

        output.seek(0)

        await update.message.reply_photo(
            photo=output,
            caption=text,
            parse_mode="Markdown",
        )

    except Exception as e:

        print(
            f"❌ TILE ERROR: {e}",
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
        )


# ============================================================
# RGB PROCESSING
# ============================================================

async def process_rgb(
    update,
    context,
    value,
):

    print(
        f"🌈 Processing RGB: {value}",
        flush=True
    )

    try:

        cleaned = (
            value
            .replace(",", " ")
            .replace("(", " ")
            .replace(")", " ")
        )

        parts = cleaned.split()

        if len(parts) != 3:
            raise ValueError

        rgb = tuple(
            int(float(x))
            for x in parts
        )

        if any(
            x < 0 or x > 255
            for x in rgb
        ):
            raise ValueError

    except Exception:

        await update.message.reply_text(
            "❌ Invalid RGB value.\n\n"
            "Example:\n"
            "`/rgb 255 0 0`",
            parse_mode="Markdown",
        )

        return

    try:

        matches = nearest_matches(
            rgb,
            PALETTE,
            n=3,
        )

    except Exception as e:

        print(
            f"❌ RGB MATCH ERROR: {e}",
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ Error matching this color."
        )

        return

    if not matches:

        await update.message.reply_text(
            "❌ No matching colors found."
        )

        return

    best = matches[0]

    pantone_name = best["name"]

    pantone_rgb = (
        best["r"],
        best["g"],
        best["b"],
    )

    save_history(
        update.effective_user.id,
        "RGB",
        value,
        pantone_name,
        pantone_rgb,
    )

    text = (
        "🌈 *RGB MATCH*\n\n"
        f"Input: `{rgb}`\n\n"
        "🏆 *Closest Match*\n"
        f"*{pantone_name}*\n"
        f"RGB: `{pantone_rgb}`\n\n"
        "Other close matches:\n"
    )

    for match in matches[1:]:

        text += (
            f"• {match['name']} — "
            f"RGB {match['r']}, "
            f"{match['g']}, "
            f"{match['b']}\n"
        )

    try:

        tile = make_color_tile(
            pantone_name,
            pantone_rgb,
        )

        output = io.BytesIO()

        tile.save(
            output,
            format="PNG"
        )

        output.seek(0)

        await update.message.reply_photo(
            photo=output,
            caption=text,
            parse_mode="Markdown",
        )

    except Exception as e:

        print(
            f"❌ RGB TILE ERROR: {e}",
            flush=True
        )

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
        )


# ============================================================
# IMAGE PROCESSING
# ============================================================

async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    print(
        "📸 =============================",
        flush=True
    )

    print(
        "📸 PHOTO RECEIVED",
        flush=True
    )

    print(
        "📸 =============================",
        flush=True
    )

    processing_message = None

    try:

        if not update.message:

            print(
                "❌ No message object",
                flush=True
            )

            return

        if not update.message.photo:

            print(
                "❌ No photo object",
                flush=True
            )

            return

        # ----------------------------------------------------
        # PROCESSING MESSAGE
        # ----------------------------------------------------

        processing_message = (
            await update.message.reply_text(
                "⏳ Processing your image..."
            )
        )

        print(
            "✅ Processing message sent",
            flush=True
        )

        # ----------------------------------------------------
        # GET PHOTO
        # ----------------------------------------------------

        photo = update.message.photo[-1]

        print(
            f"📸 Telegram file ID: "
            f"{photo.file_id}",
            flush=True
        )

        print(
            f"📸 Dimensions: "
            f"{photo.width}x{photo.height}",
            flush=True
        )

        # ----------------------------------------------------
        # DOWNLOAD PHOTO
        # ----------------------------------------------------

        print(
            "📥 Getting Telegram file...",
            flush=True
        )

        telegram_file = await context.bot.get_file(
            photo.file_id
        )

        print(
            "✅ Telegram file obtained",
            flush=True
        )

        print(
            "📥 Downloading image...",
            flush=True
        )

        image_bytes = (
            await telegram_file.download_as_bytearray()
        )

        print(
            f"✅ Downloaded "
            f"{len(image_bytes)} bytes",
            flush=True
        )

        # ----------------------------------------------------
        # OPEN IMAGE
        # ----------------------------------------------------

        print(
            "🖼 Opening image with Pillow...",
            flush=True
        )

        image = Image.open(
            io.BytesIO(image_bytes)
        )

        print(
            f"🖼 Format: {image.format}",
            flush=True
        )

        print(
            f"🖼 Mode: {image.mode}",
            flush=True
        )

        print(
            f"🖼 Size: {image.size}",
            flush=True
        )

        image = image.convert(
            "RGB"
        )

        print(
            "✅ Image converted to RGB",
            flush=True
        )

        # ----------------------------------------------------
        # EXTRACT DOMINANT COLORS
        # ----------------------------------------------------

        print(
            "🎨 Extracting dominant colors...",
            flush=True
        )

        # IMPORTANT:
        # Your existing color_utils.py does NOT accept n=5.
        colors = extract_dominant_colors(
            image
        )

        print(
            f"✅ Extracted colors: {colors}",
            flush=True
        )

        if not colors:

            await processing_message.edit_text(
                "❌ I couldn't extract colors "
                "from this image."
            )

            return

        # ----------------------------------------------------
        # CURRENT MODE
        # ----------------------------------------------------

        mode = context.user_data.get(
            "mode",
            "image"
        )

        print(
            f"🔧 Current mode: {mode}",
            flush=True
        )

        # ====================================================
        # COLOR CARD
        # ====================================================

        if mode == "card":

            print(
                "🖼 Generating color card...",
                flush=True
            )

            matches_for_card = []

            for rgb in colors:

                print(
                    f"🔍 Matching RGB {rgb}",
                    flush=True
                )

                matches = nearest_matches(
                    rgb,
                    PALETTE,
                    n=1,
                )

                if matches:

                    match = matches[0]

                    matches_for_card.append(
                        (
                            match["name"],
                            (
                                match["r"],
                                match["g"],
                                match["b"],
                            ),
                        )
                    )

            if not matches_for_card:

                await processing_message.edit_text(
                    "❌ Couldn't find Pantone matches."
                )

                return

            print(
                "🖼 Creating color card...",
                flush=True
            )

            card = make_color_card(
                matches_for_card
            )

            output = io.BytesIO()

            card.save(
                output,
                format="PNG"
            )

            output.seek(0)

            await update.message.reply_photo(
                photo=output,
                caption=(
                    "🖼 *MODEX PANTONE COLOR CARD*"
                ),
                parse_mode="Markdown",
            )

            await processing_message.delete()

            context.user_data.pop(
                "mode",
                None
            )

            print(
                "✅ COLOR CARD COMPLETE",
                flush=True
            )

            return

        # ====================================================
        # IMAGE → PANTONE
        # ====================================================

        results = []

        for rgb in colors:

            print(
                f"🔍 Matching color: {rgb}",
                flush=True
            )

            collection = None

            if mode == "tcx":
                collection = "TCX"

            matches = nearest_matches(
                rgb,
                PALETTE,
                n=1,
                collection=collection,
            )

            if matches:

                results.append(
                    (
                        rgb,
                        matches[0],
                    )
                )

        print(
            f"✅ Total matches: "
            f"{len(results)}",
            flush=True
        )

        if not results:

            await processing_message.edit_text(
                "❌ I couldn't find any Pantone matches."
            )

            return

        # ----------------------------------------------------
        # BUILD RESPONSE
        # ----------------------------------------------------

        text = (
            "🎨 *IMAGE → PANTONE*\n\n"
        )

        for rgb, match in results:

            pantone_rgb = (
                match["r"],
                match["g"],
                match["b"],
            )

            print(
                f"🎯 {rgb} → "
                f"{match['name']}",
                flush=True
            )

            save_history(
                update.effective_user.id,
                "IMAGE",
                str(rgb),
                match["name"],
                pantone_rgb,
            )

            text += (
                f"🎨 RGB `{rgb}`\n"
                f"→ *{match['name']}*\n"
                f"Pantone RGB "
                f"`{pantone_rgb}`\n\n"
            )

        # ----------------------------------------------------
        # SEND RESULT
        # ----------------------------------------------------

        print(
            "📤 Sending Pantone results...",
            flush=True
        )

        await processing_message.edit_text(
            text,
            parse_mode="Markdown",
        )

        context.user_data.pop(
            "mode",
            None
        )

        print(
            "✅ IMAGE PROCESSING COMPLETE",
            flush=True
        )

    except Exception as e:

        print(
            "❌ =============================",
            flush=True
        )

        print(
            f"❌ PHOTO PROCESSING ERROR: "
            f"{type(e).__name__}: {e}",
            flush=True
        )

        print(
            "❌ =============================",
            flush=True
        )

        traceback.print_exc()

        try:

            error_text = (
                "❌ *Something went wrong while "
                "processing the image.*\n\n"
                f"Error: `{type(e).__name__}: "
                f"{e}`"
            )

            if processing_message:

                await processing_message.edit_text(
                    error_text,
                    parse_mode="Markdown",
                )

            else:

                await update.message.reply_text(
                    error_text,
                    parse_mode="Markdown",
                )

        except Exception as send_error:

            print(
                f"❌ Couldn't send error: "
                f"{send_error}",
                flush=True
            )


# ============================================================
# TEXT HANDLER
# ============================================================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = update.message.text.strip()

    mode = context.user_data.get(
        "mode"
    )

    print(
        f"💬 TEXT RECEIVED: {text}",
        flush=True
    )

    # TCX
    if mode == "tcx":

        await process_hex(
            update,
            context,
            text,
        )

        context.user_data.pop(
            "mode",
            None
        )

        return

    # HEX
    if mode == "hex":

        await process_hex(
            update,
            context,
            text,
        )

        context.user_data.pop(
            "mode",
            None
        )

        return

    # RGB
    if mode == "rgb":

        await process_rgb(
            update,
            context,
            text,
        )

        context.user_data.pop(
            "mode",
            None
        )

        return

    # CARD
    if mode == "card":

        await update.message.reply_text(
            "🖼 Please send an image "
            "for the color card."
        )

        return

    # AUTOMATIC HEX
    if text.startswith("#") or (
        len(text) in (6, 7)
        and all(
            c in "0123456789abcdefABCDEF"
            for c in text.lstrip("#")
        )
    ):

        await process_hex(
            update,
            context,
            text,
        )

        return

    # AUTOMATIC RGB
    parts = (
        text
        .replace(",", " ")
        .replace("(", " ")
        .replace(")", " ")
        .split()
    )

    if len(parts) == 3:

        try:

            if all(
                0 <= int(x) <= 255
                for x in parts
            ):

                await process_rgb(
                    update,
                    context,
                    text,
                )

                return

        except ValueError:
            pass

    await update.message.reply_text(
        "I didn't recognize that color.\n\n"
        "Try:\n"
        "`#FF0000`\n"
        "`255 0 0`\n\n"
        "Or send me an image.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


# ============================================================
# BUTTON HANDLER
# ============================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    data = query.data

    print(
        f"🔘 BUTTON: {data}",
        flush=True
    )

    # IMAGE
    if data == "image":

        context.user_data["mode"] = "image"

        await query.message.reply_text(
            "🎨 Send me an image and I'll match "
            "its dominant colors to Pantone."
        )

    # HEX
    elif data == "hex":

        context.user_data["mode"] = "hex"

        await query.message.reply_text(
            "🔢 Send a HEX color.\n\n"
            "Example:\n"
            "`#FF0000`",
            parse_mode="Markdown",
        )

    # RGB
    elif data == "rgb":

        context.user_data["mode"] = "rgb"

        await query.message.reply_text(
            "🌈 Send RGB values.\n\n"
            "Example:\n"
            "`255 0 0`",
            parse_mode="Markdown",
        )

    # TCX
    elif data == "tcx":

        context.user_data["mode"] = "tcx"

        await query.message.reply_text(
            "👕 *TCX MATCH*\n\n"
            "Send a HEX color.\n\n"
            "Example:\n"
            "`#C6233A`",
            parse_mode="Markdown",
        )

    # CARD
    elif data == "card":

        context.user_data["mode"] = "card"

        await query.message.reply_text(
            "🖼 Send an image and I'll generate "
            "a color card."
        )

    # HISTORY
    elif data == "history":

        rows = get_history(
            query.from_user.id
        )

        if not rows:

            await query.message.reply_text(
                "📜 No match history yet."
            )

            return

        text = (
            "📜 *YOUR MATCH HISTORY*\n\n"
        )

        for row in rows:

            (
                input_type,
                input_value,
                pantone_name,
                rgb,
                created_at,
            ) = row

            text += (
                f"• `{input_value}` → "
                f"*{pantone_name}*\n"
                f"  {created_at}\n\n"
            )

        await query.message.reply_text(
            text,
            parse_mode="Markdown",
        )

    # SETTINGS
    elif data == "settings":

        await query.message.reply_text(
            "⚙️ *SETTINGS*\n\n"
            "Color matching: Lab distance\n"
            "Image extraction: Dominant colors\n"
            "Palette: Local dataset",
            parse_mode="Markdown",
        )

    # HELP
    elif data == "help":

        await query.message.reply_text(
            "❓ *HOW TO USE MODEX PANTONE*\n\n"
            "Send:\n"
            "• A HEX color\n"
            "• RGB values\n"
            "• An image\n\n"
            "Commands:\n"
            "`/hex`\n"
            "`/rgb`\n"
            "`/image`\n"
            "`/tcx`\n"
            "`/card`\n"
            "`/history`\n"
            "`/help`",
            parse_mode="Markdown",
        )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    print(
        "❌ TELEGRAM ERROR",
        flush=True
    )

    print(
        f"❌ {type(context.error).__name__}: "
        f"{context.error}",
        flush=True
    )

    traceback.print_exception(
        type(context.error),
        context.error,
        context.error.__traceback__,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================",
        flush=True
    )

    print(
        "🚀 MODEX PANTONE STARTING",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    # Database
    init_db()

    # Render Web Server
    web_thread = threading.Thread(
        target=run_web_server,
        daemon=True,
    )

    web_thread.start()

    print(
        "✅ Render web server started.",
        flush=True
    )

    # Telegram application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(set_commands)
        .build()
    )

    # --------------------------------------------------------
    # COMMANDS
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "settings",
            settings_command
        )
    )

    application.add_handler(
        CommandHandler(
            "hex",
            hex_command
        )
    )

    application.add_handler(
        CommandHandler(
            "rgb",
            rgb_command
        )
    )

    application.add_handler(
        CommandHandler(
            "cmyk",
            cmyk_command
        )
    )

    application.add_handler(
        CommandHandler(
            "image",
            image_command
        )
    )

    application.add_handler(
        CommandHandler(
            "tcx",
            tcx_command
        )
    )

    application.add_handler(
        CommandHandler(
            "card",
            card_command
        )
    )

    application.add_handler(
        CommandHandler(
            "history",
            history_command
        )
    )

    # --------------------------------------------------------
    # BUTTONS
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # --------------------------------------------------------
    # PHOTOS
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    # --------------------------------------------------------
    # ERRORS
    # --------------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    print(
        "🤖 Telegram bot is running...",
        flush=True
    )

    print(
        "📸 Photo handler registered.",
        flush=True
    )

    print(
        "💬 Text handler registered.",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    # --------------------------------------------------------
    # TELEGRAM POLLING
    # --------------------------------------------------------

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()