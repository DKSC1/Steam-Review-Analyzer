# config.py
import sys

# --- File Configuration ---
AITEXT_FILENAME = "AITEXT.txt"
BASE_REVIEW_DIR = "Games_Reviews" # Main directory for all game data

# --- API Configuration ---
API_KEY = "YOUR_VALID_GEMINI_API_KEY_PLACEHOLDER"

# --- Model Definitions ---
SUPPORTED_MODELS = [
    {"name": "Gemini 2.5 Pro Exp 03-25", "id": "gemini-2.5-pro-exp-03-25"},
    {"name": "Gemini 2.0 Flash Thinking Exp", "id": "gemini-2.0-flash-thinking-exp-01-21"},
    {"name": "Gemini 2.0 Flash 001 (Alias)", "id": "gemini-2.0-flash-001"},
    {"name": "Gemini 2.0 Flash", "id": "gemini-2.0-flash"},
    {"name": "Gemini 2.0 Flash Lite 001 (Alias)", "id": "gemini-2.0-flash-lite-001"},
    {"name": "Gemini 2.0 Flash Lite", "id": "gemini-2.0-flash-lite"},
    {"name": "Gemini 1.5 Pro", "id": "gemini-1.5-pro-latest"},
    {"name": "Gemini 1.5 Flash", "id": "gemini-1.5-flash-latest"},
]
if not SUPPORTED_MODELS:
    print("Error: config.py - SUPPORTED_MODELS list cannot be empty!", file=sys.stderr)

# --- Steam Filter Options ---
# (Values should correspond to Steam API parameter values)
STEAM_LANGUAGES = {
    "All Languages": "all", "English": "english", "German": "german",
    "French": "french", "Spanish - Spain": "spanish", "Russian": "russian",
    "Simplified Chinese": "schinese", "Portuguese - Brazil": "brazilian",
    "Japanese": "japanese", "Korean": "koreana", "Polish": "polish",
    # Add more as needed...
}
STEAM_REVIEW_TYPES = {"All": "all", "Positive Only": "positive", "Negative Only": "negative"}
STEAM_PURCHASE_TYPES = {"All": "all", "Steam Purchasers": "steam", "Other Keys/Retail": "non_steam_purchase"}
STEAM_DATE_RANGES = { # Display Name: API Value (days, 0=all)
    "All Time": "0", "Last 24 hours": "1", "Last 7 days": "7",
    "Last 30 days": "30", "Last 90 days": "90", "Last 365 days": "365"
}
STEAM_PLAYTIME_FILTERS = { # Display Name: API Value (min hours, 0=any)
    "Any": "0", "Over 1 hour": "1", "Over 10 hours": "10",
    "Over 100 hours": "100", "Over 1000 hours": "1000"
}
STEAM_FILTER_BY = { # Display Name: API Value ('filter' parameter)
    "Most Helpful (Default)": "all", # 'all' often defaults to helpfulness sort
    "Recent": "recent",
    "Recently Updated": "updated"
}


# --- Default Settings ---
DEFAULT_SETTINGS = {
    # Scraping General
    'max_reviews': 30000,
    'sleep_duration': 1.5,
    'num_per_page': 100,
    # Optimization
    'token_threshold': 950000,
    # --- NEW Steam Filter Defaults ---
    'steam_language': "all", # API value
    'steam_review_type': "all", # API value
    'steam_purchase_type': "all", # API value
    'steam_date_range': "0", # API value (days)
    'steam_playtime': "0", # API value (min hours)
    'steam_filter_by': "all", # API value ('filter' parameter)
    'steam_beta': "0", # API value ('review_beta_enabled') 0=No, 1=Yes
}

DEFAULT_MULTILINE_PROMPT = ""

# --- Appearance ---
APPEARANCE_MODE = "System"
COLOR_THEME = "blue"