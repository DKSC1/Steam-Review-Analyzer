# reviews.py
import requests
import urllib.parse
import time
import json
import sys
import argparse
from datetime import datetime
import os # Import os for flush
import traceback

# --- Default Configuration ---
# (Defaults remain the same)
DEFAULT_MAX_REVIEWS = 30000
DEFAULT_NUM_PER_PAGE = 100
DEFAULT_SLEEP_DURATION = 1.5
OUTPUT_FILENAME = 'reviews.txt'
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_LANGUAGE = "all"
DEFAULT_REVIEW_TYPE = "all"
DEFAULT_PURCHASE_TYPE = "all"
DEFAULT_DATE_RANGE = "0"
DEFAULT_PLAYTIME = "0"
DEFAULT_FILTER_BY = "all"
DEFAULT_BETA = "0"

# --- Helper Functions ---
# (get_validated_app_id remains the same)
def get_validated_app_id():
    try: app_id_str = input(); return app_id_str if app_id_str.isdigit() else None
    except EOFError: print("reviews.py: Error: No App ID via stdin.", file=sys.stderr); return None # noqa

# (get_initial_game_data remains the same)
def get_initial_game_data(session, app_id):
    details = {"name": f"Game (ID: {app_id})", "release_date": "N/A", "review_desc": "N/A", "total_reviews": "N/A"} # noqa
    try: # AppDetails
        details_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english" # noqa
        response = session.get(details_url, timeout=15); response.raise_for_status(); data = response.json(); # noqa
        if data and str(app_id) in data and data[str(app_id)].get('success'):
            app_data = data[str(app_id)]['data']
            details["name"] = app_data.get('name', details["name"])
            if 'release_date' in app_data and app_data['release_date'].get('date'): details["release_date"] = app_data['release_date']['date'] # noqa
    except Exception as e: print(f"reviews.py: Warn: Failed app details: {e}", file=sys.stderr) # noqa
    try: # Review Summary
        summary_url = f'https://store.steampowered.com/appreviews/{app_id}' # noqa
        params = {'json': '1', 'num_per_page': '0', 'language': 'all'}
        response = session.get(summary_url, params=params, timeout=15); response.raise_for_status(); data = response.json(); # noqa
        if data and data.get('success') == 1 and 'query_summary' in data:
            summary = data['query_summary']
            details["review_desc"] = summary.get('review_score_desc', 'N/A')
            details["total_reviews"] = str(summary.get('total_reviews', 'N/A'))
    except Exception as e: print(f"reviews.py: Warn: Failed review summary: {e}", file=sys.stderr) # noqa
    return details

# (format_review_for_file remains the same)
def format_review_for_file(review_dict):
    try:
        review_text = review_dict.get('review', ''); timestamp = review_dict.get('timestamp_created', 0); # noqa
        playtime_minutes = review_dict.get('author', {}).get('playtime_forever', 0); voted_up = review_dict.get('voted_up', False); # noqa
        date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d') if timestamp > 0 else "Unknown Date" # noqa
        playtime_hours = playtime_minutes // 60; playtime_rem_mins = playtime_minutes % 60; # noqa
        playtime_str = f"{playtime_hours}h {playtime_rem_mins}m"
        rec_str = "Positive" if voted_up else "Negative"
        header = f"[Date: {date_str} | Playtime: {playtime_str} | Rec: {rec_str}] "
        cleaned_text = review_text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ') # noqa
        return header + cleaned_text + '\n'
    except Exception as e:
        rec_id = review_dict.get('recommendationid', 'N/A')
        print(f"reviews.py: Warn: Format review ID {rec_id}: {e}", file=sys.stderr) # noqa
        return f"[Formatting Error] {review_dict.get('review', '')}\n"


