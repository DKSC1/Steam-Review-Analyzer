# main.py
import customtkinter as ctk
from tkinter import messagebox
import sys
import os
from functools import partial
import traceback

# Import components
import config
import gui
import utils
# Import NEW handlers/managers
import process_handler
import api_handler
import file_handler # <-- Make sure file_handler is imported
import gui_manager # Import the class
import task_manager # Import the class

# --- Global State ---
API_KEY = config.API_KEY
DEFAULT_PROMPT = config.DEFAULT_MULTILINE_PROMPT
widgets = {}
log_func = lambda message: print(f"EarlyLog: {message}")

# --- Application Setup ---
def main():
    global widgets, API_KEY, DEFAULT_PROMPT, log_func

    # Basic setup
    try:
        ctk.set_appearance_mode(config.APPEARANCE_MODE)
        ctk.set_default_color_theme(config.COLOR_THEME)
        root = ctk.CTk()
    except Exception as setup_e:
        # Use standard print for critical early errors
        print(f"FATAL: Error initializing CustomTkinter: {setup_e}\n{traceback.format_exc()}", file=sys.stderr)
        # Attempt messagebox, might fail if Tk isn't working well
        try:
            messagebox.showerror("Init Error", f"Failed to initialize UI:\n{setup_e}")
        except Exception:
            pass # Ignore messagebox error if Tk fails
        sys.exit(1)

    # Define early logger
    def early_log(message):
        # Simple print for logging before GUI log box is ready
        print(f"EarlyLog: {message}")
    log_func = early_log

    # --- Build GUI ---
    try:
        # Pass None for callbacks initially, wired up later
        widgets = gui.build_gui(
            root, fetch_callback=None, scrape_callback=None, optimize_callback=None,
            ai_optimized_callback=None, ai_original_callback=None,
            load_callback=None, refresh_callback=None,
            stop_scrape_callback=None,
            strip_metadata_callback=None # <-- Add placeholder for new callback
        )
    except Exception as gui_build_e:
        early_log(f"FATAL: GUI Build Error: {gui_build_e}\n{traceback.format_exc()}")
        try:
            messagebox.showerror("GUI Error", f"Failed to build UI:\n{gui_build_e}")
        except Exception:
            pass # Ignore messagebox error
        try:
            root.quit() # Try to close window if partially opened
        except Exception:
            pass # Ignore quit error
        return # Exit main function

    # --- Initialize Managers ---
    try:
        # Create real logger AFTER widgets dict and log_box exist
        log_func = partial(utils.log_message, root, widgets['log_box'])

        # Instantiate Managers, passing dependencies
        gui_mgr = gui_manager.GuiManager(root, widgets, log_func)
        task_mgr = task_manager.TaskManager(root, widgets, gui_mgr, log_func)

        # Configure widget groups within TaskManager AFTER widgets created
        task_mgr.configure_widget_groups()

    except KeyError as ke:
         # Use early_log if log_func setup failed
         (log_func or early_log)(f"FATAL: Widget missing for managers: {ke}.")
         messagebox.showerror("GUI Error", f"Critical GUI component missing: {ke}")
         try: root.quit()
         except Exception: pass
         return
    except Exception as manager_setup_e:
         (log_func or early_log)(f"FATAL: Error setting up managers: {manager_setup_e}")
         messagebox.showerror("Setup Error", f"Cannot initialize core components: {manager_setup_e}")
         try: root.quit()
         except Exception: pass
         return

    # --- Load Config and Set Default Prompt ---
    try:
        API_KEY, DEFAULT_PROMPT = utils.load_config_from_file(log_func)
        ai_query_widget = widgets.get('ai_query_text')
        if DEFAULT_PROMPT and ai_query_widget and ai_query_widget.winfo_exists():
             ai_query_widget.insert("1.0", DEFAULT_PROMPT)
    except Exception as e:
         log_func(f"Error during config load/prompt insert: {e}")
         # Continue if possible, defaults might be used

    # Log initial status messages
    try:
        log_func("Application started.")
        log_func("Note: XLSX export requires 'pandas' and 'openpyxl'.")
        if not config.SUPPORTED_MODELS:
            log_func("ERROR: No AI models configured in config.py!")
        if not file_handler.PANDAS_AVAILABLE:
            log_func("Warn: Install pandas & openpyxl for XLSX output (`pip install pandas openpyxl`)")
    except Exception as log_e:
        # Fallback if logging fails unexpectedly
        print(f"Error during initial logging: {log_e}", file=sys.stderr)


    # --- Create Action Partials ---
    try:
        # Helper to get current settings
        get_current_settings = partial(utils.get_settings, widgets, config.DEFAULT_SETTINGS, log_func)

        # Pass stop_event from task_manager to scrape_action partial
        scrape_action = partial(process_handler.run_scraping, root, widgets, get_current_settings, log_func, task_mgr.stop_requested)
        optimize_action = partial(process_handler.run_optimization, widgets, get_current_settings, log_func)
        ai_optimized_action = partial(api_handler.send_to_ai, widgets, lambda: API_KEY, config.SUPPORTED_MODELS, log_func, use_optimized_file=True)
        ai_original_action = partial(api_handler.send_to_ai, widgets, lambda: API_KEY, config.SUPPORTED_MODELS, log_func, use_optimized_file=False)
        load_action = partial(file_handler.load_existing_data, widgets, log_func)
        # --- New Partial ---
        strip_action = partial(file_handler.strip_review_metadata, widgets, log_func) # <-- Create partial for stripping

    except Exception as partial_e:
         log_func(f"FATAL: Error creating action partials: {partial_e}")
         messagebox.showerror("Setup Error", f"Cannot create core actions: {partial_e}")
         try: root.quit()
         except Exception: pass
         return

    # --- Configure Button Commands using TaskManager ---
    try:
        # Fetch Name uses its own start method in TaskManager
        widgets['fetch_name_button'].configure(command=task_mgr.start_fetch_game_name)

        # Other actions use the generic start_action method
        widgets['scrape_button'].configure(command=partial(task_mgr.start_action, scrape_action, action_type="scrape"))
        widgets['optimize_button'].configure(command=partial(task_mgr.start_action, optimize_action, action_type="optimize"))
        widgets['ai_send_optimized_button'].configure(command=partial(task_mgr.start_action, ai_optimized_action, action_type="ai"))
        widgets['ai_send_original_button'].configure(command=partial(task_mgr.start_action, ai_original_action, action_type="ai"))
        widgets['load_button'].configure(command=partial(task_mgr.start_action, load_action, action_type="load"))
        # --- Configure New Button ---
        widgets['strip_button'].configure(command=partial(task_mgr.start_action, strip_action, action_type="strip")) # <-- Wire up strip button

        # Wire up STOP button to TaskManager method
        widgets['stop_button'].configure(command=task_mgr.request_stop)

        # Configure Filter Menu Command (calls GuiManager method)
        filter_menu = widgets.get('filter_menu')
        if filter_menu:
            filter_menu.configure(command=gui_mgr.on_filter_change)

        # Configure Refresh Button Command (calls GuiManager method)
        browser_refresh = widgets.get('refresh_browser_button')
        if browser_refresh:
            browser_refresh.configure(command=gui_mgr.populate_game_browser)

    except KeyError as ke:
         log_func(f"FATAL: GUI widget missing when configuring commands: {ke}.")
         messagebox.showerror("GUI Error", f"GUI component missing for command setup: {ke}")
         try: root.quit()
         except Exception: pass
         return
    except Exception as cmd_e:
         log_func(f"FATAL: Error configuring commands: {cmd_e}")
         messagebox.showerror("Setup Error", f"Cannot configure UI commands: {cmd_e}")
         try: root.quit()
         except Exception: pass
         return

    # --- Initial GUI Updates ---
    try:
        # Use GuiManager methods, scheduled via root.after
        root.after(200, gui_mgr.populate_game_browser)
        root.after(300, gui_mgr.update_token_display)
    except Exception as e:
        log_func(f"Error scheduling initial GUI updates: {e}")
        # Try immediate population if scheduling fails
        try:
            gui_mgr.populate_game_browser()
            gui_mgr.update_token_display()
        except Exception as pop_e:
            log_func(f"Error populating GUI immediately after schedule failure: {pop_e}")

    # --- Start Main Loop ---
    try:
        root.mainloop()
    except Exception as mainloop_e:
         # Log error if mainloop itself fails (less common)
         log_func(f"Error during main loop execution: {mainloop_e}\n{traceback.format_exc()}")

# --- Run Application ---
if __name__ == "__main__":
    # Overall try-except for the main entry point
    try:
        main()
    except ImportError as e:
         # Use standard print for critical errors before GUI might be ready
         print(f"Fatal Error: Missing required module. {e}\n{traceback.format_exc()}", file=sys.stderr)
         print("Ensure required libraries (customtkinter, requests, etc.) and local modules are installed/present.", file=sys.stderr)
         # Attempt messagebox, might fail
         try: messagebox.showerror("Startup Error", f"Missing required library: {e}")
         except Exception: pass
         sys.exit(1)
    except Exception as e:
         # Catch any other unexpected startup errors
         print(f"Fatal Error during startup.\n{traceback.format_exc()}", file=sys.stderr)
         try: messagebox.showerror("Startup Error", f"Critical startup error:\n{e}")
         except Exception: pass
         sys.exit(1)