import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import time
import requests
import csv
import os
import re
import shutil

# --- Helper functions for logging ---
def log_message(message):
    log_box.configure(state='normal')
    log_box.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
    log_box.see(tk.END)
    log_box.configure(state='disabled')

# --- Functions to run external scripts ---
def run_scraping():
    game_name = game_name_entry.get().strip()
    steam_app_id = steam_id_entry.get().strip()
    if not game_name:
        messagebox.showwarning("Input Error", "Please enter a Game Name.")
        return
    if not steam_app_id:
        messagebox.showwarning("Input Error", "Please enter a Steam Game ID.")
        return

    log_message("Starting review scraping...")
    try:
        # Start reviews.py as a subprocess. It expects the Steam Game ID as input.
        process = subprocess.Popen(
            ['python', 'reviews.py'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # Send the Steam Game ID (with newline) to reviews.py.
        out, err = process.communicate(input=steam_app_id + "\n")
        log_message(out)
        if err:
            log_message("Errors during scraping:\n" + err)
        else:
            log_message("Scraping complete.")
        # Rename the scraped reviews file if it exists.
        scraped_filename = "reviews.txt"
        if os.path.exists(scraped_filename):
            new_name = f"{game_name}_reviews.txt"
            os.rename(scraped_filename, new_name)
            log_message(f"Scraped reviews saved as '{new_name}'.")
        else:
            log_message("Scraped reviews file not found.")
    except Exception as e:
        log_message(f"Scraping failed: {e}")

def run_optimization():
    game_name = game_name_entry.get().strip()
    if not game_name:
        messagebox.showwarning("Input Error", "Please enter a Game Name.")
        return

    # Before running optimization, copy the scraped file back to reviews.txt
    scraped_file = f"{game_name}_reviews.txt"
    if not os.path.exists(scraped_file):
        messagebox.showwarning("File Missing", f"Scraped file '{scraped_file}' not found. Run scraping first.")
        return

    try:
        shutil.copyfile(scraped_file, "reviews.txt")
        log_message(f"Copied '{scraped_file}' to 'reviews.txt' for optimization.")
    except Exception as e:
        log_message(f"Failed to copy file for optimization: {e}")
        return

    log_message("Starting file optimization...")
    try:
        process = subprocess.Popen(
            ['python', 'optimize.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = process.communicate()
        log_message(out)
        if err:
            log_message("Errors during optimization:\n" + err)
        else:
            log_message("Optimization complete.")

        # After optimization, remove the temporary 'reviews.txt'
        if os.path.exists("reviews.txt"):
            os.remove("reviews.txt")
            log_message("Temporary file 'reviews.txt' removed.")

        # Rename the optimized file.
        optimized_filename = "reviews2.txt"
        if os.path.exists(optimized_filename):
            new_name = f"{game_name}_reviews_optimized.txt"
            os.rename(optimized_filename, new_name)
            log_message(f"Optimized reviews saved as '{new_name}'.")
            
            # Parse and log the approximate token count if present.
            token_match = re.search(r"Approximate input tokens:\s*(\d+)", out)
            if token_match:
                tokens = token_match.group(1)
                log_message(f"Approximate token count: {tokens}")
        else:
            log_message("Optimized reviews file not found.")
    except Exception as e:
        log_message(f"Optimization failed: {e}")

# --- Function to call the Google Gemini API ---
def send_to_ai():
    query_text = ai_query_text.get("1.0", tk.END).strip()
    if not query_text:
        messagebox.showwarning("Input Error", "Please enter a query for the AI.")
        return

    game_name = game_name_entry.get().strip()
    if not game_name:
        messagebox.showwarning("Input Error", "Please enter a Game Name (to locate the optimized file).")
        return

    optimized_filename = f"{game_name}_reviews_optimized.txt"
    if not os.path.exists(optimized_filename):
        messagebox.showwarning("File Missing", f"The optimized reviews file '{optimized_filename}' was not found. Run optimization first.")
        return

    log_message("Sending data to AI...")
    try:
        with open(optimized_filename, "r", encoding="utf-8") as f:
            reviews_text = f.read()

        # Prepare the payload for the API call.
        # Replace the following URL, headers, and payload structure with your actual API details.
        api_url = "https://api.example.com/gemini"  # placeholder endpoint
        headers = {
            "Authorization": "AIzaSyAe_nVxv1PC06783TSHKciJmDUpcunX7Bc",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gemini-2.5-pro-exp-03-25",
            "prompt": f"Extract the following information: {query_text}\nFrom the reviews:\n{reviews_text}",
            "response_format": "csv"
        }
        
        response = requests.post(api_url, json=payload, headers=headers)
        if response.status_code != 200:
            log_message(f"AI API request failed with status code {response.status_code}: {response.text}")
            return

        csv_filename = f"{game_name}_ai_response.csv"
        with open(csv_filename, "w", encoding="utf-8", newline="") as csvfile:
            csvfile.write(response.text)
        log_message(f"AI response saved to '{csv_filename}'.")
    except Exception as e:
        log_message(f"Failed to send to AI: {e}")

# --- Thread wrapper functions ---
def thread_scraping():
    threading.Thread(target=run_scraping, daemon=True).start()

def thread_optimization():
    threading.Thread(target=run_optimization, daemon=True).start()

def thread_send_to_ai():
    threading.Thread(target=send_to_ai, daemon=True).start()

# --- Build the GUI ---
root = tk.Tk()
root.title("Steam Reviews Analyzer")

# Frame for Game Name
game_frame = tk.Frame(root)
game_frame.pack(pady=5, padx=5, fill="x")
tk.Label(game_frame, text="Game Name:").pack(side="left")
game_name_entry = tk.Entry(game_frame, width=30)
game_name_entry.pack(side="left", padx=5)

# Frame for Steam Game ID
steam_frame = tk.Frame(root)
steam_frame.pack(pady=5, padx=5, fill="x")
tk.Label(steam_frame, text="Steam Game ID:").pack(side="left")
steam_id_entry = tk.Entry(steam_frame, width=30)
steam_id_entry.pack(side="left", padx=5)

# Buttons for scraping and optimization
button_frame = tk.Frame(root)
button_frame.pack(pady=5, padx=5, fill="x")
scrape_button = tk.Button(button_frame, text="Scrape Reviews", command=thread_scraping)
scrape_button.pack(side="left", padx=5)
optimize_button = tk.Button(button_frame, text="Create Optimized File", command=thread_optimization)
optimize_button.pack(side="left", padx=5)

# Live log display
log_box = scrolledtext.ScrolledText(root, width=80, height=15, state="disabled")
log_box.pack(pady=5, padx=5)

# AI query input area (using a larger Text widget)
ai_frame = tk.Frame(root)
ai_frame.pack(pady=5, padx=5, fill="x")
tk.Label(ai_frame, text="Query for AI:").pack(anchor="w")
ai_query_text = tk.Text(ai_frame, height=5, width=70)
ai_query_text.pack(pady=5, padx=5)

ai_button = tk.Button(ai_frame, text="Send to AI", command=thread_send_to_ai)
ai_button.pack(pady=5)

# Start the GUI event loop
root.mainloop()
