# process_handler.py
import subprocess
import os
import shutil
import re
import sys
import io
import traceback
import threading
from tkinter import messagebox

# Assume utils.py and config.py are accessible
from utils import sanitize_filename
from utils import log_message
from config import BASE_REVIEW_DIR

# --- Helper: Get Game Folder Path ---
# (Keep unchanged - Generally simpler structure)
def get_game_folder_path(game_name, steam_id, log_func):
    if not game_name or not steam_id or not steam_id.isdigit():
        log_func("Error: Cannot get folder path without Game/ID.")
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
def run_scraping(root, widgets, settings_func, log_func, stop_event: threading.Event):
    """Gets inputs, runs reviews.py, handles stop, saves data."""

    # --- 1. Input Validation and Path Setup ---
    settings = settings_func()
    game_name = ""
    steam_app_id = ""
    try:
        entry_name = widgets.get('game_name_entry')
        entry_id = widgets.get('steam_id_entry')
        if entry_name: game_name = entry_name.get().strip()
        if entry_id: steam_app_id = entry_id.get().strip()
    except Exception as e:
        log_func(f"Error getting game/ID widgets: {e}"); messagebox.showwarning("Input Error", "Read Error."); return False # noqa
    if not steam_app_id or not steam_app_id.isdigit() or not game_name:
        messagebox.showwarning("Input Error", "Valid Game Name & Steam ID required."); return False # noqa
    game_folder_path = get_game_folder_path(game_name, steam_app_id, log_func)
    if not game_folder_path:
        return False # Error logged by helper

    script_path = 'reviews.py'
    temp_output_file = 'reviews.txt' # Created by reviews.py
    folder_basename = os.path.basename(game_folder_path)
    target_output_file = os.path.join(game_folder_path, f"{folder_basename}_reviews.txt") # Final destination

    log_func(f"Starting scraping for App ID: {steam_app_id} ('{game_name}')...")
    # (Simplified logging calls slightly)
    log_func(f"Target: {os.path.basename(game_folder_path)}")
    log_func(f"Settings: Max={settings.get('max_reviews','N/A')}, #/Pg={settings.get('num_per_page','N/A')}, Sleep={settings.get('sleep_duration','N/A')}s")
    log_func(f"Filters: Lang={settings.get('steam_language','N/A')}, Type={settings.get('steam_review_type','N/A')}, Purch={settings.get('steam_purchase_type','N/A')}, Date={settings.get('steam_date_range','N/A')}, Play={settings.get('steam_playtime','N/A')}, By={settings.get('steam_filter_by','N/A')}, Beta={settings.get('steam_beta','N/A')}")

    # --- 2. GUI Progress Setup ---
    progress_bar = widgets.get('progress_bar')
    progress_label = widgets.get('scrape_progress_label')
    max_reviews_target = settings.get('max_reviews', 0)
    current_reviews_scraped = 0
    try:
        progress_bar_frame = progress_bar.master if progress_bar else None
        if progress_bar_frame and hasattr(progress_bar_frame, 'grid'): progress_bar_frame.grid()
        if progress_label and progress_label.winfo_exists(): progress_label.configure(text=f"Scraping: 0 / {max_reviews_target}")
        if progress_bar and progress_bar.winfo_exists(): progress_bar.set(0)
        if root and root.winfo_exists(): root.update_idletasks()
    except Exception as gui_e: log_func(f"Warn: Error setting progress display: {gui_e}")

    # --- 3. State Variables ---
    process = None
    success_flag = False # True only on successful completion AND move
    stderr_output = ""
    return_code = -99 # Default/initial code

    # --- 4. Main Execution Block (Outer Try/Finally for Cleanup) ---
    try:
        # --- 4a. Pre-run Checks & Setup ---
        if not os.path.exists(script_path):
            log_func(f"Error: Script missing: {script_path}"); messagebox.showerror("File Error", f"Script missing: {script_path}"); return False # noqa
        if os.path.exists(target_output_file):
            overwrite = messagebox.askyesno("Exists", f"'{os.path.basename(target_output_file)}' exists.\nOverwrite?", icon='warning') # noqa
            if not overwrite: log_func("Scraping cancelled (overwrite)."); return False
            else:
                log_func(f"Overwrite: '{os.path.basename(target_output_file)}'.")
                try:
                    os.remove(target_output_file)
                except OSError as r:
                    log_func(f"Warn: Remove fail: {r}") # noqa
        if os.path.exists(temp_output_file):
             try: os.remove(temp_output_file); log_func(f"Removed old temp: '{temp_output_file}'.");
             except OSError as r: log_func(f"Warn: Could not remove temp: {r}")

        # --- 4b. Build Command ---
        command = [ sys.executable, script_path, '--max', str(settings.get('max_reviews', 1000)), '--sleep', str(settings.get('sleep_duration', 1.5)), '--num', str(settings.get('num_per_page', 100)), '--language', settings.get('steam_language', 'all'), '--review_type', settings.get('steam_review_type', 'all'), '--purchase_type', settings.get('steam_purchase_type', 'all'), '--day_range', settings.get('steam_date_range', '0'), '--playtime', settings.get('steam_playtime', '0'), '--filter_by', settings.get('steam_filter_by', 'all'), '--beta', settings.get('steam_beta', '0') ] # noqa
        log_func(f"Running: {' '.join(command)}")

        # --- 4c. Start Subprocess ---
        try:
            script_dir = os.path.dirname(sys.argv[0]) or '.'
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            process = subprocess.Popen( command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding=None, cwd=script_dir, creationflags=creationflags) # noqa
        except FileNotFoundError as fnf: log_func(f"Error starting: {fnf}"); messagebox.showerror("Exec Error", f"Not Found:\n{fnf}"); return False # noqa
        except Exception as popen_e: log_func(f"Error starting: {popen_e}"); messagebox.showerror("Exec Error", f"Failed start:\n{popen_e}"); return False # noqa

        # --- 4d. Send Input ---
        try:
            if process.stdin: app_id_bytes = (steam_app_id + "\n").encode('utf-8'); process.stdin.write(app_id_bytes); process.stdin.close(); # noqa
            else: raise OSError("Process stdin unavailable.")
        except (OSError, ValueError, TypeError) as stdin_e:
             log_func(f"Error writing stdin: {stdin_e}")
             if process and process.poll() is None:
                 try:
                     process.kill()
                     process.wait(timeout=5)
                 except Exception:
                     pass  # noqa
             messagebox.showerror("Exec Error", "Failed send ID.")
             return False

        # --- 4e. Monitor Output & Stop Event ---
        if process.stdout:
            try:
                stdout_reader = io.TextIOWrapper(process.stdout, encoding='utf-8', errors='replace')
                while True:
                    if stop_event.is_set():
                        log_func("Stop request. Terminating script...")
                        success_flag = False # Mark as stopped
                        if process and process.poll() is None:
                            try:
                                process.terminate()
                                _, stderr_data = process.communicate(timeout=10) # Try get final stderr
                                if stderr_data: stderr_output += stderr_data.decode('utf-8', errors='replace')
                            except subprocess.TimeoutExpired:
                                log_func("Terminate timed out, killing.");
                                if process and process.poll() is None:
                                    try:
                                        process.kill()
                                        _, stderr_data = process.communicate(timeout=5)
                                    except Exception:
                                        pass # noqa
                            except Exception as e_term:
                                log_func(f"Error stopping: {e_term}")
                                if process and process.poll() is None:
                                    try:
                                        process.kill()
                                    except Exception:
                                        pass # noqa
                        log_func("Scraping stopped by user.")
                        messagebox.showinfo("Stopped", "Scraping stopped.")
                        break # Exit read loop

                    line = stdout_reader.readline()
                    if not line and process.poll() is not None: break # Process ended

                    if line:
                        line_strip = line.strip(); log_func(f"SCRIPT: {line_strip}"); # noqa
                        # --- UPDATED PROGRESS REGEX ---
                        match = re.search(r'Total written:\s*(\d+)', line_strip, re.IGNORECASE) # Match the actual output from reviews.py
                        if match:
                            try:
                                current_reviews_scraped = int(match.group(1))
                                progress_val = min(1.0, current_reviews_scraped / max_reviews_target) if max_reviews_target > 0 else 0 # noqa
                                def _update_gui(val, prog): # Inner func for clarity
                                    try:
                                        if progress_label and progress_label.winfo_exists(): progress_label.configure(text=f"Scraping: {val} / {max_reviews_target}"); # noqa
                                        if progress_bar and progress_bar.winfo_exists(): progress_bar.set(prog); # noqa
                                    except Exception: pass # Ignore GUI errors in callback
                                if root and root.winfo_exists(): root.after(0, _update_gui, current_reviews_scraped, progress_val) # noqa
                            except Exception as e_prog: log_func(f"Warn: Progress error: {e_prog}")
            except Exception as read_e: log_func(f"Error reading output: {read_e}")
        else: log_func("Error: stdout unavailable.")

        # --- 4f. Final Wait & Status Check (if not stopped) ---
        return_code = process.poll() if process else -100
        if not stop_event.is_set() and return_code is None:
            log_func("Waiting for script completion...")
            try:
                 _, stderr_data = process.communicate(timeout=300) # 5 min final wait
                 return_code = process.returncode
                 if stderr_data: stderr_output += stderr_data.decode('utf-8', errors='replace')
            except subprocess.TimeoutExpired:
                 log_func("Warn: Timeout on final wait."); return_code = -1;
                 if process and process.poll() is None:
                     try:
                         process.kill()
                         process.wait(timeout=5)
                     except Exception:
                         pass  # noqa
                 messagebox.showerror("Timeout", "Script timed out.")
            except Exception as wait_e:
                 log_func(f"Error on final wait: {wait_e}")
                 return_code = -2
                 if process and process.poll() is None:
                     try:
                         process.kill()
                         process.wait(timeout=5)
                     except Exception:
                         pass  # noqa
        elif stop_event.is_set():
             if process: return_code = process.poll(); # Get final code if possible
             log_func(f"Stopped, final code: {return_code}")
             success_flag = False # Ensure false

        # --- 4g. Process Final Result ---
        if stderr_output: log_func("Script Errors/Warnings (Final):\n---\n" + stderr_output.strip() + "\n---") # noqa

        if not stop_event.is_set(): # Only process success/fail if not stopped
            if return_code == 0:
                log_func("Script OK (Code 0).")
                if os.path.exists(temp_output_file):
                    try: # Move successful result
                        os.makedirs(os.path.dirname(target_output_file), exist_ok=True)
                        shutil.move(temp_output_file, target_output_file)
                        log_func(f"Saved result: '{os.path.basename(target_output_file)}'.")
                        success_flag = True
                        def _final_gui(count): # Inner func for callback
                            try:
                                if progress_label and progress_label.winfo_exists(): progress_label.configure(text=f"Scraped: {count}"); # noqa
                                if progress_bar and progress_bar.winfo_exists(): progress_bar.set(1.0); # noqa
                            except Exception: pass
                        if root and root.winfo_exists(): root.after(0, _final_gui, current_reviews_scraped)
                    except Exception as e_move: log_func(f"Error moving result: {e_move}"); messagebox.showerror("File Error", f"Save fail:\n{e_move}"); success_flag = False; # noqa
                else: # Script OK but no temp file
                    log_func(f"Warn: Script OK but temp missing: {temp_output_file}"); success_flag = False; # noqa
                    if not stderr_output.strip(): messagebox.showwarning("Warn", "Script OK, output missing.");
            else: # Script failed (non-zero code)
                 log_func(f"Script failed (Code: {return_code})."); success_flag = False;
                 snip = stderr_output.strip()[:200] + ('...' if len(stderr_output.strip()) > 200 else ''); messagebox.showerror("Error", f"Script failed (Code: {return_code}).\n{snip}"); # noqa

        # --- 4h. Save Partial File (if needed) ---
        if not success_flag and os.path.exists(temp_output_file):
            log_func(f"Not successful (Stopped/Error: {return_code}). Saving partial data...")
            try:
                os.makedirs(os.path.dirname(target_output_file), exist_ok=True)
                shutil.copyfile(temp_output_file, target_output_file) # Use copy
                log_func(f"Saved partial: '{os.path.basename(target_output_file)}'.")
                if stop_event.is_set(): messagebox.showinfo("Partial Saved", f"Stopped.\nPartial data saved:\n{os.path.basename(target_output_file)}") # noqa
                else: messagebox.showwarning("Partial Saved", f"Failed.\nPartial data saved:\n{os.path.basename(target_output_file)}") # noqa
            except Exception as e_copy: log_func(f"Error saving partial: {e_copy}"); messagebox.showerror("File Error", f"Save partial fail:\n{e_copy}"); # noqa
        # --- End Result Processing ---

    # --- Outer Exception Handling ---
    except Exception as e_outer:
        log_func(f"Outer error: {e_outer}\n{traceback.format_exc()}"); success_flag = False;
        messagebox.showerror("Error", f"Unexpected error:\n{e_outer}");
        if process and process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception:
                pass  # noqa

    # --- 5. Final Cleanup Block ---
    finally:
        # Close streams if process exists (defensive)
        if process:
            try:
                if process.stdin and not process.stdin.closed: process.stdin.close()
                if process.stdout and not process.stdout.closed: process.stdout.close()
                if process.stderr and not process.stderr.closed: process.stderr.close()
            except Exception: pass # Ignore cleanup errors

        # Clean temp file logic (remove if full success OR if partial was saved)
        should_remove_temp = False
        if os.path.exists(temp_output_file):
             if success_flag or os.path.exists(target_output_file): # If full success OR partial save worked
                  should_remove_temp = True
                  reason = "(after success/partial save)"
             else:
                  should_remove_temp = True # Also remove if neither full nor partial saved
                  reason = "(no target created)"

             if should_remove_temp:
                 try: os.remove(temp_output_file); log_func(f"Cleaned temp: '{temp_output_file}' {reason}.");
                 except OSError as e: log_func(f"Warn: Remove temp fail: {e}")

        # Reset progress display (scheduled)
        def reset_prog_gui():
            try:
                bar_frame = progress_bar.master if progress_bar else None;
                if bar_frame and hasattr(bar_frame, 'grid_remove'): bar_frame.grid_remove();
                if progress_bar and progress_bar.winfo_exists(): progress_bar.set(0);
                if progress_label and progress_label.winfo_exists(): progress_label.configure(text="Scraping: Idle");
            except Exception as e: log_func(f"Warn: Reset progress GUI error: {e}") if log_func else None;
        if root and root.winfo_exists():
            root.after(10, reset_prog_gui)
        try:
            reset_prog_gui() # Try immediate reset as well
        except Exception:
            pass

    return success_flag

