# actions.py
import subprocess
import os
import shutil
import re
import json
import csv
import requests
from tkinter import messagebox
import sys
import time
import io
import traceback

# --- Dependencies ---
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: 'pandas' library not found. XLSX generation will be skipped.", file=sys.stderr)
    print("Install using: pip install pandas openpyxl", file=sys.stderr)

# --- Local Imports ---
from config import BASE_REVIEW_DIR
from utils import sanitize_filename

# --- XLSX Generation ---
def generate_xlsx_from_csv(csv_filepath, xlsx_filepath, log_func):
    """Reads a CSV and generates an XLSX file using pandas."""
    if not PANDAS_AVAILABLE:
        log_func("XLSX generation skipped: pandas library not available.")
        return False

    if not os.path.exists(csv_filepath):
        log_func(f"XLSX generation skipped: CSV file '{csv_filepath}' not found.")
        return False

    log_func(f"Generating XLSX from '{os.path.basename(csv_filepath)}'...")
    try:
        df = pd.read_csv(csv_filepath)
        with pd.ExcelWriter(xlsx_filepath, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            # Auto-adjust column widths
            for column in df:
                try: # Inner try for column adjustment
                    column_length = max(df[column].astype(str).map(len).max(), len(column))
                    col_idx = df.columns.get_loc(column)
                    col_letter = writer.sheets['Sheet1'].cell(row=1, column=col_idx + 1).column_letter
                    adjusted_width = min(max(column_length * 1.2, 10), 60)
                    writer.sheets['Sheet1'].column_dimensions[col_letter].width = adjusted_width
                except Exception as col_e:
                    log_func(f"Warning: Could not auto-adjust width for column '{column}': {col_e}")
                    # Safely attempt fallback width setting
                    try:
                         col_idx = df.columns.get_loc(column)
                         col_letter = writer.sheets['Sheet1'].cell(row=1, column=col_idx + 1).column_letter
                         writer.sheets['Sheet1'].column_dimensions[col_letter].width = 20
                    except Exception:
                         pass # Ignore if even fallback fails

        log_func(f"Successfully generated XLSX file: '{xlsx_filepath}'.")
        return True
    except FileNotFoundError:
        log_func(f"Error generating XLSX: Input CSV '{csv_filepath}' disappeared.")
        messagebox.showerror("XLSX Error", f"Could not find CSV to create XLSX:\n{csv_filepath}")
        return False
    except ImportError:
        log_func("Error generating XLSX: pandas or openpyxl missing.")
        messagebox.showerror("XLSX Error", "Install libraries: pip install pandas openpyxl")
        return False
    except Exception as e:
        log_func(f"Error generating XLSX file '{xlsx_filepath}': {e}")
        log_func(f"Traceback: {traceback.format_exc()}")
        messagebox.showerror("XLSX Error", f"Failed to generate XLSX file:\n{e}")
        return False


# --- Helper: Get Game Folder Path ---
def get_game_folder_path(game_name, steam_id, log_func):
    """Constructs and ensures the game-specific folder path exists."""
    if not game_name or not steam_id or not steam_id.isdigit():
        log_func("Error: Cannot get folder path without Game Name/ID.")
        return None

    sanitized_name = sanitize_filename(game_name)
    if sanitized_name == "_invalid_name_":
        log_func(f"Error: Invalid sanitized name '{game_name}'.")
        return None

    folder_name = f"{sanitized_name}_{steam_id}"
    game_folder_path = None
    try:
        base_dir_path = os.path.abspath(BASE_REVIEW_DIR)
        game_folder_path = os.path.join(base_dir_path, folder_name)
        os.makedirs(game_folder_path, exist_ok=True)
        return game_folder_path
    except OSError as e:
        log_func(f"Error creating directory '{game_folder_path}': {e}")
        messagebox.showerror("Directory Error", f"Could not create directory:\n{e}")
        return None
    except Exception as e:
         log_func(f"Unexpected error getting game folder path: {e}")
         return None


# --- Subprocess Execution: Scraping ---
def run_scraping(root, widgets, settings_func, log_func):
    """Gets inputs, creates folder, runs reviews.py, updates progress, moves output."""
    settings = settings_func()
    game_name = widgets['game_name_entry'].get().strip()
    steam_app_id = widgets['steam_id_entry'].get().strip()

    if not steam_app_id or not steam_app_id.isdigit() or not game_name:
        messagebox.showwarning("Input Error", "Please enter a valid Game Name and Steam ID.")
        return False

    game_folder_path = get_game_folder_path(game_name, steam_app_id, log_func)
    if not game_folder_path:
        return False

    script_path = 'reviews.py'
    temp_output_file = 'reviews.txt'
    target_output_file = os.path.join(game_folder_path, f"{os.path.basename(game_folder_path)}_reviews.txt")

    log_func(f"Starting scraping for App ID: {steam_app_id} ('{game_name}')...")
    log_func(f"Target Folder: {game_folder_path}")
    log_func(f"Settings: Max={settings['max_reviews']}, NumPerPage={settings['num_per_page']}, Sleep={settings['sleep_duration']}s")

    progress_bar = widgets.get('progress_bar')
    progress_label = widgets.get('scrape_progress_label')

    # Setup Progress Updates safely
    max_reviews_target = settings['max_reviews']
    current_reviews_scraped = 0
    try:
        if progress_label:
            progress_label.configure(text=f"Scraping: 0 / {max_reviews_target}")
        if progress_bar:
            progress_bar.set(0)
            if hasattr(progress_bar, 'master') and progress_bar.master:
                 progress_bar.master.grid()
                 progress_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
            else:
                 log_func("Warn: Progress bar master widget not found.")
        if root and root.winfo_exists():
            root.update_idletasks()
    except Exception as gui_e:
        log_func(f"Warn: Error setting up progress display: {gui_e}")

    process = None
    success_flag = False
    full_stderr = ""

    try: # Outer try for overall process setup and execution
        # --- Pre-checks ---
        if not os.path.exists(script_path):
            log_func(f"Error: Script '{script_path}' not found.")
            messagebox.showerror("File Error", f"'{script_path}' script not found.")
            return False # Critical failure, cannot continue

        if os.path.exists(target_output_file):
            if not messagebox.askyesno("File Exists", f"'{os.path.basename(target_output_file)}' exists.\nOverwrite?", icon='warning'):
                log_func("Scraping cancelled."); return False # User cancel # noqa
            else:
                log_func(f"Confirmed overwrite for '{os.path.basename(target_output_file)}'.")

        command = [ sys.executable, script_path, '--max', str(settings['max_reviews']), '--sleep', str(settings['sleep_duration']), '--num', str(settings['num_per_page']) ]
        log_func(f"Running command: {' '.join(command)}")

        # Clean temp file
        if os.path.exists(temp_output_file):
             try:
                 os.remove(temp_output_file)
             except OSError as remove_e:
                 log_func(f"Warn: Could not remove old temp file: {remove_e}")
                 # Continue anyway

        # --- Popen Call ---
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding=None, cwd=os.path.dirname(sys.argv[0]) or '.', creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0) # noqa
        except Exception as popen_e:
            log_func(f"Error starting subprocess: {popen_e}\n{traceback.format_exc()}"); messagebox.showerror("Execution Error", f"Failed start script:\n{popen_e}"); return False # noqa

        # --- Send Input to Subprocess ---
        try:
            if process.stdin:
                 app_id_bytes = (steam_app_id + "\n").encode('utf-8'); process.stdin.write(app_id_bytes); process.stdin.close(); # noqa
            else:
                 # This case means Popen likely failed silently before, raise error
                 raise OSError("Process stdin stream unavailable immediately after Popen.")
        except (OSError, ValueError, TypeError) as stdin_e:
             log_func(f"Error writing stdin: {stdin_e}")
             # Try killing the process if it exists and might be running
             if process and process.poll() is None:
                 try: process.kill()
                 except Exception: pass # Explicitly pass on kill error
             return False # Can't proceed

        # --- Read Output Stream ---
        if process.stdout:
            # Use a separate try block for reading stdout
            try:
                stdout_reader = io.TextIOWrapper(process.stdout, encoding='utf-8', errors='replace')
                while True:
                    line = stdout_reader.readline()
                    if not line and process.poll() is not None:
                        break # Process ended and no more data
                    if line:
                        line_strip = line.strip()
                        log_func(f"SCRIPT: {line_strip}")

                        match = re.search(r'Total so far:\s*(\d+)', line_strip, re.IGNORECASE)
                        if match:
                            # Inner try specifically for GUI updates
                            try:
                                current_reviews_scraped = int(match.group(1))
                                if progress_label: progress_label.configure(text=f"Scraping: {current_reviews_scraped} / {max_reviews_target}") # noqa
                                if progress_bar: progress_value = min(1.0, current_reviews_scraped / max_reviews_target) if max_reviews_target > 0 else 0; progress_bar.set(progress_value) # noqa
                                if root and root.winfo_exists(): root.update_idletasks() # noqa
                            except ValueError:
                                log_func("Warn: Cannot parse progress number.")
                                pass # Continue reading lines
                            except Exception as e_update:
                                log_func(f"Warn: Error updating progress GUI: {e_update}")
                                pass # Continue reading lines
            except Exception as read_e:
                 log_func(f"Error reading script output: {read_e}")
                 # Continue to wait/check return code below
        else:
             log_func("Error: Process stdout stream unavailable.")
             # Still wait for process below

        # --- Wait for Process and Check Results ---
        return_code = -99 # Default unknown code
        try:
             return_code = process.wait(timeout=60)
        except subprocess.TimeoutExpired:
             log_func("Warn: Process final wait timeout.")
             return_code = -1 # Indicate timeout state
             if process and process.poll() is None: # Check again before killing
                 try: process.kill()
                 except Exception: pass # Ignore kill error
        except Exception as wait_e:
             log_func(f"Error waiting for process: {wait_e}")
             return_code = -2 # Indicate wait error

        # Read any remaining stderr after process completion
        if process.stderr:
            try:
                stderr_reader = io.TextIOWrapper(process.stderr, encoding='utf-8', errors='replace')
                full_stderr = stderr_reader.read()
                if full_stderr:
                    log_func("Scraping Script Errors/Warnings:\n" + full_stderr)
            except Exception as stderr_e:
                 log_func(f"Error reading stderr after process completion: {stderr_e}")
                 pass # Continue despite stderr read error

        # --- Process Results Based on Return Code ---
        if return_code != 0:
             log_func(f"Scraping process failed (Return Code: {return_code}).")
             messagebox.showerror("Scraping Error", f"reviews.py failed (Code: {return_code}). Check logs.\n{full_stderr[:200]}...")
             if progress_bar:
                 try: progress_bar.set(0) # Reset bar on error
                 except Exception: pass # Ignore GUI errors here
             success_flag = False # Failed
        else:
             # Process finished successfully
             log_func("Scraping script finished successfully (Return Code: 0).")
             # Final GUI update for success state
             try:
                 if progress_label: progress_label.configure(text=f"Scraped: {current_reviews_scraped}") # noqa
                 if progress_bar: progress_bar.set(1.0) # noqa
                 if root and root.winfo_exists(): root.update_idletasks() # noqa
             except Exception as gui_e:
                 log_func(f"Warn: Error in final success GUI update: {gui_e}")
                 pass # Continue processing file

             # Move output file - this determines final success
             if os.path.exists(temp_output_file):
                 try:
                     shutil.move(temp_output_file, target_output_file)
                     log_func(f"Saved scraped reviews to: '{target_output_file}'.")
                     success_flag = True # SUCCESS
                 except OSError as e:
                      log_func(f"Error moving '{temp_output_file}' to '{target_output_file}': {e}")
                      messagebox.showerror("File Error", f"Could not save scraped file:\n{e}")
                      success_flag = False # Move failed
             else:
                 log_func(f"Warning: Script OK, but temp file '{temp_output_file}' was not found.")
                 if not full_stderr:
                     messagebox.showwarning("File Warning", f"Scraping OK, but '{temp_output_file}' not created.")
                 success_flag = False # Output missing

    # --- Outer Exception Catch-all ---
    except FileNotFoundError as fnf_e:
        # This catches if 'python' itself isn't found
        log_func(f"File Not Found Error during setup: {fnf_e}")
        messagebox.showerror("Execution Error", f"File not found: {fnf_e}")
        success_flag = False
    except Exception as e:
        # Catch any other unexpected errors during setup or Popen etc.
        log_func(f"Unexpected error during scraping execution: {e}")
        log_func(f"Traceback: {traceback.format_exc()}")
        messagebox.showerror("Scraping Error", f"An unexpected error occurred: {e}")
        success_flag = False

    # --- Final Cleanup (Always runs) ---
    finally:
        # Close streams safely
        if process:
             try:
                 if process.stdout: process.stdout.close()
                 if process.stderr: process.stderr.close()
             except Exception:
                 pass # Ignore stream closing errors
        # Remove temp file if it still exists
        if os.path.exists(temp_output_file):
            try:
                os.remove(temp_output_file)
                log_func(f"Cleaned up temporary file: '{temp_output_file}'.")
            except OSError as e:
                log_func(f"Warning: Could not remove temp file '{temp_output_file}': {e}")
                pass # Continue cleanup
        # Hide progress bar and reset label safely
        if progress_bar and hasattr(progress_bar, 'master') and progress_bar.master:
            try:
                 if progress_bar.master.winfo_exists():
                    progress_bar.master.grid_remove()
                 progress_bar.set(0)
            except Exception:
                 pass # Ignore errors hiding progress bar
        if progress_label:
            try:
                if progress_label.winfo_exists():
                     progress_label.configure(text="Scraping: Idle")
            except Exception:
                 pass # Ignore errors resetting label

    return success_flag


