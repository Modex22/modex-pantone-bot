import os
import io
import sqlite3
import traceback
from pathlib import Path

from PIL import Image

from telegram import (
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
    make_color_card,
    load_palette,
    rgb_to_hex,
)


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "history.db"
PALETTE_PATH = BASE_DIR / "pantone_colors.csv"

BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable is missing."
    )


# =========================================================
# LOAD PALETTE
# =========================================================

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


# =========================================================
# DATABASE
# =========================================================

def init_db():

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            input_type TEXT,
            input_value TEXT,
            pantone_name TEXT,
            rgb TEXT,
            created_at TEXT
        )
    """)

    cursor.execute(
        "PRAGMA table_info(history)"
    )

    columns = {
        row[1]
        for row in cursor.fetchall()
    }

    # Migrate older database versions
    if "user_id" not in columns:
        cursor.execute(
            "ALTER TABLE history ADD COLUMN user_id INTEGER"
        )

    if "input_type" not in columns:
        cursor.execute(
            "ALTER TABLE history ADD COLUMN input_type TEXT"
        )

    if "input_value" not in columns:
        cursor.execute(
            "ALTER TABLE history ADD COLUMN input_value TEXT"
        )

    if "pantone_name" not in columns:
        cursor.execute(
            "ALTER TABLE history ADD COLUMN pantone_name TEXT"
        )

    if "rgb" not in columns:
        cursor.execute(
            "ALTER TABLE history ADD COLUMN rgb TEXT"
        )

    if "created_at" not in columns:
        cursor.execute(
            "ALTER TABLE history ADD COLUMN created_at TEXT"
        )

    cursor.execute("""
        UPDATE history
        SET created_at = datetime('now')
        WHERE created_at IS NULL
    """)

    conn.commit()
    conn.close()

    print(
        "✅ Database initialized and migrated",
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
        (
            user_id,
            input_type,
            input_value,
            pantone_name,
            rgb,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, datetime('now'))
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
        SELECT
            input_type,
            input_value,
            pantone_name,
            rgb,
            created_at
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


# =========================================================
# BOT COMMAND MENU
# =========================================================

async def set_commands(application):

    commands = [

        BotCommand(
            "start",
            "Bot main menu"
        ),

        BotCommand(
            "hex",
            "HEX → Pantone"
        ),

        BotCommand(
            "rgb",
            "RGB → Pantone"
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
            "settings",
            "Bot settings"
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


# =========================================================
# MAIN MENU
# =========================================================

def main_menu():

    keyboard = [

        [
            InlineKeyboardButton(
                "🔢 HEX → Pantone",
                callback_data="hex"
            ),

            InlineKeyboardButton(
                "🌈 RGB → Pantone",
                callback_data="rgb"
            ),
        ],

        [
            InlineKeyboardButton(
                "👕 TCX Match",
                callback_data="tcx"
            ),

            InlineKeyboardButton(
                "🖼 Color Card",
                callback_data="card"
            ),
        ],

        [
            InlineKeyboardButton(
                "📜 History",
                callback_data="history"
            ),

            InlineKeyboardButton(
                "⚙️ Settings",
                callback_data="settings"
            ),
        ],

        [
            InlineKeyboardButton(
                "❓ Help",
                callback_data="help"
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# START
# =========================================================

async def start(update, context):

    print(
        f"👤 /start from "
        f"{update.effective_user.id}",
        flush=True
    )

    await update.message.reply_text(

        "🎨 *MODEX PANTONE*\n\n"

        "Send me an image and I'll "
        "automatically extract its colors "
        "and find the closest Pantone references.\n\n"

        "You can also use the options below:",

        parse_mode="Markdown",

        reply_markup=main_menu(),
    )


# =========================================================
# HELP
# =========================================================

async def help_command(update, context):

    await update.message.reply_text(

        "🎨 *MODEX PANTONE — HOW TO USE*\n\n"

        "📸 *IMAGE*\n"
        "Simply send me an image. "
        "No button required.\n\n"

        "🔢 *HEX*\n"
        "`#FF0000`\n\n"

        "🌈 *RGB*\n"
        "`255 0 0`\n\n"

        "👕 *TCX*\n"
        "Use `/tcx` then send a HEX color.\n\n"

        "🖼 *COLOR CARD*\n"
        "Use `/card` then send an image.\n\n"

        "📜 *HISTORY*\n"
        "Use `/history` to see your matches.",

        parse_mode="Markdown",

        reply_markup=main_menu(),
    )


# =========================================================
# SETTINGS
# =========================================================

async def settings_command(update, context):

    await update.message.reply_text(

        "⚙️ *SETTINGS*\n\n"

        "Color matching: Lab distance\n"
        "Image extraction: Dominant colors\n"
        "Dominant colors: 4\n"
        "Palette: Local dataset\n\n"

        "⚠️ Pantone results are digital "
        "approximations.",

        parse_mode="Markdown",
    )


# =========================================================
# HEX COMMAND
# =========================================================

async def hex_command(update, context):

    context.user_data["mode"] = "hex"

    if context.args:

        await process_hex(
            update,
            context,
            context.args[0]
        )

        context.user_data.pop(
            "mode",
            None
        )

        return

    await update.message.reply_text(

        "🔢 *HEX → PANTONE*\n\n"

        "Send a HEX color.\n\n"

        "Example:\n"
        "`#FF0000`",

        parse_mode="Markdown",
    )


# =========================================================
# RGB COMMAND
# =========================================================

async def rgb_command(update, context):

    context.user_data["mode"] = "rgb"

    if context.args:

        await process_rgb(
            update,
            context,
            " ".join(context.args)
        )

        context.user_data.pop(
            "mode",
            None
        )

        return

    await update.message.reply_text(

        "🌈 *RGB → PANTONE*\n\n"

        "Send RGB values.\n\n"

        "Example:\n"
        "`255 0 0`",

        parse_mode="Markdown",
    )


# =========================================================
# TCX COMMAND
# =========================================================

async def tcx_command(update, context):

    context.user_data["mode"] = "tcx"

    await update.message.reply_text(

        "👕 *TCX MATCH*\n\n"

        "Send a HEX color.\n\n"

        "Example:\n"
        "`#C6233A`",

        parse_mode="Markdown",
    )


# =========================================================
# CARD COMMAND
# =========================================================

async def card_command(update, context):

    context.user_data["mode"] = "card"

    await update.message.reply_text(

        "🖼 *COLOR CARD*\n\n"

        "Send an image and I'll generate "
        "a Pantone color card.",

        parse_mode="Markdown",
    )


# =========================================================
# HISTORY COMMAND
# =========================================================

async def history_command(update, context):

    rows = get_history(
        update.effective_user.id
    )

    if not rows:

        await update.message.reply_text(
            "📜 You don't have any match "
            "history yet."
        )

        return

    text = "📜 *YOUR MATCH HISTORY*\n\n"

    for row in rows:

        (
            input_type,
            input_value,
            pantone_name,
            rgb,
            created_at
        ) = row

        text += (
            f"• `{input_value}` → "
            f"*{pantone_name}*\n"
            f"  {created_at}\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# HEX PROCESSING
# =========================================================

async def process_hex(
    update,
    context,
    value
):

    print(
        f"🔢 Processing HEX: {value}",
        flush=True
    )

    try:

        rgb = hex_to_rgb(value)

    except Exception:

        await update.message.reply_text(

            "❌ Invalid HEX color.\n\n"

            "Example:\n"
            "`#FF0000`",

            parse_mode="Markdown",
        )

        return

    collection = (
        "TCX"
        if context.user_data.get("mode") == "tcx"
        else None
    )

    try:

        matches = nearest_matches(
            rgb,
            PALETTE,
            collection=collection,
            limit=3,
        )

    except Exception as e:

        print(
            f"❌ HEX MATCH ERROR: {e}",
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

        f"HEX: `{rgb_to_hex(pantone_rgb)}`\n"

        f"RGB: `{pantone_rgb}`\n"

        f"Distance: `{best['distance']:.2f}`\n\n"

        "Other close matches:\n"
    )

    for match in matches[1:]:

        match_rgb = (
            match["r"],
            match["g"],
            match["b"],
        )

        text += (
            f"• {match['name']} — "
            f"`{rgb_to_hex(match_rgb)}` — "
            f"`{match['distance']:.2f}`\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# RGB PROCESSING
# =========================================================

async def process_rgb(
    update,
    context,
    value
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
            "`255 0 0`",

            parse_mode="Markdown",
        )

        return

    try:

        matches = nearest_matches(
            rgb,
            PALETTE,
            limit=3,
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

        f"HEX: `{rgb_to_hex(pantone_rgb)}`\n"

        f"RGB: `{pantone_rgb}`\n"

        f"Distance: `{best['distance']:.2f}`\n\n"

        "Other close matches:\n"
    )

    for match in matches[1:]:

        match_rgb = (
            match["r"],
            match["g"],
            match["b"],
        )

        text += (
            f"• {match['name']} — "
            f"`{rgb_to_hex(match_rgb)}` — "
            f"`{match['distance']:.2f}`\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# IMAGE PROCESSING
# =========================================================

async def handle_photo(
    update,
    context
):

    print(
        "========================================",
        flush=True
    )

    print(
        "📸 PHOTO RECEIVED",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    processing_message = None

    try:

        if not update.message:
            return

        if not update.message.photo:
            return

        # -------------------------------------------------
        # PROCESSING MESSAGE
        # -------------------------------------------------

        processing_message = (
            await update.message.reply_text(
                "⏳ Processing your image..."
            )
        )

        # -------------------------------------------------
        # GET PHOTO
        # -------------------------------------------------

        photo = update.message.photo[-1]

        print(
            f"📸 File ID: {photo.file_id}",
            flush=True
        )

        print(
            f"📸 Dimensions: "
            f"{photo.width}x{photo.height}",
            flush=True
        )

        telegram_file = (
            await context.bot.get_file(
                photo.file_id
            )
        )

        # -------------------------------------------------
        # DOWNLOAD
        # -------------------------------------------------

        image_bytes = (
            await telegram_file.download_as_bytearray()
        )

        print(
            f"✅ Downloaded "
            f"{len(image_bytes)} bytes",
            flush=True
        )

        # -------------------------------------------------
        # OPEN IMAGE
        # -------------------------------------------------

        image = Image.open(
            io.BytesIO(image_bytes)
        )

        print(
            f"🖼 Image: "
            f"{image.format} "
            f"{image.size}",
            flush=True
        )

        image = image.convert("RGB")

        # -------------------------------------------------
        # EXTRACT COLORS
        # -------------------------------------------------

        print(
            "🎨 Extracting dominant colors...",
            flush=True
        )

        colors = extract_dominant_colors(
            image,
            count=4
        )

        print(
            f"✅ Extracted colors: "
            f"{colors}",
            flush=True
        )

        if not colors:

            await processing_message.edit_text(
                "❌ I couldn't extract colors "
                "from this image."
            )

            return

        # =================================================
        # MATCH COLORS
        # =================================================

        results = []

        for rgb in colors:

            print(
                f"🔍 Matching RGB {rgb}",
                flush=True
            )

            matches = nearest_matches(
                rgb,
                PALETTE,
                limit=1,
            )

            if matches:

                results.append(
                    (
                        rgb,
                        matches[0]
                    )
                )

        print(
            f"✅ Matches found: "
            f"{len(results)}",
            flush=True
        )

        if not results:

            await processing_message.edit_text(
                "❌ No Pantone matches found."
            )

            return

        # =================================================
        # CREATE COLOR CARD
        # =================================================

        print(
            "🖼 Creating MODEX color card...",
            flush=True
        )

        card = make_color_card(
            results
        )

        output = io.BytesIO()

        card.save(
            output,
            format="PNG"
        )

        output.seek(0)

        # =================================================
        # SEND COLOR CARD
        # =================================================

        await update.message.reply_photo(
            photo=output,
            caption="🎨 *MODEX COLOR CARD*",
            parse_mode="Markdown",
        )

        print(
            "✅ Color card sent",
            flush=True
        )

        # =================================================
        # BUILD RESULTS MESSAGE
        # =================================================

        text = (
            "🎨 *COLORS DETECTED*\n\n"
        )

        for index, (rgb, match) in enumerate(
            results,
            start=1
        ):

            pantone_name = match["name"]

            pantone_rgb = (
                match["r"],
                match["g"],
                match["b"],
            )

            pantone_hex = rgb_to_hex(
                pantone_rgb
            )

            distance = match["distance"]

            # Save to history
            save_history(
                update.effective_user.id,
                "IMAGE",
                str(rgb),
                pantone_name,
                pantone_rgb,
            )

            text += (
                f"{index}. "
                f"*{pantone_name}* — "
                f"`{pantone_hex}` — "
                f"distance `{distance:.2f}`\n"
            )

        text += (
            "\n⚠️ *Digital approximation* — "
            "verify with physical swatches "
            "before production."
        )

        # -------------------------------------------------
        # REMOVE PROCESSING MESSAGE
        # -------------------------------------------------

        try:

            await processing_message.delete()

        except Exception:

            pass

        # =================================================
        # SEND RESULTS
        # =================================================

        await update.message.reply_text(
            text,
            parse_mode="Markdown"
        )

        # Clear mode after successful image
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
            "❌ PHOTO PROCESSING ERROR",
            flush=True
        )

        print(
            f"❌ {type(e).__name__}: {e}",
            flush=True
        )

        traceback.print_exc()

        try:

            error_text = (
                "❌ *Something went wrong "
                "while processing the image.*\n\n"
                f"`{type(e).__name__}: {e}`"
            )

            if processing_message:

                await processing_message.edit_text(
                    error_text,
                    parse_mode="Markdown"
                )

            else:

                await update.message.reply_text(
                    error_text,
                    parse_mode="Markdown"
                )

        except Exception as send_error:

            print(
                f"❌ Could not send error: "
                f"{send_error}",
                flush=True
            )


# =========================================================
# TEXT HANDLER
# =========================================================

async def handle_text(
    update,
    context
):

    text = update.message.text.strip()

    mode = context.user_data.get(
        "mode"
    )

    print(
        f"💬 TEXT RECEIVED: {text}",
        flush=True
    )

    # -----------------------------------------------------
    # HEX / TCX
    # -----------------------------------------------------

    if mode in (
        "hex",
        "tcx"
    ):

        await process_hex(
            update,
            context,
            text
        )

        context.user_data.pop(
            "mode",
            None
        )

        return

    # -----------------------------------------------------
    # RGB
    # -----------------------------------------------------

    if mode == "rgb":

        await process_rgb(
            update,
            context,
            text
        )

        context.user_data.pop(
            "mode",
            None
        )

        return

    # -----------------------------------------------------
    # CARD
    # -----------------------------------------------------

    if mode == "card":

        await update.message.reply_text(
            "🖼 Please send an image "
            "for the color card."
        )

        return

    # -----------------------------------------------------
    # AUTOMATIC HEX
    # -----------------------------------------------------

    if (
        text.startswith("#")
        or (
            len(text) in (6, 7)
            and all(
                c in
                "0123456789abcdefABCDEF"
                for c in text.lstrip("#")
            )
        )
    ):

        await process_hex(
            update,
            context,
            text
        )

        return

    # -----------------------------------------------------
    # AUTOMATIC RGB
    # -----------------------------------------------------

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
                    text
                )

                return

        except ValueError:

            pass

    # -----------------------------------------------------
    # UNKNOWN MESSAGE
    # -----------------------------------------------------

    await update.message.reply_text(

        "I didn't recognize that color.\n\n"

        "Try:\n"
        "`#FF0000`\n"
        "`255 0 0`\n\n"

        "Or simply send me an image.",

        parse_mode="Markdown",

        reply_markup=main_menu(),
    )


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(
    update,
    context
):

    query = update.callback_query

    await query.answer()

    data = query.data

    print(
        f"🔘 BUTTON: {data}",
        flush=True
    )

    # -----------------------------------------------------
    # HEX
    # -----------------------------------------------------

    if data == "hex":

        context.user_data["mode"] = "hex"

        await query.message.reply_text(

            "🔢 Send a HEX color.\n\n"

            "Example:\n"
            "`#FF0000`",

            parse_mode="Markdown"
        )

    # -----------------------------------------------------
    # RGB
    # -----------------------------------------------------

    elif data == "rgb":

        context.user_data["mode"] = "rgb"

        await query.message.reply_text(

            "🌈 Send RGB values.\n\n"

            "Example:\n"
            "`255 0 0`",

            parse_mode="Markdown"
        )

    # -----------------------------------------------------
    # TCX
    # -----------------------------------------------------

    elif data == "tcx":

        context.user_data["mode"] = "tcx"

        await query.message.reply_text(

            "👕 *TCX MATCH*\n\n"

            "Send a HEX color.\n\n"

            "Example:\n"
            "`#C6233A`",

            parse_mode="Markdown"
        )

    # -----------------------------------------------------
    # CARD
    # -----------------------------------------------------

    elif data == "card":

        context.user_data["mode"] = "card"

        await query.message.reply_text(

            "🖼 *COLOR CARD*\n\n"

            "Send an image and I'll generate "
            "a Pantone color card.",

            parse_mode="Markdown"
        )

    # -----------------------------------------------------
    # HISTORY
    # -----------------------------------------------------

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
                created_at
            ) = row

            text += (
                f"• `{input_value}` → "
                f"*{pantone_name}*\n"
                f"  {created_at}\n\n"
            )

        await query.message.reply_text(
            text,
            parse_mode="Markdown"
        )

    # -----------------------------------------------------
    # SETTINGS
    # -----------------------------------------------------

    elif data == "settings":

        await query.message.reply_text(

            "⚙️ *SETTINGS*\n\n"

            "Color matching: Lab distance\n"
            "Image extraction: 4 dominant colors\n"
            "Palette: Local dataset\n\n"

            "⚠️ Digital approximation.",

            parse_mode="Markdown"
        )

    # -----------------------------------------------------
    # HELP
    # -----------------------------------------------------

    elif data == "help":

        await query.message.reply_text(

            "❓ *HOW TO USE MODEX PANTONE*\n\n"

            "📸 Simply send an image.\n"
            "No button required.\n\n"

            "You can also send:\n"
            "• HEX\n"
            "• RGB\n\n"

            "Commands:\n"
            "`/hex`\n"
            "`/rgb`\n"
            "`/tcx`\n"
            "`/card`\n"
            "`/history`\n"
            "`/settings`\n"
            "`/help`",

            parse_mode="Markdown"
        )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context
):

    print(
        "❌ TELEGRAM ERROR",
        flush=True
    )

    print(
        f"❌ "
        f"{type(context.error).__name__}: "
        f"{context.error}",
        flush=True
    )

    traceback.print_exception(
        type(context.error),
        context.error,
        context.error.__traceback__,
    )


# =========================================================
# MAIN
# =========================================================

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

    # -----------------------------------------------------
    # DATABASE
    # -----------------------------------------------------

    init_db()

    # -----------------------------------------------------
    # TELEGRAM APPLICATION
    # -----------------------------------------------------

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(set_commands)
        .build()
    )

    # -----------------------------------------------------
    # COMMAND HANDLERS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # BUTTONS
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # -----------------------------------------------------
    # PHOTOS
    # -----------------------------------------------------

    # IMPORTANT:
    # Any photo sent to the bot automatically
    # goes through Pantone image matching.
    #
    # User does NOT need to click a button first.

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    # -----------------------------------------------------
    # TEXT
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    # -----------------------------------------------------
    # ERRORS
    # -----------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    print(
        "🤖 Telegram bot is running...",
        flush=True
    )

    print(
        "📸 Direct image matching: ENABLED",
        flush=True
    )

    print(
        "🎨 Automatic color card: ENABLED",
        flush=True
    )

    print(
        "📜 History: ENABLED",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    # -----------------------------------------------------
    # START POLLING
    # -----------------------------------------------------

    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()