# --- Subprocess Execution: Optimization ---
# (Keep unchanged - Structure is simpler)
def run_optimization(widgets, settings_func, log_func):
    settings = settings_func(); game_name = ""; steam_app_id = "";
    try:
        entry_name = widgets.get('game_name_entry')
        entry_id = widgets.get('steam_id_entry')
        if entry_name:
            game_name = entry_name.get().strip()
        if entry_id:
            steam_app_id = entry_id.get().strip()
    except Exception as e:
        log_func(f"Error getting optimization ID: {e}")
        messagebox.showwarning("Input Error", "Failed to read input.")
        return False
    if not game_name or not steam_app_id or not steam_app_id.isdigit(): messagebox.showwarning("Input Error", "Game/ID req."); return False; # noqa
    game_folder_path = get_game_folder_path(game_name, steam_app_id, log_func); # noqa
    if not game_folder_path: return False
    folder_base = os.path.basename(game_folder_path); src = os.path.join(game_folder_path, f"{folder_base}_reviews.txt"); target = os.path.join(game_folder_path, f"{folder_base}_reviews_optimized.txt"); s_dir = os.path.dirname(sys.argv[0]) or '.'; tmp_in = os.path.join(s_dir, "reviews.txt"); tmp_out = os.path.join(s_dir, "reviews2.txt"); s_path = os.path.join(s_dir, 'optimize.py'); ok = False; stdout = ""; stderr = ""; # noqa
    if not os.path.exists(src): log_func(f"Opt Err: Src missing: {os.path.basename(src)}"); messagebox.showwarning("Missing", f"Scraped file missing:\n{os.path.basename(src)}"); return False; # noqa
    if os.path.exists(target):
        ow = messagebox.askyesno("Exists", f"'{os.path.basename(target)}' exists.\nOverwrite?", icon='warning')  # noqa
        if not ow:
            log_func("Opt cancelled.")
            return False
        else:
            log_func(f"Overwrite: {os.path.basename(target)}.")
            try:
                os.remove(target)
            except OSError as r:
                log_func(f"Warn: Rem fail: {r}")  # noqa
    log_func("Optimizing...")
    try:  # Prep temp
        if os.path.exists(tmp_in): os.remove(tmp_in);
        if os.path.exists(tmp_out): os.remove(tmp_out);
        shutil.copyfile(src, tmp_in); log_func(f"Prep tmp '{os.path.basename(tmp_in)}'.");
    except Exception as p: log_func(f"Error prep tmp: {p}"); messagebox.showerror("File Error", f"Copy fail:\n{p}"); return False; # noqa
    proc = None
    try: # Run subprocess
        if not os.path.exists(s_path): log_func(f"Error: Opt script missing: {s_path}"); messagebox.showerror("Error", f"'{os.path.basename(s_path)}' missing."); return False; # noqa
        thr = settings.get('token_threshold', 950000); log_func(f"Token Thr: {thr}"); cmd = [sys.executable, s_path, '--threshold', str(thr)]; log_func(f"Run: {' '.join(cmd)}"); # noqa
        try: # Popen
            cf = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0; proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', cwd=s_dir, creationflags=cf); # noqa
        except FileNotFoundError as f: log_func(f"Error start opt: {f}"); messagebox.showerror("Error", f"Not Found:\n{f}"); return False; # noqa
        except Exception as p_e: log_func(f"Error start opt: {p_e}"); messagebox.showerror("Error", f"Failed start:\n{p_e}"); return False; # noqa
        try:  # Communicate
            stdout, stderr = proc.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            log_func("Opt timed out!")
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
            messagebox.showerror("Timeout", "Opt timed out.")
            return False
        except Exception as c_e:
            log_func(f"Error comm opt: {c_e}")
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
            messagebox.showerror("Error", f"Error run:\n{c_e}")
            return False
        if stdout:
            log_func(f"Opt Output:\n---\n{stdout.strip()}\n---")
        if stderr:
            log_func(f"Opt Errors:\n---\n{stderr.strip()}\n---")
        if proc.returncode != 0: log_func(f"Opt fail (Code: {proc.returncode})."); snip = stderr.strip()[:200] + ('...' if len(stderr.strip()) > 200 else ''); messagebox.showerror("Opt Error", f"optimize.py fail (Code: {proc.returncode}).\n{snip}"); # noqa
        else: # Success
            log_func("Opt OK (Code 0).")
            if os.path.exists(tmp_out):
                try: os.makedirs(os.path.dirname(target), exist_ok=True); shutil.move(tmp_out, target); log_func(f"Saved opt: '{os.path.basename(target)}'."); ok = True; # noqa
                except OSError as m: log_func(f"Error move opt: {m}"); messagebox.showerror("File Error", f"Save fail:\n{m}"); # noqa
                except Exception as e: log_func(f"Error move opt: {e}"); messagebox.showerror("Error", f"Final fail:\n{e}"); # noqa
            else:
                log_func(f"Warn: Opt OK but tmp out miss: {os.path.basename(tmp_out)}")
                if not stderr.strip():
                    messagebox.showwarning("Warn", f"Opt OK but output miss.")
    except Exception as e: log_func(f"Unexpected opt err: {e}\n{traceback.format_exc()}"); messagebox.showerror("Opt Error", f"Unexpected:\n{e}"); ok = False; # noqa
    finally: # Cleanup
        if os.path.exists(tmp_in):
            try:
                os.remove(tmp_in)
                log_func("Cleaned tmp in.")
            except OSError as e:
                log_func(f"Warn: Rem tmp in fail: {e}") # noqa

        if os.path.exists(tmp_out):
            # Clean tmp_out only if the target wasn't successfully created
            if not os.path.exists(target):
                try:
                    os.remove(tmp_out)
                    log_func("Cleaned tmp out (no target created).")
                except OSError as e:
                    log_func(f"Warn: Rem tmp out fail: {e}") # noqa
            elif not ok: # Also clean if operation failed but target might exist from previous run
                try:
                    os.remove(tmp_out)
                    log_func("Cleaned tmp out (operation failed).")
                except OSError as e:
                    log_func(f"Warn: Rem tmp out fail: {e}") # noqa


    return ok