# --- Subprocess Execution: Optimization ---
def run_optimization(widgets, settings_func, log_func):
    """Copies scraped file, runs optimize.py, moves output."""
    settings = settings_func()
    game_name = widgets['game_name_entry'].get().strip()
    steam_app_id = widgets['steam_id_entry'].get().strip()

    if not game_name or not steam_app_id or not steam_app_id.isdigit():
        messagebox.showwarning("Input Error", "Game Name and valid Steam ID required.")
        return False

    game_folder_path = get_game_folder_path(game_name, steam_app_id, log_func)
    if not game_folder_path:
        return False

    # Define paths
    scraped_source_file = os.path.join(game_folder_path, f"{os.path.basename(game_folder_path)}_reviews.txt")
    temp_input_file = "reviews.txt"
    temp_output_file = "reviews2.txt"
    optimized_target_file = os.path.join(game_folder_path, f"{os.path.basename(game_folder_path)}_reviews_optimized.txt")
    script_path = 'optimize.py'
    success_flag = False

    if not os.path.exists(scraped_source_file):
        log_func(f"Opt Error: Source '{os.path.basename(scraped_source_file)}' not found.")
        messagebox.showwarning("File Missing", f"Scraped file not found:\n{os.path.basename(scraped_source_file)}")
        return False

    if os.path.exists(optimized_target_file):
        if not messagebox.askyesno("File Exists", f"'{os.path.basename(optimized_target_file)}' exists.\nOverwrite?", icon='warning'):
            log_func("Opt cancelled.")
            return False
        else:
            log_func(f"Confirmed overwrite: {os.path.basename(optimized_target_file)}.")

    log_func("Optimizing...")
    # Prepare temporary input
    try:
        if os.path.exists(temp_input_file): os.remove(temp_input_file) # noqa
        if os.path.exists(temp_output_file): os.remove(temp_output_file) # noqa
        shutil.copyfile(scraped_source_file, temp_input_file)
        log_func(f"Copied source to temp '{temp_input_file}'.")
    except Exception as prep_e:
        log_func(f"Failed prep temp input: {prep_e}")
        messagebox.showerror("File Error", f"Could not copy source:\n{prep_e}")
        return False

    # Run optimize.py Subprocess
    process = None
    try: # Main try for subprocess execution
        if not os.path.exists(script_path):
            log_func(f"Error: Script '{script_path}' missing.")
            messagebox.showerror("File Error", f"'{script_path}' not found.")
            # Let finally clean up temp_input_file
        else:
            log_func(f"Token Threshold: {settings['token_threshold']}")
            command = [sys.executable, script_path, '--threshold', str(settings['token_threshold'])]
            log_func(f"Running: {' '.join(command)}")

            # Popen in its own try
            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', cwd=os.path.dirname(sys.argv[0]) or '.', creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0) # noqa
            except Exception as popen_e:
                 log_func(f"Error starting opt script: {popen_e}")
                 messagebox.showerror("Execution Error", f"Failed start optimize.py:\n{popen_e}")
                 # Let finally clean up

            if process: # Only proceed if Popen likely succeeded
                out, err = "", ""
                # Communicate in its own try
                try:
                    out, err = process.communicate(timeout=1800)
                except subprocess.TimeoutExpired:
                    log_func("Opt timed out!")
                    try: process.kill() # noqa
                    except Exception: pass # noqa
                    try: out, err = process.communicate() # Try get output # noqa
                    except Exception as comm_e: log_func(f"Error get output after timeout: {comm_e}") # noqa
                    messagebox.showerror("Timeout", "Opt timed out.")
                    # Let finally clean up, success_flag remains False
                except Exception as comm_e:
                     log_func(f"Error communicating with opt script: {comm_e}")
                     messagebox.showerror("Execution Error", f"Error running optimize.py:\n{comm_e}")
                     # Let finally clean up, success_flag remains False

                # Check results only if communicate finished or recovered output
                if process.returncode is not None:
                    if out: log_func(f"Opt Output:\n{out}") # noqa
                    if err: log_func(f"Opt Errors:\n{err}") # noqa
                    if process.returncode != 0:
                        log_func(f"Opt failed (Code: {process.returncode}).")
                        messagebox.showerror("Opt Error", f"optimize.py failed (Code: {process.returncode}).\n{err[:200]}...")
                        # success_flag remains False
                    else:
                        log_func("Opt script OK (Code: 0).")
                        if os.path.exists(temp_output_file):
                            try: # Move result file
                                shutil.move(temp_output_file, optimized_target_file)
                                log_func(f"Saved optimized: '{optimized_target_file}'.")
                                token_match=re.search(r"Approx.*?tokens kept:\s*(\d+)", out, re.IGNORECASE) # noqa
                                if token_match: log_func(f"Script tokens: {token_match.group(1)}") # noqa
                                success_flag = True # Set success only after move
                            except OSError as move_e:
                                log_func(f"Error moving opt file: {move_e}")
                                messagebox.showerror("File Error", f"Could not save opt file:\n{move_e}")
                                # success_flag remains False
                        else:
                            log_func(f"Warn: Script OK, but temp out '{temp_output_file}' missing.")
                            if not err: messagebox.showwarning("File Warning", f"Opt OK, but '{temp_output_file}' not created.") # noqa
                            # success_flag remains False
                else:
                     # This means communicate might have failed badly
                     log_func("Error: Opt process status unknown after execution attempt.")
                     # success_flag remains False

    # Outer exception handling
    except FileNotFoundError as fnf_e:
        log_func(f"Error: Python interpreter not found: {fnf_e}")
        messagebox.showerror("Execution Error", "Python interpreter not found.")
        success_flag = False
    except Exception as e:
        log_func(f"Unexpected opt error: {e}\n{traceback.format_exc()}")
        messagebox.showerror("Opt Error", f"Unexpected error: {e}")
        success_flag = False
    finally: # Final cleanup
        # Close streams
        if process:
            try: # noqa
                if process.stdout: process.stdout.close() # noqa
                if process.stderr: process.stderr.close() # noqa
            except Exception:
                pass
        # Clean temp input
        if os.path.exists(temp_input_file):
            try: os.remove(temp_input_file); log_func("Cleaned temp input.") # noqa
            except OSError as e: log_func(f"Warn: Could not remove temp input: {e}") # noqa
        # Clean temp output only if overall operation failed
        if os.path.exists(temp_output_file) and not success_flag:
            try: os.remove(temp_output_file); log_func("Cleaned temp output (as target not created).") # noqa
            except OSError as e: log_func(f"Warn: Could not remove temp output: {e}") # noqa

    return success_flag