# --- Main Script ---
if __name__ == "__main__":
    # --- Argument Parsing (Unchanged) ---
    parser = argparse.ArgumentParser(description="Scrape Steam reviews.")
    parser.add_argument('--max', type=int, default=DEFAULT_MAX_REVIEWS, help=f"Max reviews (default: {DEFAULT_MAX_REVIEWS})") # noqa
    parser.add_argument('--num', type=int, default=DEFAULT_NUM_PER_PAGE, choices=range(1, 101), metavar='[1-100]', help=f"Reviews per page (default: {DEFAULT_NUM_PER_PAGE})") # noqa
    parser.add_argument('--sleep', type=float, default=DEFAULT_SLEEP_DURATION, help=f"Sleep (sec, default: {DEFAULT_SLEEP_DURATION})") # noqa
    parser.add_argument('--language', type=str, default=DEFAULT_LANGUAGE, help=f"Language filter (default: {DEFAULT_LANGUAGE})") # noqa
    parser.add_argument('--review_type', type=str, default=DEFAULT_REVIEW_TYPE, choices=['all', 'positive', 'negative'], help=f"Review type filter (default: {DEFAULT_REVIEW_TYPE})") # noqa
    parser.add_argument('--purchase_type', type=str, default=DEFAULT_PURCHASE_TYPE, choices=['all', 'steam', 'non_steam_purchase'], help=f"Purchase type filter (default: {DEFAULT_PURCHASE_TYPE})") # noqa
    parser.add_argument('--day_range', type=str, default=DEFAULT_DATE_RANGE, help=f"Date range filter (days, 0=all; default: {DEFAULT_DATE_RANGE})") # noqa
    parser.add_argument('--playtime', type=str, default=DEFAULT_PLAYTIME, help=f"Min playtime filter (hours, 0=any; default: {DEFAULT_PLAYTIME})") # noqa
    parser.add_argument('--filter_by', type=str, default=DEFAULT_FILTER_BY, choices=['all', 'recent', 'updated'], help=f"Filter/Sort order (default: {DEFAULT_FILTER_BY})") # noqa
    parser.add_argument('--beta', type=str, default=DEFAULT_BETA, choices=['0', '1'], help=f"Include beta reviews (0=No, 1=Yes; default: {DEFAULT_BETA})") # noqa
    args = parser.parse_args()

    # --- Use Parsed Arguments (Unchanged) ---
    max_reviews_to_fetch = args.max; num_per_page_to_fetch = args.num; sleep_between_requests = args.sleep; request_timeout_seconds = DEFAULT_REQUEST_TIMEOUT; # noqa
    max_iterations = (max_reviews_to_fetch // num_per_page_to_fetch) + 50 if num_per_page_to_fetch > 0 else max_reviews_to_fetch + 50 # noqa

    # --- Get App ID ---
    app_id = get_validated_app_id()
    if app_id is None: sys.exit(1) # Error printed in helper

    # --- Initialize state ---
    cursor = '*'; seen_cursors = {cursor}; total_fetched = 0; batch_num = 0; api_errors = 0; output_file_handle = None; # noqa

    # --- Logging Setup (Unchanged) ---
    print(f"--- Steam Review Scraper ---"); print(f"App ID: {app_id}"); print(f"Target: {max_reviews_to_fetch}"); print(f"Per Page: {num_per_page_to_fetch}"); print(f"Sleep: {sleep_between_requests}s"); print(f"Timeout: {request_timeout_seconds}s"); print(f"Output: {OUTPUT_FILENAME}"); print("-" * 10 + " Filters " + "-" * 10); print(f"Lang: {args.language}"); print(f"Type: {args.review_type}"); print(f"Purchase: {args.purchase_type}"); print(f"Date: {args.day_range}"); print(f"Playtime: {args.playtime}"); print(f"FilterBy: {args.filter_by}"); print(f"Beta: {'Yes' if args.beta == '1' else 'No'}"); print("-" * 30); # noqa

    try: # Wrap main logic in try/finally
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'Mozilla/5.0 SteamReviewAnalyzer/1.3'})
            print("Fetching game details for header..."); game_details = get_initial_game_data(session, app_id); # noqa
            print(f"Opening output file: {OUTPUT_FILENAME}"); output_file_handle = open(OUTPUT_FILENAME, 'w', encoding='utf-8'); # noqa
            output_file_handle.write("="*50 + "\n"); output_file_handle.write(f"Game: {game_details['name']}\n"); output_file_handle.write(f"AppID: {app_id}\n"); output_file_handle.write(f"Release Date: {game_details['release_date']}\n"); output_file_handle.write(f"Review Score: {game_details['review_desc']} ({game_details['total_reviews']} total)\n"); output_file_handle.write(f"Scrape Target: {max_reviews_to_fetch}\n"); output_file_handle.write(f"Scrape Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"); output_file_handle.write("="*50 + "\n\n"); # noqa
            output_file_handle.flush() # Flush header immediately

            print(f"Starting review scraping loop...")

            # --- Main Fetch Loop ---
            while total_fetched < max_reviews_to_fetch and batch_num < max_iterations:
                batch_num += 1
                print(f"\nBatch {batch_num}: Fetching (Cursor: '{str(cursor)[:20]}...'). Total written: {total_fetched}", end='')  # noqa

                params = { 'json': '1', 'language': args.language, 'review_type': args.review_type, 'purchase_type': args.purchase_type, 'filter': args.filter_by, 'day_range': args.day_range, 'playtime_filter_min': args.playtime, 'review_beta_enabled': args.beta, 'num_per_page': str(num_per_page_to_fetch), 'cursor': cursor }; url = f'https://store.steampowered.com/appreviews/{app_id}'; # noqa

                # API Request with Retries (Unchanged logic)
                response_data = None
                try: response = session.get(url, params=params, timeout=request_timeout_seconds); print(f" -> HTTP {response.status_code}", end=''); response.raise_for_status(); response_data = response.json(); api_errors = 0; # noqa
                except requests.exceptions.Timeout:
                    print(f"\nreviews.py: Error: Timeout.", file=sys.stderr)
                    api_errors += 1
                    if api_errors >= 3:
                        print("Timeout limit.", file=sys.stderr)
                        sys.exit(1)
                    sleep_time = sleep_between_requests * (2 ** api_errors)
                    print(f"Retrying after {sleep_time:.1f}s...", file=sys.stderr)
                    time.sleep(sleep_time)
                    batch_num -= 1
                    continue  # noqa
                except requests.exceptions.RequestException as e:
                    print(f"\nreviews.py: Error: Network: {e}", file=sys.stderr)
                    api_errors += 1
                    if api_errors >= 3:
                        print("Network limit.", file=sys.stderr)
                        sys.exit(1)
                    sleep_time = sleep_between_requests * (2 ** api_errors)
                    print(f"Retrying after {sleep_time:.1f}s...", file=sys.stderr)
                    time.sleep(sleep_time)
                    batch_num -= 1
                    continue
                except json.JSONDecodeError:
                    print(f"\nreviews.py: Error: Invalid JSON.", file=sys.stderr)
                    print(f"Response: {response.text[:500]}", file=sys.stderr)
                    print("Stopping.", file=sys.stderr)
                    sys.exit(1)

                # Check API Success (Unchanged logic)
                api_success_code = response_data.get('success')
                next_cursor_from_data = response_data.get('cursor')  # noqa

                if api_success_code != 1:
                    print(f"\nAPI fail code: {api_success_code}", file=sys.stderr)
                    print(f"Query: {response_data.get('query_summary', {})}", file=sys.stderr)
                    if not response_data.get('reviews') and next_cursor_from_data is None:
                        print("API fail but looks like end. Finishing.", file=sys.stderr)
                        print("BREAKING: API fail, no reviews/cursor.", file=sys.stderr)
                        break
                    else:
                        print("Stopping: API failure code.", file=sys.stderr)
                        sys.exit(1)  # noqa

                # --- Process & WRITE Reviews ---
                new_reviews = response_data.get('reviews', [])
                num_in_batch = len(new_reviews)
                print(f", Got {num_in_batch}", end='') # Status update

                reviews_actually_written = 0
                if new_reviews:
                    reviews_to_process = new_reviews[:max(0, max_reviews_to_fetch - total_fetched)]
                    for review_dict in reviews_to_process:
                        formatted_line = format_review_for_file(review_dict)
                        try: output_file_handle.write(formatted_line); reviews_actually_written += 1; # noqa
                        except Exception as write_e: rec_id = review_dict.get('recommendationid', 'N/A'); print(f"\nWrite Error ID {rec_id}: {write_e}", file=sys.stderr); print("Stopping: Write error.", file=sys.stderr); sys.exit(1); # noqa

                    total_fetched += reviews_actually_written
                    print(f". Written: {reviews_actually_written}. Total: {total_fetched}/{max_reviews_to_fetch}") # noqa

                    # --- ADDED FLUSH ---
                    try:
                        output_file_handle.flush()
                        # Optionally sync to ensure OS writes to disk, might be slow:
                        # os.fsync(output_file_handle.fileno())
                    except Exception as flush_e:
                         # Log error but don't necessarily stop the whole process
                         print(f"\nreviews.py: Warn: Error flushing file buffer: {flush_e}", file=sys.stderr)
                    # --- END ADDED FLUSH ---

                else: # No new reviews in this batch
                     print(f". Total: {total_fetched}/{max_reviews_to_fetch}") # Still print total

                # --- Check Loop Termination Conditions (Unchanged logic) ---
                if not new_reviews and (next_cursor_from_data is None or next_cursor_from_data == ''): print("\nNo reviews/cursor. End.", file=sys.stderr); print("BREAKING: No reviews/cursor.", file=sys.stderr); break; # noqa
                if not new_reviews and next_cursor_from_data is not None and next_cursor_from_data != '':
                     if next_cursor_from_data != cursor:
                          if next_cursor_from_data in seen_cursors: print("\nRepeat cursor empty batch. Stop.", file=sys.stderr); print("BREAKING: Repeat cursor empty batch.", file=sys.stderr); break; # noqa
                          else: print("\nEmpty batch, new cursor.", file=sys.stderr); cursor = next_cursor_from_data; seen_cursors.add(cursor); print(f"Sleeping {sleep_between_requests}s..."); time.sleep(sleep_between_requests); continue; # noqa
                     else: print("\nEmpty batch, cursor same. End.", file=sys.stderr); print("BREAKING: Empty batch, cursor same.", file=sys.stderr); break; # noqa
                if total_fetched >= max_reviews_to_fetch: print(f"\nTarget reached ({max_reviews_to_fetch})."); print("BREAKING: Max reviews.", file=sys.stderr); break; # noqa
                if next_cursor_from_data and next_cursor_from_data != cursor:
                    if next_cursor_from_data in seen_cursors: print("\nRepeat cursor. Stop.", file=sys.stderr); print("BREAKING: Repeat cursor.", file=sys.stderr); break; # noqa
                    cursor = next_cursor_from_data; seen_cursors.add(cursor); # noqa
                elif not next_cursor_from_data or next_cursor_from_data == cursor: print("\nNo new/changed cursor. End.", file=sys.stderr); print("BREAKING: No new/changed cursor.", file=sys.stderr); break; # noqa

                # Sleep before next request
                print(f"Sleeping {sleep_between_requests}s...")
                time.sleep(sleep_between_requests)
            # --- End of while loop ---

        # --- Loop finished ---
        if batch_num >= max_iterations and total_fetched < max_reviews_to_fetch: print(f"\nWarn: Max iterations reached ({max_iterations}).", file=sys.stderr); # noqa
        print(f"\nScraping loop finished. Total reviews written: {total_fetched}")

    except Exception as main_e: # Catch errors outside loop
        print(f"\nreviews.py: CRITICAL ERROR: {main_e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr); sys.exit(1); # noqa

    finally:
        # --- Ensure file is closed ---
        if output_file_handle:
            try: output_file_handle.close(); print(f"Output file '{OUTPUT_FILENAME}' closed."); # noqa
            except Exception as close_e: print(f"Error closing output: {close_e}", file=sys.stderr); # noqa
        else: print("Notice: Output file not opened.", file=sys.stderr); # noqa

    print("\nScraping script execution complete.")
    sys.exit(0) # Success exit code