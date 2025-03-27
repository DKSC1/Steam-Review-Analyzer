import subprocess
import os
import sys
import io
import re
import time
import traceback
from tkinter import messagebox

def execute_reviews_script(root, command, steam_app_id, progress_callback, log_func):
    """
    Executes the reviews.py script as a subprocess, handling I/O and progress.

    Args:
        root: The main Tkinter root window (for update_idletasks).
        command (list): The command list to execute (e.g., ['python', 'reviews.py', ...]).
        steam_app_id (str): The Steam App ID to send via stdin.
        progress_callback (callable): Function to call with scraped count (e.g., lambda count: update_gui(count)).
        log_func (callable): Function for logging messages.

    Returns:
        tuple: (bool: success, str: full_stderr)
    """
    process = None
    full_stderr = ""
    success_flag = False
    current_reviews_scraped = 0

    try:
        # --- Popen Call ---
        log_func(f"Running command: {' '.join(command)}")
        try:
            # Use CREATE_NO_WINDOW on Windows to hide console
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding=None,  # Read stdout/stderr as bytes
                cwd=os.path.dirname(sys.argv[0]) or '.',
                creationflags=creationflags
            )
        except Exception as popen_e:
            log_func(f"Error starting subprocess: {popen_e}\n{traceback.format_exc()}")
            messagebox.showerror("Execution Error", f"Failed start script:\n{popen_e}")
            return False, ""

        # --- Send Input to Subprocess ---
        try:
            if process.stdin:
                app_id_bytes = (steam_app_id + "\n").encode('utf-8')
                process.stdin.write(app_id_bytes)
                process.stdin.close() # Close stdin after writing
            else:
                raise OSError("Process stdin stream unavailable immediately after Popen.")
        except (OSError, ValueError, TypeError) as stdin_e:
            log_func(f"Error writing stdin: {stdin_e}")
            if process and process.poll() is None:
                try: process.kill()
                except Exception: pass
            return False, "" # Can't proceed

        # --- Read Output Stream ---
        if process.stdout:
            try:
                # Read byte stream and decode line by line
                stdout_reader = io.TextIOWrapper(process.stdout, encoding='utf-8', errors='replace')
                while True:
                    line = stdout_reader.readline()
                    # Check if process ended AND no more data is available
                    if not line and process.poll() is not None:
                        break
                    if line:
                        line_strip = line.strip()
                        log_func(f"SCRIPT: {line_strip}")

                        # Match progress line
                        match = re.search(r'Total so far:\s*(\d+)', line_strip, re.IGNORECASE)
                        if match:
                            try:
                                current_reviews_scraped = int(match.group(1))
                                if progress_callback:
                                    progress_callback(current_reviews_scraped) # Call the provided callback
                                # Schedule GUI update via root.after if needed, but simple callback is cleaner here
                                # if root and root.winfo_exists(): root.update_idletasks()
                            except ValueError:
                                log_func("Warn: Cannot parse progress number.")
                            except Exception as e_update:
                                log_func(f"Warn: Error in progress callback: {e_update}")
            except Exception as read_e:
                log_func(f"Error reading script output: {read_e}")
                # Continue to wait/check return code below
        else:
            log_func("Error: Process stdout stream unavailable.")
            # Still wait for process below

        # --- Wait for Process and Check Results ---
        return_code = -99 # Default unknown code
        try:
            # Reasonable timeout for the process to finish after I/O is done
            return_code = process.wait(timeout=120) # Increased timeout
        except subprocess.TimeoutExpired:
            log_func("Warn: Process final wait timeout. Killing process.")
            return_code = -1 # Indicate timeout state
            if process and process.poll() is None: # Check again before killing
                try: process.kill()
                except Exception: pass
        except Exception as wait_e:
            log_func(f"Error waiting for process: {wait_e}")
            return_code = -2 # Indicate wait error

        # Read any remaining stderr after process completion
        if process.stderr:
            try:
                # Ensure stderr is read completely even after wait/kill
                stderr_reader = io.TextIOWrapper(process.stderr, encoding='utf-8', errors='replace')
                full_stderr = stderr_reader.read()
                if full_stderr:
                    log_func("Scraping Script Errors/Warnings:\n" + full_stderr)
            except Exception as stderr_e:
                log_func(f"Error reading stderr after process completion: {stderr_e}")

        # --- Process Results Based on Return Code ---
        if return_code == 0:
            log_func("Scraping script finished successfully (Return Code: 0).")
            success_flag = True
        else:
            log_func(f"Scraping process failed (Return Code: {return_code}).")
            messagebox.showerror("Scraping Error", f"reviews.py failed (Code: {return_code}). Check logs.\n{full_stderr[:200]}...")
            success_flag = False

    # --- Outer Exception Catch-all ---
    except FileNotFoundError as fnf_e:
        log_func(f"File Not Found Error during subprocess setup: {fnf_e}")
        messagebox.showerror("Execution Error", f"File not found: {fnf_e}")
        success_flag = False
    except Exception as e:
        log_func(f"Unexpected error during subprocess execution: {e}")
        log_func(f"Traceback: {traceback.format_exc()}")
        messagebox.showerror("Execution Error", f"An unexpected error occurred: {e}")
        success_flag = False
    finally:
        # Close streams safely if process exists
        if process:
            try:
                if process.stdout: process.stdout.close()
                if process.stderr: process.stderr.close()
            except Exception:
                pass # Ignore stream closing errors

    return success_flag, full_stderr


