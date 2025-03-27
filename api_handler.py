import requests
import json
import os
import csv
import io
import traceback
from tkinter import messagebox

# Assume utils.py and file_handler.py are accessible
# Need get_game_folder_path to know where to save results
from process_handler import get_game_folder_path
# Need generate_xlsx_from_csv from file_handler (we'll create this file next)
# Forward declaration - will import properly later
# from file_handler import generate_xlsx_from_csv

# Placeholder until file_handler is defined
def generate_xlsx_from_csv(csv_filepath, xlsx_filepath, log_func):
     log_func(f"Placeholder: Would generate XLSX for {xlsx_filepath}")
     # Real implementation will be in file_handler.py
     return True


# --- AI Interaction ---
# (Moved from actions.py - Modified to use passed log_func)
def send_to_ai(widgets, api_key_func, models, log_func, use_optimized_file):
    """
    Sends chosen review file (optimized or original) to Gemini, with token warning.
    Saves modified text, extracts/saves CSV & XLSX.
    Returns tuple: (success_bool, csv_data_list_or_None, modified_full_text_or_None)
    """
    # Import here to avoid circular dependency if file_handler imports this
    from file_handler import generate_xlsx_from_csv

    api_key = api_key_func()
    if not api_key or api_key == "YOUR_VALID_GEMINI_API_KEY_PLACEHOLDER":
         log_func("AI Error: Valid Gemini API Key is missing or not loaded.")
         messagebox.showerror("API Key Error", "A valid Google Gemini API Key has not been provided or loaded.\nPlease check AITEXT.txt or configuration.") # noqa
         return False, None, None

    # Get Inputs safely
    game_name = ""
    steam_app_id = ""
    selected_model_name = ""
    query_text = ""
    try:
        if widgets.get('game_name_entry'): game_name = widgets['game_name_entry'].get().strip()
        if widgets.get('steam_id_entry'): steam_app_id = widgets['steam_id_entry'].get().strip()
        if widgets.get('model_combobox'): selected_model_name = widgets['model_combobox'].get()
        if widgets.get('ai_query_text'): query_text = widgets['ai_query_text'].get("1.0", "end-1c").strip()
    except Exception as e:
        log_func(f"Error getting AI inputs from widgets: {e}")
        messagebox.showerror("Input Error", "Could not read inputs for AI analysis.")
        return False, None, None

    # Validate Inputs
    model_info = next((item for item in models if item["name"] == selected_model_name), None)
    if not model_info:
        log_func(f"AI Error: Selected model '{selected_model_name}' not found in configuration.")
        messagebox.showerror("Model Error", f"Model '{selected_model_name}' is not a valid selection.")
        return False, None, None
    model_id, model_display_name = model_info['id'], model_info['name']

    if not query_text:
        log_func("AI Error: Query text is empty.");
        messagebox.showwarning("Input Error", "Please enter a query for the AI.")
        return False, None, None
    if not game_name or not steam_app_id or not steam_app_id.isdigit():
        messagebox.showwarning("Input Error", "A valid Game Name and Steam ID are required.")
        return False, None, None

    # Get game folder path (using imported function)
    game_folder_path = get_game_folder_path(game_name, steam_app_id, log_func)
    if not game_folder_path:
        # Error logged/shown by get_game_folder_path
        return False, None, None

    # Determine Input File based on flag
    folder_basename = os.path.basename(game_folder_path)
    if use_optimized_file:
        input_filename = os.path.join(game_folder_path, f"{folder_basename}_reviews_optimized.txt")
        file_description = "optimized review"
        log_func(f"Preparing to send OPTIMIZED reviews ({os.path.basename(input_filename)}) to AI...")
    else:
        input_filename = os.path.join(game_folder_path, f"{folder_basename}_reviews.txt")
        file_description = "original scraped review"
        log_func(f"Preparing to send ORIGINAL reviews ({os.path.basename(input_filename)}) to AI...")

    # Define output file paths within the game folder
    full_response_txt_filename = os.path.join(game_folder_path, f"{folder_basename}_ai_response_text.txt")
    extracted_csv_filename = os.path.join(game_folder_path, f"{folder_basename}_ai_extracted_data.csv")
    extracted_xlsx_filename = os.path.join(game_folder_path, f"{folder_basename}_ai_extracted_data.xlsx")

    # Check Input File exists
    if not os.path.exists(input_filename):
        log_func(f"AI Error: Input file missing: {os.path.basename(input_filename)}")
        messagebox.showwarning("File Missing", f"The required {file_description} file was not found.\nRun the corresponding step (Scrape or Optimize) first.") # noqa
        return False, None, None

    log_func(f"Preparing AI request for model: {model_display_name} ({model_id})...")
    parsed_csv_data = None
    full_generated_text_api = None
    text_for_file_display = None
    overall_success = False
    csv_saved = False
    txt_saved = False
    reviews_text = ""

    try: # Main try for interaction (Read file -> Optional Warn -> API -> Process)
        # --- Read Input File ---
        try:
            log_func(f"Reading {file_description} file: {os.path.basename(input_filename)}")
            with open(input_filename, "r", encoding="utf-8") as f:
                reviews_text = f.read()
            if not reviews_text.strip():
                # Raise error if file is empty or only whitespace
                raise ValueError("Input file is empty or contains only whitespace.")
            log_func(f"Read {len(reviews_text):,} characters from '{os.path.basename(input_filename)}'.")
        except (IOError, ValueError) as e:
            log_func(f"AI Error: Cannot read or input file is empty: {e}")
            messagebox.showerror("File Error", f"Cannot read the {file_description} file or it is empty:\n{os.path.basename(input_filename)}") # noqa
            return False, None, None

        # --- Token Warning (ONLY for ORIGINAL file) ---
        if not use_optimized_file:
            # Simple word count estimation (very rough)
            estimated_tokens = len(reviews_text.split())
            log_func(f"Estimated tokens for original file (word count): ~{estimated_tokens:,}")
            # Define a threshold for warning - adjust as needed
            token_warning_threshold = 700_000 # Example: warn if over ~700k words
            # Note: Gemini 1.5 Pro has a large context, but requests can still timeout or be costly.
            # Gemini Flash has smaller limits. Adjust based on typical model usage.
            # The API payload itself has a size limit too (e.g., 2MB for generateContent).

            if estimated_tokens > token_warning_threshold:
                warning_message = (
                    f"The selected ORIGINAL review file is large (~{estimated_tokens:,} estimated words/tokens).\n\n"
                    f"Sending it to the AI might:\n"
                    f"- Take a long time\n"
                    f"- Consume significant API quota/cost\n"
                    f"- Potentially exceed model context limits or request timeouts\n\n"
                    f"Using the OPTIMIZED file (if available) is recommended for large inputs.\n\n"
                    f"Proceed with the ORIGINAL file anyway?"
                )
                if not messagebox.askyesno("Large Input Warning", warning_message, icon='warning'):
                    log_func("AI submission cancelled by user due to large original file warning.")
                    return False, None, None # User cancelled

        # --- Prepare API Call ---
        # Construct prompt
        # Consider providing more structure/instructions for CSV output if needed
        prompt_text = (
            f"You are analyzing Steam reviews for the game '{game_name}'.\n"
            f"Based *only* on the provided review text below, answer the following query:\n"
            f"QUERY: {query_text}\n\n"
            # Instruction for CSV extraction
            f"If the query asks for structured data (like pros/cons, feature mentions, bug types), "
            f"present that data as a standard CSV block enclosed ONLY by <CSV_START> and <CSV_END> tags. "
            f"Include a header row in the CSV data. Do not include the tags themselves within the CSV content.\n"
            f"Provide any textual explanation or summary *outside* of these CSV tags.\n\n"
            f"---\nREVIEW TEXT START\n---\n{reviews_text}\n---\nREVIEW TEXT END\n---"
        )

        # Define payload
        # Check model documentation for optimal maxOutputTokens; 8192 is large.
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "maxOutputTokens": 8192,
                # Add temperature, topP, topK if needed
                # "temperature": 0.7,
            },
            # Add safety settings if necessary (e.g., block fewer categories)
            # "safetySettings": [
            #     { "category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE" },
            #     # ... other categories
            # ]
        }

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}

        log_func(f"Sending request to Gemini model: {model_display_name}...")

        # --- Execute API Call ---
        generated_text_from_api = "Error: API call failed or no valid response received." # Default error
        finish_reason = "UNKNOWN"
        usage_metadata = {}
        response_data = None
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=300) # 5 min timeout
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)

            log_func(f"AI request successful (HTTP Status: {response.status_code}).")
            response_data = response.json()

            # --- Safely Parse API Response ---
            try:
                # Check for prompt feedback first (indicates blocking)
                prompt_feedback = response_data.get('promptFeedback')
                if prompt_feedback:
                    block_reason = prompt_feedback.get('blockReason')
                    if block_reason:
                         safety_ratings = prompt_feedback.get('safetyRatings', [])
                         log_func(f"AI Error: Request blocked by API. Reason: {block_reason}. Safety Ratings: {safety_ratings}") # noqa
                         generated_text_from_api = f"Error: Content blocked by API safety filters (Reason: {block_reason}). Please modify the input reviews or query." # noqa
                         # Don't proceed with candidate parsing if blocked
                         raise ValueError("Content blocked by API") # Use exception to jump to outer catch

                # If not blocked, proceed to parse candidates
                candidates = response_data.get('candidates')
                if candidates and isinstance(candidates, list) and len(candidates) > 0:
                    candidate = candidates[0] # Get the first candidate
                    content = candidate.get('content', {})
                    parts = content.get('parts', [])
                    if parts and isinstance(parts, list) and len(parts) > 0:
                        generated_text_from_api = parts[0].get('text', "Error: Text part missing in API response.") # noqa
                    else:
                        generated_text_from_api = "Error: No 'parts' found in API response content."

                    finish_reason = candidate.get('finishReason', 'UNKNOWN')
                    safety_ratings = candidate.get('safetyRatings', []) # Log safety ratings even if not blocked
                    log_func(f"AI Finish Reason: {finish_reason}. Safety Ratings: {safety_ratings}")
                    if finish_reason not in ["STOP", "MAX_TOKENS", "UNSPECIFIED", None]: # Log unusual reasons
                          log_func(f"Warning: Unusual finish reason received: '{finish_reason}'. Response might be incomplete or malformed.") # noqa
                    elif finish_reason == "MAX_TOKENS":
                         log_func(f"Warning: AI response potentially truncated due to maximum output tokens limit.") # noqa

                    usage_metadata = response_data.get('usageMetadata', {})
                    log_func(f"API Usage Metadata: {usage_metadata}")

                else:
                     generated_text_from_api = "Error: No valid 'candidates' found in API response."

            except ValueError as block_e:
                 # This catches the "Content blocked" exception raised above
                 # Error message already set in generated_text_from_api
                 pass # Continue to processing/saving the error message
            except Exception as parse_e:
                log_func(f"Error parsing successful AI response structure: {parse_e}\nResponse Snippet: {str(response_data)[:500]}") # noqa
                generated_text_from_api = f"Error: Failed to parse the structure of the AI response. {parse_e}"

        # Handle API request exceptions
        except requests.exceptions.Timeout:
            log_func("AI Error: Request timed out.")
            messagebox.showerror("API Error", "The request to the AI timed out. The server might be busy or the request too large/long.") # noqa
            return False, None, None
        except requests.exceptions.HTTPError as http_e:
             log_func(f"AI Error: HTTP Error: {http_e.response.status_code} {http_e.response.reason}")
             error_details = http_e.response.text # Default to raw text
             try: # Try to parse JSON error details from Google API
                 error_json = http_e.response.json()
                 error_details = error_json.get('error', {}).get('message', error_details)
             except json.JSONDecodeError:
                 pass # Keep raw text if JSON parsing fails
             log_func(f"API Error Details: {error_details[:500]}") # Log first 500 chars
             messagebox.showerror("API Error", f"AI request failed (HTTP {http_e.response.status_code}).\nDetails: {error_details[:300]}...") # noqa
             return False, None, None
        except requests.exceptions.RequestException as req_e:
            log_func(f"AI Error: Network or request failed: {req_e}")
            messagebox.showerror("API Error", f"Could not communicate with the AI service.\nCheck network connection.\nError: {req_e}") # noqa
            return False, None, None
        except Exception as e_api_call:
             log_func(f"AI Error: Unexpected error during API call: {e_api_call}\n{traceback.format_exc()}")
             messagebox.showerror("API Error", f"An unexpected error occurred during the AI request:\n{e_api_call}")
             return False, None, None


        # --- Process Result ---
        full_generated_text_api = generated_text_from_api # Store whatever text we got (could be an error message)

        # Prepare text for file display (excluding CSV block if present)
        text_for_file_display = full_generated_text_api # Default to full response
        start_tag = "<CSV_START>"; end_tag = "<CSV_END>"
        start_index = full_generated_text_api.find(start_tag)
        end_index = full_generated_text_api.find(end_tag)

        csv_content_str = None # Initialize CSV content string

        # Check if tags exist and are ordered correctly
        if start_index != -1 and end_index != -1 and start_index < end_index:
             log_func("Found <CSV_START> and <CSV_END> tags in response.")
             # Extract text before, between, and after tags
             text_before_csv = full_generated_text_api[:start_index].rstrip()
             csv_content_str = full_generated_text_api[start_index + len(start_tag):end_index].strip() # Extract CSV content
             text_after_csv = full_generated_text_api[end_index + len(end_tag):].lstrip()

             # Construct the text for display, replacing the CSV block
             text_for_file_display = text_before_csv
             if text_before_csv: text_for_file_display += "\n\n"
             text_for_file_display += "[CSV data extracted - see 'Extracted Data' tab or saved files]"
             if text_after_csv: text_for_file_display += "\n\n" + text_after_csv
             text_for_file_display = text_for_file_display.strip()
        else:
             log_func("CSV start/end tags not found or incorrectly ordered in the response.")
             # text_for_file_display remains the full_generated_text_api

        # Save Modified Text (excluding CSV block) to TXT file
        try:
            log_func(f"Saving AI response text (excluding CSV) to: '{os.path.basename(full_response_txt_filename)}'")
            with open(full_response_txt_filename, "w", encoding="utf-8") as txt_file:
                txt_file.write(text_for_file_display)
            log_func("Successfully saved AI response text file.")
            txt_saved = True
        except IOError as io_e:
            log_func(f"Error saving AI response text file: {io_e}")
            messagebox.showwarning("File Warning", f"Could not save the AI's textual response to a file:\n{io_e}")
            # Continue processing, but txt_saved remains False

        # --- Extract, Parse, Save CSV & Generate XLSX ---
        # Only attempt if we found CSV tags and the API didn't return an initial error message
        if csv_content_str and not full_generated_text_api.startswith("Error:"):
            log_func("Attempting to parse and save extracted CSV data...")
            try: # Inner try block for CSV processing and saving
                # Use StringIO to treat the string as a file for the csv reader
                csvfile = io.StringIO(csv_content_str)
                reader = csv.reader(csvfile)
                # Read all rows, filter out rows that are completely empty
                parsed_csv_data = [row for row in reader if any(field.strip() for field in row)]

                if parsed_csv_data:
                    log_func(f"Parsed {len(parsed_csv_data)} rows from CSV block.")
                    # Save the parsed data to the CSV file
                    with open(extracted_csv_filename, "w", encoding="utf-8", newline="") as extracted_f:
                        writer = csv.writer(extracted_f, quoting=csv.QUOTE_MINIMAL)
                        writer.writerows(parsed_csv_data)
                    log_func(f"Extracted CSV data saved to: '{os.path.basename(extracted_csv_filename)}'")
                    csv_saved = True

                    # Attempt to generate XLSX from the saved CSV
                    log_func("Attempting to generate XLSX file from CSV...")
                    # Import generate_xlsx_from_csv from file_handler here or ensure it's imported globally
                    xlsx_success = generate_xlsx_from_csv(extracted_csv_filename, extracted_xlsx_filename, log_func)
                    if xlsx_success:
                        log_func(f"Successfully generated XLSX file: '{os.path.basename(extracted_xlsx_filename)}'")
                    else:
                        log_func("XLSX generation skipped or failed (check previous logs).")

                else:
                    log_func("Warning: CSV content between tags was empty or contained only empty fields after parsing.")
                    parsed_csv_data = None # Ensure it's None if no valid data

            # Handle errors during CSV parsing or file writing
            except csv.Error as csv_e:
                log_func(f"Error parsing content between CSV tags: {csv_e}")
                messagebox.showwarning("CSV Parsing Error", f"Could not parse the data found between <CSV_START> and <CSV_END> tags.\nPlease check the raw AI response if needed.\nError: {csv_e}") # noqa
                parsed_csv_data = None
            except IOError as io_e_csv:
                log_func(f"Error writing extracted CSV data to file: {io_e_csv}")
                messagebox.showerror("File Error", f"Could not save the extracted CSV data:\n{io_e_csv}")
                parsed_csv_data = None # Mark as failed
            except Exception as e_csv_proc:
                log_func(f"Unexpected error during CSV processing/saving: {e_csv_proc}\n{traceback.format_exc()}")
                messagebox.showerror("Error", f"An unexpected error occurred while processing the CSV data:\n{e_csv_proc}")
                parsed_csv_data = None
        elif not csv_content_str and not full_generated_text_api.startswith("Error:"):
            # Log if no CSV tags were found but API call was otherwise okay
            log_func("No CSV data block found in the AI response to extract.")
        elif full_generated_text_api.startswith("Error:"):
             log_func("Skipping CSV extraction because the AI response indicated an error.")


        # --- Final Logging & Return ---
        log_func("-" * 20 + " AI Response Text (for GUI Tab) " + "-" * 20)
        log_func(text_for_file_display if text_for_file_display else "[No text processed/available]")
        log_func("-" * 20 + " End AI Response Text " + "-" * 22)

        # Overall success is true if *either* the text file was saved or the CSV was saved
        overall_success = txt_saved or csv_saved
        if overall_success:
             log_func("AI interaction and processing completed.")
        elif not full_generated_text_api.startswith("Error:"):
             # If no error from API, but nothing saved (e.g., file IO errors)
             log_func("AI interaction completed, but failed to save results.")
        # If API returned error, failure is implicit

        # Return the success flag, the parsed CSV data (list of lists, or None),
        # and the text intended for the display tab (which excludes the CSV block).
        return overall_success, parsed_csv_data, text_for_file_display

    # --- Outer Exception Handling ---
    except Exception as e_outer_ai:
        log_func(f"Unexpected critical error during AI interaction (outer scope): {e_outer_ai}\n{traceback.format_exc()}") # noqa
        messagebox.showerror("AI Error", f"An unexpected critical error occurred during the AI step:\n{e_outer_ai}")
        return False, None, None # Return failure state