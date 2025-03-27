# utils.py
import time
import requests
import json
import sys
from tkinter import messagebox, TclError
# import tkinter # No longer needed
import os
import re
import customtkinter as ctk

# Import config constants and filter mappings
from config import (
    AITEXT_FILENAME, BASE_REVIEW_DIR, STEAM_LANGUAGES, STEAM_REVIEW_TYPES,
    STEAM_PURCHASE_TYPES, STEAM_DATE_RANGES, STEAM_PLAYTIME_FILTERS,
    STEAM_FILTER_BY
)

# --- Logging (Unchanged) ---
def log_message(root, log_box, message):
    log_entry = f"{time.strftime('%H:%M:%S')} - {message}\n"
    try: # noqa
        if root and root.winfo_exists() and log_box and log_box.winfo_exists(): log_box.configure(state="normal"); log_box.insert("end", log_entry); log_box.see("end"); log_box.configure(state="disabled"); # noqa
        else: print(f"Log (GUI N/A): {message}") # noqa
    except TclError as e: print(f"Log (TclError): {message} - {e}") # noqa
    except Exception as e: print(f"Error logging message: {e}\nOriginal: {message}", file=sys.stderr) # noqa


# --- Configuration Loading (Unchanged) ---
def load_config_from_file(log_func):
    loaded_api_key = ""
    loaded_default_prompt = ""
    try:
        with open(AITEXT_FILENAME, 'r', encoding='utf-8') as f:
            api_key_line = f.readline().strip()
            if api_key_line and api_key_line != "YOUR_VALID_GEMINI_API_KEY_PLACEHOLDER":
                loaded_api_key = api_key_line
                log_func("Loaded API Key.")
            elif api_key_line == "YOUR_VALID_GEMINI_API_KEY_PLACEHOLDER":
                log_func("Warn: Using placeholder API Key from AITEXT.txt.")
            else:
                log_func("Warn: API Key line empty in AITEXT.txt.")
            loaded_default_prompt = f.read().strip()
            if loaded_default_prompt:
                log_func("Loaded default prompt.")
            else:
                log_func("No default prompt found in AITEXT.txt.")
    except FileNotFoundError:
        log_func(f"Warn: Config file '{AITEXT_FILENAME}' not found. Using defaults/placeholders.")
    except IOError as e: log_func(f"Error reading {AITEXT_FILENAME}: {e}.") # noqa
    except Exception as e: log_func(f"Unexpected error loading config: {e}.") # noqa
    return loaded_api_key, loaded_default_prompt


# --- Steam API Helper (Unchanged) ---
def fetch_game_name(app_id, log_func):
    if not app_id or not app_id.isdigit(): log_func("Invalid App ID for fetching game name."); return None; # noqa
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"; log_func(f"Fetching name for ID: {app_id}..."); headers = {'User-Agent': 'SteamReviewAnalyzer/1.0'}; # noqa
    try: response = requests.get(url, timeout=15, headers=headers); response.raise_for_status(); data = response.json(); # noqa
    except requests.exceptions.Timeout: log_func(f"Timeout fetching name for App ID {app_id}."); messagebox.showerror("API Error", "Timeout fetching game name from Steam API."); return None; # noqa
    except requests.exceptions.RequestException as e: log_func(f"Network error fetching game name: {e}"); messagebox.showerror("API Error", f"Network error fetching game name: {e}"); return None; # noqa
    except json.JSONDecodeError: log_func("JSON decode error fetching game name."); messagebox.showerror("API Error", "Invalid API response (game name)."); return None; # noqa
    except Exception as e: log_func(f"Unexpected error fetching game name: {e}"); messagebox.showerror("Error", f"Unexpected error fetching game name: {e}"); return None; # noqa
    if not isinstance(data, dict) or app_id not in data or not isinstance(data[app_id], dict): log_func(f"Unexpected API structure for App ID {app_id} (name fetch)."); return None; # noqa
    app_data = data[app_id]; # noqa
    if app_data.get('success') is True and 'data' in app_data and isinstance(app_data['data'], dict) and 'name' in app_data['data']: name = app_data['data']['name']; log_func(f"Fetched game name: {name}"); return name; # noqa
    else: log_func(f"Could not find name for App ID {app_id}. Success: {app_data.get('success', 'N/A')}."); messagebox.showwarning("API Warning", f"Could not fetch game name for App ID {app_id}.\nCheck if the ID is correct."); return None; # noqa