def execute_optimize_script(command, log_func):
    """
    Executes the optimize.py script as a subprocess using communicate.

    Args:
        command (list): The command list to execute (e.g., ['python', 'optimize.py', ...]).
        log_func (callable): Function for logging messages.

    Returns:
        tuple: (bool: success, str: output, str: error)
    """
    process = None
    out = ""
    err = ""
    success_flag = False

    try:
        log_func(f"Running: {' '.join(command)}")

        # Popen in its own try block
        try:
            # Use CREATE_NO_WINDOW on Windows to hide console
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,  # Use text mode for communicate
                encoding='utf-8', # Specify encoding
                errors='replace', # Handle potential decoding errors
                cwd=os.path.dirname(sys.argv[0]) or '.',
                creationflags=creationflags
            )
        except Exception as popen_e:
            log_func(f"Error starting optimization script: {popen_e}")
            messagebox.showerror("Execution Error", f"Failed start optimize.py:\n{popen_e}")
            return False, "", str(popen_e) # Return error message

        # Communicate in its own try block
        try:
            # Set a long timeout (e.g., 30 minutes) for potentially large files
            out, err = process.communicate(timeout=1800)
        except subprocess.TimeoutExpired:
            log_func("Optimization script timed out!")
            try:
                if process and process.poll() is None: process.kill() # noqa
            except Exception: pass # noqa
            # Try to get any output after kill
            try: out, err = process.communicate() # noqa
            except Exception as comm_e: log_func(f"Error getting output after timeout: {comm_e}") # noqa
            messagebox.showerror("Timeout", "Optimization script timed out (30 minutes).")
            # Let finally clean up, success_flag remains False
        except Exception as comm_e:
            log_func(f"Error communicating with optimization script: {comm_e}")
            messagebox.showerror("Execution Error", f"Error running optimize.py:\n{comm_e}")
            err = str(comm_e) # Capture error message
            # Let finally clean up, success_flag remains False

        # Check results only if communicate finished or recovered output
        # process.returncode should be set after communicate() or kill()/communicate()
        if process and process.returncode is not None:
            if out: log_func(f"Optimization Output:\n{out}") # noqa
            if err: log_func(f"Optimization Errors:\n{err}") # noqa

            if process.returncode == 0:
                log_func("Optimization script OK (Code: 0).")
                success_flag = True
            else:
                log_func(f"Optimization failed (Code: {process.returncode}).")
                messagebox.showerror("Optimization Error", f"optimize.py failed (Code: {process.returncode}).\n{err[:200]}...")
                success_flag = False
        else:
             # This case means communicate might have failed badly or process state is unknown
             log_func("Error: Optimization process status unknown after execution attempt.")
             success_flag = False
             if not err: err = "Process status unknown after execution."


    except FileNotFoundError as fnf_e:
        log_func(f"Error: Python interpreter or script not found: {fnf_e}")
        messagebox.showerror("Execution Error", f"Python or optimize.py not found:\n{fnf_e}")
        success_flag = False
        err = str(fnf_e)
    except Exception as e:
        log_func(f"Unexpected optimization error: {e}\n{traceback.format_exc()}")
        messagebox.showerror("Optimization Error", f"Unexpected error: {e}")
        success_flag = False
        err = str(e)
    finally: # Final cleanup (streams are handled by communicate)
        pass # No explicit stream closing needed when using communicate

    return success_flag, out, err