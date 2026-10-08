# MODEX PANTONE BOT — @modexpantonebot

A Telegram MVP for matching image/HEX/RGB colors against a local Pantone-style palette and generating visual color tiles/cards.

## What it does

- Button-based Telegram interface
- Image → dominant colors → nearest palette matches
- HEX → nearest palette match
- RGB → nearest palette match
- TCX collection filter
- PNG color tile generation
- Multi-color PNG color cards
- SQLite match history
- Designed so an authorized Pantone dataset can replace the demo CSV

## Important

The included `pantone_colors.csv` is only a tiny DEMO palette for testing the bot.

It is NOT an official Pantone database. Do not represent the demo results as official Pantone matches.

For production, use a Pantone dataset/API you are legally authorized to use. The bot's matching engine expects:

name,r,g,b,collection,description

## Setup

Python 3.10+ recommended.

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

Set your Telegram token:

```bash
# Linux/macOS
export BOT_TOKEN="YOUR_TOKEN"

# Windows PowerShell
$env:BOT_TOKEN="YOUR_TOKEN"
```

Run:

```bash
python bot.py
```

## Bot flow

/start
  ↓
Buttons
  ↓
Image / HEX / RGB
  ↓
RGB conversion
  ↓
CIE Lab
  ↓
nearest-color distance
  ↓
generated PNG tile/card
  ↓
Telegram

## Production improvements

1. Replace the demo CSV with an authorized Pantone dataset/API.
2. Add proper Delta E 2000 instead of the simple Lab Euclidean distance.
3. Add CMYK input.
4. Add Pantone → HEX/RGB conversion.
5. Add PDF color-card export.
6. Add project/techpack storage.
7. Add user-specific saved palettes.
8. Add batch image processing.


## Native Telegram command menu

The bot registers `/start`, `/settings`, `/hex`, `/image`, `/rgb`, `/cmyk`, `/tcx`, `/card`, `/history`, and `/help` with Telegram. These appear in Telegram's native bot menu (☰) after the bot starts.