# --- Filesystem Helpers (Unchanged) ---
def sanitize_filename(name):
    if not name: return "_invalid_name_"; # noqa
    sanitized = re.sub(r'[<>:"/\\|?*\'\.]', '_', name); sanitized = re.sub(r'_+', '_', sanitized); sanitized = sanitized.strip('_ '); # noqa
    if not sanitized or sanitized == '.' or sanitized == '..': return "_invalid_name_"; # noqa
    return sanitized


# --- Token Estimation (Unchanged) ---
def _estimate_tokens(text):
    """Roughly estimates token count (1 token ~ 4 characters)."""
    if not text: return 0
    return len(text) // 4

def calculate_and_format_token_estimates(game_name, steam_id, log_func):
    """Reads review files and returns formatted token estimate string and raw numbers."""
    orig_tokens = None; opt_tokens = None; display_text = "Token Estimates: N/A"; # noqa

    if not game_name or not steam_id or not steam_id.isdigit():
        # Don't log error here, just return default. Calling context should decide if error.
        return display_text, orig_tokens, opt_tokens # Return N/A and None

    sanitized_name = sanitize_filename(game_name)
    if sanitized_name == "_invalid_name_":
        log_func("Cannot calculate tokens: Invalid sanitized game name.")
        return display_text, orig_tokens, opt_tokens

    folder_name = f"{sanitized_name}_{steam_id}"
    try:
        base_dir_path = os.path.abspath(BASE_REVIEW_DIR)
        game_folder_path = os.path.join(base_dir_path, folder_name)
    except Exception as e:
         log_func(f"Error constructing game folder path for token calc: {e}")
         return display_text, orig_tokens, opt_tokens

    orig_file = os.path.join(game_folder_path, f"{folder_name}_reviews.txt")
    opt_file = os.path.join(game_folder_path, f"{folder_name}_reviews_optimized.txt")

    # Estimate Original
    if os.path.exists(orig_file):
        try:
            with open(orig_file, 'r', encoding='utf-8') as f: content = f.read()
            orig_tokens = _estimate_tokens(content)
        except Exception as e: log_func(f"Warn: Error estimating tokens for original file: {e}") # noqa
    # else: log_func(f"Info: Original file not found for token count: {os.path.basename(orig_file)}") # Less verbose

    # Estimate Optimized
    if os.path.exists(opt_file):
        try:
            with open(opt_file, 'r', encoding='utf-8') as f: content = f.read()
            opt_tokens = _estimate_tokens(content)
        except Exception as e: log_func(f"Warn: Error estimating tokens for optimized file: {e}") # noqa
    # else: log_func(f"Info: Optimized file not found for token count: {os.path.basename(opt_file)}") # Less verbose

    # Format Display String
    orig_str = f"~{orig_tokens:,}" if orig_tokens is not None else "N/A"
    opt_str = f"~{opt_tokens:,}" if opt_tokens is not None else "N/A"
    display_text = f"Orig. Tokens: {orig_str} | Opt. Tokens: {opt_str}"

    return display_text, orig_tokens, opt_tokens


# --- GUI Interaction Helpers ---

