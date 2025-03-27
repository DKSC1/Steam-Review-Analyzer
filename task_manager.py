# task_manager.py
import threading
import traceback

# Assume utils.py is accessible
import utils

class TaskManager:
    """Handles running background tasks and coordinating GUI updates."""

    def __init__(self, root, widgets, gui_manager, log_func):
        self.root = root
        self.widgets = widgets
        self.gui_manager = gui_manager # Instance of GuiManager
        self.log_func = log_func
        self.widgets_to_disable_actions = []
        self.widgets_to_disable_fetch = []
        # --- ADDED Stop Event ---
        self.stop_requested = threading.Event()

    def configure_widget_groups(self):
        """Defines which widgets get disabled during operations."""
        try:
            # --- ADD 'strip_button' to the list ---
            action_buttons = [
                self.widgets['scrape_button'], self.widgets['stop_button'],
                self.widgets['optimize_button'], self.widgets['load_button'],
                self.widgets['strip_button'], # <-- Added strip_button here
                self.widgets['ai_send_optimized_button'], self.widgets['ai_send_original_button']
            ]
            setting_entries = [
                self.widgets['max_reviews_entry'], self.widgets['token_threshold_entry'],
                self.widgets['sleep_duration_entry'], self.widgets['num_per_page_entry']
            ]
            filter_widgets = [
                self.widgets.get('filter_language_combo'), self.widgets.get('filter_review_type_option'), # noqa
                self.widgets.get('filter_purchase_type_option'), self.widgets.get('filter_date_range_option'), # noqa
                self.widgets.get('filter_playtime_option'), self.widgets.get('filter_filter_by_option'), # noqa
                self.widgets.get('filter_beta_checkbox')
            ]
            other_controls = [
                self.widgets['fetch_name_button'], self.widgets['model_combobox'],
                self.widgets['game_name_entry'], self.widgets['steam_id_entry'],
                self.widgets.get('filter_menu'), self.widgets.get('refresh_browser_button'),
            ]

            base_list = action_buttons + setting_entries + filter_widgets + other_controls
            # Note: stop_button is handled specifically in start_action/check_thread
            self.widgets_to_disable_actions = [w for w in base_list if w]

            # Fetch disable list can remain the same for now
            self.widgets_to_disable_fetch = self.widgets_to_disable_actions

        except KeyError as ke:
            self.log_func(f"FATAL: GUI widget missing during TaskManager setup: {ke}.")
            raise
        except Exception as e:
            self.log_func(f"FATAL: Error setting widget groups in TaskManager: {e}")
            raise

    # --- Request Stop Method ---
    def request_stop(self):
        """Signals the currently running scraping task to stop."""
        if not self.stop_requested.is_set():
             self.log_func("Stop request initiated by user.")
             self.stop_requested.set()
             # Optionally disable the stop button immediately after clicking
             stop_button = self.widgets.get('stop_button')
             if stop_button:
                 try:
                     stop_button.configure(state="disabled", text="Stopping...")
                 except Exception:
                     pass # Ignore if widget gone

    # --- Fetch Game Name ---
    # (Unchanged methods: _perform_fetch_game_name_thread, _update_game_name_entry, start_fetch_game_name, _check_thread_simple) # noqa
    def _perform_fetch_game_name_thread(self):
        app_id_entry = self.widgets.get('steam_id_entry'); app_id = ""; fetched_name = None; # noqa
        try:
            if app_id_entry and app_id_entry.winfo_exists(): app_id = app_id_entry.get().strip() # noqa
            if not app_id or not app_id.isdigit(): self.log_func("Fetch Name skipped: Invalid ID."); return # noqa
            fetched_name = utils.fetch_game_name(app_id, self.log_func)
        except Exception as e: self.log_func(f"Error in fetch name thread: {e}") # noqa
        finally:
             if fetched_name and self.root and self.root.winfo_exists(): self.root.after(0, lambda name=fetched_name: self._update_game_name_entry(name)) # noqa
    def _update_game_name_entry(self, name):
         entry = self.widgets.get('game_name_entry')
         try:
              if entry and entry.winfo_exists(): entry.configure(state="normal"); entry.delete(0, "end"); entry.insert(0, name); # noqa
              else: self.log_func("Warn: Name entry gone before update.") # noqa
         except Exception as e: self.log_func(f"Error updating name entry: {e}") # noqa
    def start_fetch_game_name(self):
        self.log_func("Starting fetch name task...")
        self.gui_manager.set_widget_state(self.widgets_to_disable_fetch, "disabled")
        thread = threading.Thread(target=self._perform_fetch_game_name_thread, daemon=True)
        thread.start()
        self.root.after(100, lambda: self._check_thread_simple(thread, self.widgets_to_disable_fetch)) # noqa
    def _check_thread_simple(self, thread, widgets_to_enable):
        if not self.root or not self.root.winfo_exists(): self.log_func("Root destroyed, stopping check."); return # noqa
        if thread.is_alive(): self.root.after(100, lambda: self._check_thread_simple(thread, widgets_to_enable)) # noqa
        else:
            self.log_func("Fetch name task finished."); self.gui_manager.set_widget_state(widgets_to_enable, "normal"); game_name_entry = self.widgets.get('game_name_entry'); # noqa
            try:
                if game_name_entry and game_name_entry.winfo_exists(): game_name_entry.configure(state="normal") # noqa
            except Exception as e: self.log_func(f"Warn: Error ensuring game name state: {e}") # noqa

    # --- General Action Thread ---
    # MODIFIED: Added 'strip' to the list of simple boolean results
    def start_action(self, action_func, action_type="action"):
        """Starts a thread for actions, clearing stop event for scrape."""
        self.log_func(f"Starting task: {action_type}...")

        # --- Clear stop event specifically for scrape ---
        if action_type == "scrape":
            self.stop_requested.clear()
            self.log_func("Cleared stop request flag for new scrape.")

        # Disable general widgets
        self.gui_manager.set_widget_state(self.widgets_to_disable_actions, "disabled")

        # --- Enable Stop button ONLY for scrape ---
        stop_button = self.widgets.get('stop_button')
        if action_type == "scrape" and stop_button:
             try:
                  stop_button.configure(state="normal", text="Stop Scraping") # Enable and reset text
             except Exception as e:
                  self.log_func(f"Warn: Could not enable stop button: {e}")

        action_result = {"success": False, "data": None, "full_text": None}
        def thread_target_wrapper():
            try: result = action_func() # noqa
            except Exception as e: self.log_func(f"Critical error in background task ({action_type}): {e}\n{traceback.format_exc()}"); action_result["success"] = False; return # noqa
            # Unpack results based on action type
            if action_type in ["ai", "load"]:
                if isinstance(result, tuple) and len(result) == 3: action_result["success"], action_result["data"], action_result["full_text"] = result # noqa
                else: self.log_func(f"Warn: Bad return from {action_type}: {result}"); action_result["success"] = False # noqa
            elif action_type in ["scrape", "optimize", "strip"]: # <-- Added 'strip' here
                action_result["success"] = bool(result) # Expecting True/False
            else:
                action_result["success"] = bool(result) # Default assumption

        thread = threading.Thread(target=thread_target_wrapper, daemon=True)
        thread.start()
        self.root.after(100, lambda: self._check_thread_and_update(thread, action_result, action_type))

    # MODIFIED: Disable stop button and clear event on finish
    def _check_thread_and_update(self, thread, action_result, action_type):
        """Checks thread, handles GUI updates, manages stop button state."""
        if not self.root or not self.root.winfo_exists(): self.log_func("Root destroyed, stopping check."); return # noqa

        if thread.is_alive():
            self.root.after(100, lambda: self._check_thread_and_update(thread, action_result, action_type)) # noqa
        else:
            self.log_func(f"Task '{action_type}' finished.")

            # --- Always clear the stop event when ANY task finishes ---
            # Ensures it's reset even if scrape failed or was stopped
            self.stop_requested.clear()

            # --- Re-enable general widgets ---
            self.gui_manager.set_widget_state(self.widgets_to_disable_actions, "normal")

            # --- Specifically disable the stop button ---
            stop_button = self.widgets.get('stop_button')
            if stop_button:
                try:
                    stop_button.configure(state="disabled", text="Stop Scraping") # Disable and reset text
                except Exception as e:
                    self.log_func(f"Warn: Could not disable stop button: {e}")

            # Ensure game name entry is editable (redundant if in list, but safe)
            game_name_entry = self.widgets.get('game_name_entry')
            try:
                if game_name_entry and game_name_entry.winfo_exists(): game_name_entry.configure(state="normal") # noqa
            except Exception as e: self.log_func(f"Warn: Error ensuring game name state: {e}") # noqa

            # --- Update Right Panel (AI/Load) ---
            if action_type in ["ai", "load"]:
                action_succeeded = action_result.get("success", False)
                returned_csv_data = action_result.get("data"); returned_full_text = action_result.get("full_text"); # noqa
                if action_succeeded:
                    self.log_func(f"{action_type.capitalize()} task successful, updating results panel...") # noqa
                    self.gui_manager.update_spreadsheet(returned_csv_data)
                    self.gui_manager.update_ai_response_text(returned_full_text)
                else:
                    self.log_func(f"{action_type.capitalize()} task failed or no relevant data.") # noqa
                    self.gui_manager.update_spreadsheet(None)
                    self.gui_manager.update_ai_response_text(f"[{action_type.capitalize()} Failed / No Data Loaded]") # noqa

            # --- Update Token Display ---
            # Only update after scrape/optimize success, or AI/Load actions.
            # Stripping doesn't currently recalculate tokens, so no update needed.
            if (action_type in ["scrape", "optimize"] and action_result.get("success")) or \
               (action_type in ["ai", "load"]):
                 try: self.root.after(50, self.gui_manager.update_token_display) # noqa
                 except Exception as e: self.log_func(f"Error scheduling token update: {e}") # noqa

            self.log_func(f"Finished post-task updates for '{action_type}'.")