# --- AI Interaction ---
def send_to_ai(widgets, api_key_func, models, log_func, use_optimized_file):
    """
    Sends chosen review file (optimized or original) to Gemini, with token warning.
    Saves modified text, extracts/saves CSV & XLSX.
    Returns tuple: (success_bool, csv_data_list_or_None, modified_full_text_or_None)
    """
    api_key = api_key_func()
    if not api_key or api_key == "YOUR_VALID_GEMINI_API_KEY_PLACEHOLDER":
         log_func("AI Error: API Key missing."); messagebox.showerror("API Key Error", "Valid API Key not loaded."); return False, None, None # noqa

    # Get Inputs
    selected_model_name = widgets['model_combobox'].get(); model_info = next((item for item in models if item["name"] == selected_model_name), None) # noqa
    if not model_info: log_func(f"AI Error: Model '{selected_model_name}' not found."); messagebox.showerror("Model Error", f"Model '{selected_model_name}' not found."); return False, None, None # noqa
    model_id, model_display_name = model_info['id'], model_info['name']
    query_text = widgets['ai_query_text'].get("1.0", "end-1c").strip()
    if not query_text: log_func("AI Error: Query empty."); messagebox.showwarning("Input Error", "Enter query."); return False, None, None # noqa
    game_name = widgets['game_name_entry'].get().strip(); steam_app_id = widgets['steam_id_entry'].get().strip() # noqa
    if not game_name or not steam_app_id or not steam_app_id.isdigit(): messagebox.showwarning("Input Error", "Game Name and valid Steam ID required."); return False, None, None # noqa

    # Get game folder path
    game_folder_path = get_game_folder_path(game_name, steam_app_id, log_func)
    if not game_folder_path: return False, None, None # noqa

    # Determine Input File based on flag
    folder_basename = os.path.basename(game_folder_path)
    if use_optimized_file:
        input_filename = os.path.join(game_folder_path, f"{folder_basename}_reviews_optimized.txt")
        file_description = "optimized review"
        log_func("Preparing to send OPTIMIZED reviews to AI...")
    else:
        input_filename = os.path.join(game_folder_path, f"{folder_basename}_reviews.txt")
        file_description = "original scraped review"
        log_func("Preparing to send ORIGINAL reviews to AI...")

    # Define output file paths
    full_response_txt_filename = os.path.join(game_folder_path, f"{folder_basename}_ai_response_text.txt")
    extracted_csv_filename = os.path.join(game_folder_path, f"{folder_basename}_ai_extracted_data.csv")
    extracted_xlsx_filename = os.path.join(game_folder_path, f"{folder_basename}_ai_extracted_data.xlsx")

    # Check Input File exists
    if not os.path.exists(input_filename):
        log_func(f"AI Error: Input file missing: {input_filename}")
        messagebox.showwarning("File Missing", f"Required {file_description} file not found.\nRun previous steps first.")
        return False, None, None

    log_func(f"Prep AI data: {model_display_name} ({model_id})...")
    parsed_csv_data = None; full_generated_text_api = None; text_for_file = None # noqa
    overall_success = False; csv_saved = False; txt_saved = False # noqa
    reviews_text = ""

    try: # Main try for interaction (Read file -> Optional Warn -> API -> Process)
        # --- Read Input File ---
        try:
            log_func(f"Reading {file_description} file: {input_filename}")
            with open(input_filename, "r", encoding="utf-8") as f: reviews_text = f.read() # noqa
            if not reviews_text.strip(): raise ValueError("Input file is empty.") # noqa
            log_func(f"Read {len(reviews_text)} chars from '{os.path.basename(input_filename)}'.") # noqa
        except (IOError, ValueError) as e: log_func(f"AI Error: Cannot read/empty input file: {e}"); messagebox.showerror("File Error", f"Cannot read/empty {file_description} file:\n{os.path.basename(input_filename)}"); return False, None, None # noqa

        # --- Token Warning (ONLY for ORIGINAL file) ---
        if not use_optimized_file:
            estimated_tokens = len(reviews_text.split())  # Estimate tokens by word count
            log_func(f"Estimated tokens for original file: ~{estimated_tokens:,}")
            token_limit = 1_000_000
            if estimated_tokens > token_limit:
                warning_message = (f"ORIGINAL file is large (~{estimated_tokens:,} est. tokens).\n"
                                   f"Sending may exceed limits or take long.\n\nProceed anyway?") # noqa
                if not messagebox.askyesno("Token Limit Warning", warning_message, icon='warning'):
                    log_func("AI submission cancelled by user (token warning).")
                    return False, None, None # User cancelled

        # --- API Call ---
        generated_text_from_api = "Error: API call failed or no response." # Default
        finish_reason = "UNKNOWN"; usage_metadata = {} # noqa
        try: # API request and basic parsing block
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"; headers={"Content-Type":"application/json"}; prompt=(f"Analyze Steam reviews for '{game_name}'. Based *only* on reviews, answer: {query_text}\n\n---\n{reviews_text}\n---"); payload={"contents": [{"role": "user", "parts": [{"text": prompt}]}],"generationConfig": {"maxOutputTokens": 8192}}; log_func(f"Sending request ({model_display_name})..."); # noqa
            response = requests.post(api_url, json=payload, headers=headers, timeout=300); response.raise_for_status(); log_func("AI request OK."); response_data = response.json(); # noqa
            # Parse response structure safely
            try: # noqa
                candidate = response_data.get('candidates', [{}])[0]; content = candidate.get('content', {}); parts = content.get('parts', [{}]); generated_text_from_api = parts[0].get('text', "Error: Text part missing."); finish_reason = candidate.get('finishReason', 'UNKNOWN'); log_func(f"Safety: {candidate.get('safetyRatings')}") # noqa
                if generated_text_from_api.startswith("Error:"): feedback = response_data.get('promptFeedback',{}); block_reason = feedback.get('blockReason'); # noqa
                if block_reason: generated_text_from_api = f"Error: Blocked ({block_reason})."; log_func(f"Blocked: {block_reason}. Safety: {feedback.get('safetyRatings')}") # noqa
                usage_metadata = response_data.get('usageMetadata', {}); log_func(f"API Usage: {usage_metadata}") # noqa
            except Exception as parse_e: log_func(f"Error parsing AI response: {parse_e}") # noqa
        # Handle API request errors
        except requests.exceptions.Timeout: log_func("AI timed out."); messagebox.showerror("API Error", "AI timed out."); return False, None, None # noqa
        except requests.exceptions.RequestException as req_e: # noqa
            log_func(f"AI API fail: {req_e}"); details="No body."; status="N/A"; # noqa
            if req_e.response is not None:
                status = req_e.response.status_code
                try:
                    d = req_e.response.json()
                    det = d.get('error', {}).get('message', req_e.response.text)
                    details = det if det else req_e.response.text
                except Exception:
                    details = req_e.response.text
                details = details[:500]
            log_func(f"Status: {status}. Details: {details}"); messagebox.showerror("API Error", f"AI Comms Fail.\nStatus: {status}\n{details}"); return False, None, None # noqa

        # --- Process Result ---
        full_generated_text_api = generated_text_from_api # Store whatever text we got

        # Prepare text for file (excluding CSV block)
        text_for_file = full_generated_text_api # Default
        start_tag = "<CSV_START>"; end_tag = "<CSV_END>" # noqa
        start_index = full_generated_text_api.find(start_tag)
        end_index = full_generated_text_api.find(end_tag)
        if start_index != -1 and end_index != -1 and start_index < end_index:
             text_before = full_generated_text_api[:start_index].rstrip()
             text_after = full_generated_text_api[end_index + len(end_tag):].lstrip()
             text_for_file = text_before + "\n\n[CSV data extracted separately]\n\n" + text_after
             text_for_file = text_for_file.strip()

        # Save Modified Text to TXT
        try: # noqa
            with open(full_response_txt_filename, "w", encoding="utf-8") as txt_file: txt_file.write(text_for_file); # noqa
            log_func(f"AI response text saved: '{full_response_txt_filename}'")
            txt_saved = True
        except IOError as io_e: log_func(f"Error saving AI response text: {io_e}"); messagebox.showwarning("File Warning", f"Could not save AI text:\n{io_e}") # noqa

        # Log finish reason warnings
        if finish_reason not in ["STOP", "MAX_TOKENS", "UNSPECIFIED", None, "OTHER"]: log_func(f"Warn: Unusual finish reason '{finish_reason}'.") # noqa
        elif finish_reason == "MAX_TOKENS": log_func(f"Warn: Finish reason '{finish_reason}'.") # noqa

        # Extract, Parse, Save CSV & XLSX (only if API didn't return error text)
        if not full_generated_text_api.startswith("Error:"):
            csv_content_str = None
            if start_index != -1 and end_index != -1 and start_index < end_index:
                log_func("Found CSV tags, attempting extraction...")
                csv_content_str = full_generated_text_api[start_index + len(start_tag):end_index].strip()
                if csv_content_str:
                    try: # Inner try for CSV processing # noqa
                        csvfile = io.StringIO(csv_content_str); reader = csv.reader(csvfile); parsed_csv_data = [row for row in reader if any(field.strip() for field in row)]; # noqa
                        if parsed_csv_data: # noqa
                            with open(extracted_csv_filename, "w", encoding="utf-8", newline="") as extracted_f: writer = csv.writer(extracted_f, quoting=csv.QUOTE_MINIMAL); writer.writerows(parsed_csv_data); # noqa
                            log_func(f"Extracted CSV saved: '{extracted_csv_filename}'"); csv_saved = True; # noqa
                            generate_xlsx_from_csv(extracted_csv_filename, extracted_xlsx_filename, log_func); # noqa
                        else: log_func("Warn: CSV content empty after parsing."); parsed_csv_data = None; # noqa
                    except csv.Error as csv_e: log_func(f"Error parsing CSV tags: {csv_e}"); messagebox.showwarning("CSV Parsing Error", f"Could not parse data between CSV tags.\n{csv_e}"); parsed_csv_data = None; # noqa
                    except IOError as io_e: log_func(f"Error writing extracted CSV: {io_e}"); messagebox.showerror("File Error", f"Could not save extracted CSV:\n{io_e}"); parsed_csv_data = None; # noqa
                    except Exception as e: log_func(f"Unexpected CSV error: {e}\n{traceback.format_exc()}"); messagebox.showerror("Error", f"Unexpected error processing CSV:\n{e}"); parsed_csv_data = None; # noqa
                else: log_func("Warn: No text content between CSV tags.") # noqa
            else: log_func("Warn: CSV start/end tags not found.") # noqa

        # Log the modified text
        log_func("-" * 20 + " AI Response Text (for Tab) " + "-" * 20)
        log_func(text_for_file if text_for_file else "[No text processed]")
        log_func("-" * 20 + " End AI Response Text " + "-" * 22)

        overall_success = txt_saved or csv_saved

        # Return the text intended for the display tab
        return overall_success, parsed_csv_data, text_for_file

    # Outer Exception Handling for file read or unexpected issues
    except Exception as e:
        log_func(f"Unexpected AI error (outer scope): {e}\n{traceback.format_exc()}")
        messagebox.showerror("AI Error", f"Unexpected AI error:\n{e}")
        return False, None, None