def get_settings(widgets, defaults, log_func):
    """Retrieves all settings from GUI widgets, including new filters."""
    settings = defaults.copy() # Start with defaults

    # --- Helper functions for validation (moved inside) ---
    def validate_int(widget_key, setting_key, default, min_v, max_v, name):
        entry = widgets.get(widget_key)
        try:
            val = int(entry.get())
            if not (min_v <= val <= (max_v if max_v is not None else float('inf'))):
                 raise ValueError(f"Value out of range [{min_v}-{max_v or 'inf'}]")
            settings[setting_key] = val
        except (ValueError, TclError, AttributeError, TypeError) as e:
            log_func(f"Invalid {name} ('{entry.get() if entry else 'N/A'}'). Using default {default}. Error: {e}") # noqa
            # messagebox.showwarning("Settings Error", f"Invalid {name}. Using default: {default}.") # Less disruptive
            settings[setting_key] = default
            try: # Attempt to reset GUI entry
                if entry and entry.winfo_exists(): entry.delete(0, "end"); entry.insert(0, str(default)); # noqa
            except Exception: pass

    def validate_float(widget_key, setting_key, default, min_v, name):
        entry = widgets.get(widget_key)
        try:
            val = float(entry.get())
            if not (val >= min_v): raise ValueError(f"Value must be >= {min_v}")
            settings[setting_key] = val
        except (ValueError, TclError, AttributeError, TypeError) as e:
            log_func(f"Invalid {name} ('{entry.get() if entry else 'N/A'}'). Using default {default}. Error: {e}") # noqa
            # messagebox.showwarning("Settings Error", f"Invalid {name}. Using default: {default}.") # Less disruptive
            settings[setting_key] = default
            try: # Attempt to reset GUI entry
                if entry and entry.winfo_exists(): entry.delete(0, "end"); entry.insert(0, str(default)); # noqa
            except Exception: pass

    # --- Validate General Settings ---
    validate_int('max_reviews_entry', 'max_reviews', defaults['max_reviews'], 1, None, "Max Reviews") # noqa
    validate_int('token_threshold_entry', 'token_threshold', defaults['token_threshold'], 1, None, "Token Threshold") # noqa
    validate_float('sleep_duration_entry', 'sleep_duration', defaults['sleep_duration'], 0.0, "Sleep Duration") # noqa
    validate_int('num_per_page_entry', 'num_per_page', defaults['num_per_page'], 1, 100, "# Reviews Per Page") # noqa

    # --- Get Steam Filter Settings ---
    try:
        # Language (ComboBox) - Map display name to API value
        lang_widget = widgets.get('filter_language_combo')
        selected_lang_display = lang_widget.get() if lang_widget else list(STEAM_LANGUAGES.keys())[0] # Default display
        settings['steam_language'] = STEAM_LANGUAGES.get(selected_lang_display, defaults['steam_language']) # Get API value

        # Review Type (OptionMenu) - Map display name to API value
        type_widget = widgets.get('filter_review_type_option')
        selected_type_display = type_widget.get() if type_widget else list(STEAM_REVIEW_TYPES.keys())[0]
        settings['steam_review_type'] = STEAM_REVIEW_TYPES.get(selected_type_display, defaults['steam_review_type'])

        # Purchase Type (OptionMenu) - Map display name to API value
        purchase_widget = widgets.get('filter_purchase_type_option')
        selected_purchase_display = purchase_widget.get() if purchase_widget else list(STEAM_PURCHASE_TYPES.keys())[0]
        settings['steam_purchase_type'] = STEAM_PURCHASE_TYPES.get(selected_purchase_display, defaults['steam_purchase_type'])

        # Date Range (OptionMenu) - Map display name to API value
        date_widget = widgets.get('filter_date_range_option')
        selected_date_display = date_widget.get() if date_widget else list(STEAM_DATE_RANGES.keys())[0]
        settings['steam_date_range'] = STEAM_DATE_RANGES.get(selected_date_display, defaults['steam_date_range'])

        # Playtime (OptionMenu) - Map display name to API value
        playtime_widget = widgets.get('filter_playtime_option')
        selected_playtime_display = playtime_widget.get() if playtime_widget else list(STEAM_PLAYTIME_FILTERS.keys())[0]
        settings['steam_playtime'] = STEAM_PLAYTIME_FILTERS.get(selected_playtime_display, defaults['steam_playtime'])

        # Filter By (OptionMenu) - Map display name to API value
        filterby_widget = widgets.get('filter_filter_by_option')
        selected_filterby_display = filterby_widget.get() if filterby_widget else list(STEAM_FILTER_BY.keys())[0]
        settings['steam_filter_by'] = STEAM_FILTER_BY.get(selected_filterby_display, defaults['steam_filter_by'])

        # Beta/Early Access (Checkbox) - Get 0 or 1
        beta_widget = widgets.get('filter_beta_checkbox')
        # Check if widget exists and get its value (0 or 1)
        if beta_widget and hasattr(beta_widget, 'get'):
             settings['steam_beta'] = str(beta_widget.get()) # Ensure it's '0' or '1' string for API?
        else:
             settings['steam_beta'] = defaults['steam_beta'] # Fallback to default

    except Exception as e:
        log_func(f"Error reading filter settings from GUI: {e}. Using defaults for filters.")
        # Reset filter settings to default if error occurs
        settings['steam_language'] = defaults['steam_language']
        settings['steam_review_type'] = defaults['steam_review_type']
        settings['steam_purchase_type'] = defaults['steam_purchase_type']
        settings['steam_date_range'] = defaults['steam_date_range']
        settings['steam_playtime'] = defaults['steam_playtime']
        settings['steam_filter_by'] = defaults['steam_filter_by']
        settings['steam_beta'] = defaults['steam_beta']
        # Optionally reset the GUI elements themselves here if desired

    # log_func(f"Retrieved Settings: {settings}") # Debugging log
    return settings


# set_widget_state remains in gui_manager.py now.
# Remove it from here.
# def set_widget_state(widgets_list, state): ... (REMOVED)