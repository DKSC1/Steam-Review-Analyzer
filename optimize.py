import re
import string
import os
import argparse # <--- Import argparse
import sys      # <--- Import sys for exit

# Allowed symbols that should be kept even if non-ASCII.
ALLOWED_EMOJIS = {'✅', '❌', '☑', '☐', '👍', '👎'} # Added thumbs up/down

# Define punctuation characters to strip from token ends.
PUNCTUATION_TO_STRIP = string.punctuation

# Default Token threshold (approximate) - stop processing if estimated tokens exceed this.
DEFAULT_TOKEN_THRESHOLD = 950000 # ~3.8 million characters

def clean_line(line):
    """
    Cleans a single review line:
    1. Removes URLs (http/https/www).
    2. Collapses repeating punctuation/symbols (e.g., "!!!" -> "!").
    3. Removes tokens containing disallowed non-ASCII characters (aggressive).
    4. Strips leading/trailing punctuation from tokens.
    5. Removes tokens that become empty after stripping.
    6. Normalizes whitespace (collapses multiple spaces, trims).
    """
    # Step 1: Remove URLs. Handles http, https, and www. More robust regex.
    line = re.sub(r'\b(?:https?://|www\.)\S+\b', '', line, flags=re.IGNORECASE)

    # Step 2: Collapse repeating non-alphanumeric symbols (excluding emojis in ALLOWED_EMOJIS).
    # This is tricky. Let's focus on common repeating punctuation first.
    line = re.sub(r'([.,!?;:-])\1+', r'\1', line)
    # Collapse sequences of 3 or more identical symbols if needed (less aggressive)
    # line = re.sub(r'([^a-zA-Z0-9\s])\1{2,}', r'\1', line)

    # Tokenize the line
    try:
        tokens = line.split()
    except Exception as e:
        # Handle rare cases where split might fail on weird input
        print(f"Warning: Could not split line: {line[:50]}... Error: {e}", file=sys.stderr)
        return "" # Return empty if split fails

    cleaned_tokens = []

    for token in tokens:
        # Step 3: Check for disallowed non-ASCII chars.
        # Allow ASCII (0-127) and specific emojis.
        is_token_valid = True
        for ch in token:
            char_ord = ord(ch)
            if char_ord > 127 and ch not in ALLOWED_EMOJIS:
                is_token_valid = False
                break # No need to check further characters in this token
        if not is_token_valid:
            continue # Skip the entire token

        # Step 4: Strip leading/trailing punctuation.
        cleaned_token = token.strip(PUNCTUATION_TO_STRIP)

        # Step 5: Remove tokens that are now empty.
        if not cleaned_token:
            continue

        # Optional Step: Convert to lowercase (can reduce token count slightly)
        # cleaned_token = cleaned_token.lower()

        cleaned_tokens.append(cleaned_token)

    # Rejoin tokens and normalize whitespace
    # Step 6: Join with single spaces, then strip leading/trailing whitespace.
    cleaned_line = ' '.join(cleaned_tokens)
    # No need for re.sub for spaces if using ' '.join
    cleaned_line = cleaned_line.strip()

    return cleaned_line

def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Clean and optimize review text file, limiting by token count.")
    parser.add_argument('--threshold', type=int, default=DEFAULT_TOKEN_THRESHOLD,
                        help=f"Approximate maximum token threshold to keep (default: {DEFAULT_TOKEN_THRESHOLD})")

    args = parser.parse_args()

    # --- Use Parsed Argument ---
    token_limit = args.threshold

    input_filename = 'reviews.txt'
    output_filename = 'reviews2.txt'

    print(f"--- Review Optimizer ---")
    print(f"Input File: {input_filename}")
    print(f"Output File: {output_filename}")
    print(f"Token Threshold: ~{token_limit}")
    print("-" * 30)

    # Check if input file exists
    if not os.path.exists(input_filename):
        print(f"Error: Input file '{input_filename}' not found.", file=sys.stderr)
        # Create an empty output file to potentially avoid errors downstream in app.py
        try:
            with open(output_filename, 'w', encoding='utf-8') as outfile:
                pass # Create empty file
            print(f"Created empty output file '{output_filename}'.")
        except IOError as e:
            print(f"Error: Could not create empty output file '{output_filename}': {e}", file=sys.stderr)
        sys.exit(1) # Exit with error code if input is missing

    total_reviews_processed = 0
    total_reviews_kept = 0
    total_words_kept = 0
    # total_letters_kept = 0 # Less relevant than token count
    total_tokens_estimate = 0
    threshold_reached = False

    try:
        # Process line-by-line and write directly to output
        with open(input_filename, 'r', encoding='utf-8') as infile, \
             open(output_filename, 'w', encoding='utf-8') as outfile:

            for i, line in enumerate(infile):
                total_reviews_processed += 1
                cleaned = clean_line(line)

                # Skip empty lines after cleaning
                if not cleaned:
                    continue

                # Estimate token count (1 token ≈ 4 chars heuristic)
                # Use length of the *cleaned* line for estimation
                current_token_estimate = max(1, len(cleaned) // 4)

                # Check token threshold *before* writing
                if total_tokens_estimate + current_token_estimate > token_limit:
                    print(f"\nToken threshold (~{token_limit}) reached near line {i+1}.")
                    print("Stopping further review processing.")
                    threshold_reached = True
                    break # Stop processing more lines

                # Write the cleaned review to the output file
                try:
                    outfile.write(cleaned + "\n")
                except Exception as e:
                     print(f"\nError writing line {i+1} to output file: {e}", file=sys.stderr)
                     # Decide whether to continue or stop on write error
                     print("Stopping processing due to write error.", file=sys.stderr)
                     sys.exit(1)


                # Update cumulative counts for kept reviews
                total_reviews_kept += 1
                words = cleaned.split() # Split again for word count
                total_words_kept += len(words)
                # total_letters_kept += sum(c.isalpha() for c in cleaned)
                total_tokens_estimate += current_token_estimate

                # Print progress periodically
                if (total_reviews_kept) % 500 == 0: # Update based on kept reviews
                    print(f"Processed {total_reviews_processed} lines, Kept {total_reviews_kept} reviews, Approx Tokens: {total_tokens_estimate}", end='\r')

    except IOError as e:
        print(f"\nError processing files: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred during processing: {e}", file=sys.stderr)
        import traceback
        print(traceback.format_exc(), file=sys.stderr) # Print full traceback for debugging
        sys.exit(1)

    # --- Final Summary ---
    print("\n" + "="*30) # Clear progress line
    if threshold_reached:
        print("Processing stopped due to token limit.")
    else:
        print("Processing complete (reached end of input file or error).") # Added 'or error'
    print(f"Total lines processed from input: {total_reviews_processed}")
    print(f"Total non-empty reviews kept:    {total_reviews_kept}")
    print(f"Total words kept (approx):       {total_words_kept}")
    # print(f"Total letters kept:              {total_letters_kept}")
    print(f"Approximate input tokens kept:   {total_tokens_estimate}") # This is the important number
    print(f"Output written to:               '{output_filename}'")
    print("="*30)
    sys.exit(0) # Explicitly exit with success


if __name__ == '__main__':
    main()