# --- Load Existing Data ---
def load_existing_data(widgets, log_func):
    """Loads existing processed data (CSV and modified Text) for the selected game."""
    game_name = widgets['game_name_entry'].get().strip()
    steam_app_id = widgets['steam_id_entry'].get().strip()

    if not game_name or not steam_app_id or not steam_app_id.isdigit():
        messagebox.showwarning("Input Error", "Game Name and valid Steam ID required.")
        return False, None, None

    game_folder_path = get_game_folder_path(game_name, steam_app_id, log_func)
    if not game_folder_path:
        return False, None, None

    log_func(f"Attempting to load data for {game_name}...")
    folder_basename = os.path.basename(game_folder_path)

    # Define expected file paths
    extracted_csv_path = os.path.join(game_folder_path, f"{folder_basename}_ai_extracted_data.csv")
    # Load the text file that EXCLUDES the CSV block
    response_text_path = os.path.join(game_folder_path, f"{folder_basename}_ai_response_text.txt")

    loaded_csv_data = None
    loaded_text_data = None
    found_any_data = False

    # Try loading CSV
    if os.path.exists(extracted_csv_path):
        log_func(f"Found extracted CSV: {extracted_csv_path}")
        try: # noqa
            with open(extracted_csv_path, 'r', encoding='utf-8', newline='') as f: reader = csv.reader(f); loaded_csv_data = [row for row in reader if any(field.strip() for field in row)]; # noqa
            if loaded_csv_data: log_func("Loaded extracted CSV data."); found_any_data = True; # noqa
            else: log_func("Extracted CSV file empty."); loaded_csv_data = None; # noqa
        except (IOError, csv.Error) as e: log_func(f"Error loading extracted CSV: {e}"); messagebox.showwarning("Load Warning", f"Could not load CSV:\n{e}"); loaded_csv_data = None; # noqa
    else: log_func("No extracted CSV file found.") # noqa

    # Try loading Text (the modified one)
    if os.path.exists(response_text_path):
        log_func(f"Found response text: {response_text_path}")
        try: # noqa
            with open(response_text_path, 'r', encoding='utf-8') as f: loaded_text_data = f.read(); # noqa
            log_func("Loaded response text data."); found_any_data = True; # noqa
        except IOError as e: log_func(f"Error loading response text: {e}"); messagebox.showwarning("Load Warning", f"Could not load response text:\n{e}"); loaded_text_data = "[Error loading text]"; # noqa
    else: log_func("No response text file found.") # noqa

    if not found_any_data: log_func("No existing processed data (CSV or Text) found."); messagebox.showinfo("Load Data", "No previously generated data found."); return False, None, None; # noqa

    # Return success, loaded CSV (or None), loaded Text (or None)
    return True, loaded_csv_data, loaded_text_data