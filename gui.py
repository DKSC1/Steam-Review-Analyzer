# gui.py
import customtkinter as ctk
from tkinter import ttk

# Import filter options and defaults from config
from config import (
    SUPPORTED_MODELS, DEFAULT_SETTINGS, STEAM_LANGUAGES,
    STEAM_REVIEW_TYPES, STEAM_PURCHASE_TYPES, STEAM_DATE_RANGES,
    STEAM_PLAYTIME_FILTERS, STEAM_FILTER_BY
)

def build_gui(root, fetch_callback, scrape_callback, optimize_callback,
              ai_optimized_callback, ai_original_callback,
              load_callback, refresh_callback,
              stop_scrape_callback):
    """Creates and packs the GUI elements into the root window."""

    root.title("Steam Reviews Analyzer (Gemini CTk)")
    root.geometry("1350x920"); root.columnconfigure(0, weight=1, minsize=180); root.columnconfigure(1, weight=4); root.columnconfigure(2, weight=3); root.rowconfigure(0, weight=1); root.minsize(width=1100, height=850); # noqa
    widgets = {}

    # --- Far Left Frame ---
    # (Unchanged)
    browser_frame = ctk.CTkFrame(root); browser_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10); browser_frame.grid_columnconfigure(0, weight=1); browser_frame.grid_rowconfigure(1, weight=1); ctk.CTkLabel(browser_frame, text="Saved Games", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2)); widgets['game_browser_frame'] = ctk.CTkScrollableFrame(browser_frame, label_text=""); widgets['game_browser_frame'].grid(row=1, column=0, sticky="nsew", padx=5, pady=(2, 5)); widgets['game_browser_frame'].grid_columnconfigure(0, weight=1); widgets['refresh_browser_button'] = ctk.CTkButton(browser_frame, text="Refresh List", command=refresh_callback, height=25); widgets['refresh_browser_button'].grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5)); # noqa

    # --- Middle Frame ---
    # (Layout unchanged)
    main_frame = ctk.CTkFrame(root, fg_color="transparent"); main_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=10); main_frame.grid_columnconfigure(0, weight=1); main_frame.grid_rowconfigure(4, weight=1); main_frame.grid_rowconfigure(8, weight=1); # noqa

    # Input Frame (Row 0 - Unchanged)
    input_frame = ctk.CTkFrame(main_frame); input_frame.grid(row=0, column=0, sticky="ew", pady=(0,5)); input_frame.columnconfigure(1, weight=1); ctk.CTkLabel(input_frame, text="Game Name:", width=100, anchor="e").grid(row=0, column=0, pady=2, sticky="e"); widgets['game_name_entry'] = ctk.CTkEntry(input_frame); widgets['game_name_entry'].grid(row=0, column=1, pady=2, padx=(0,5), sticky="ew"); ctk.CTkLabel(input_frame, text="Steam ID:", width=100, anchor="e").grid(row=1, column=0, pady=2, sticky="e"); widgets['steam_id_entry'] = ctk.CTkEntry(input_frame, width=100); widgets['steam_id_entry'].grid(row=1, column=1, pady=2, padx=(0,5), sticky="ew"); widgets['fetch_name_button'] = ctk.CTkButton(input_frame, text="Fetch Name", command=fetch_callback, width=100); widgets['fetch_name_button'].grid(row=0, column=2, pady=2, padx=5, rowspan=2, sticky="ns"); # noqa

    # General Settings Frame (Row 1 - Unchanged)
    settings_frame = ctk.CTkFrame(main_frame); settings_frame.grid(row=1, column=0, sticky="ew", pady=5); settings_frame.columnconfigure((1, 3, 5, 7), weight=1); ctk.CTkLabel(settings_frame, text="Max Rev:", width=60).grid(row=0, column=0, padx=(5,0), pady=2, sticky="e"); widgets['max_reviews_entry'] = ctk.CTkEntry(settings_frame, width=70); widgets['max_reviews_entry'].insert(0, str(DEFAULT_SETTINGS['max_reviews'])); widgets['max_reviews_entry'].grid(row=0, column=1, padx=(0,5), pady=2, sticky="ew"); ctk.CTkLabel(settings_frame, text="Tok Thr:", width=60).grid(row=0, column=2, padx=(5,0), pady=2, sticky="e"); widgets['token_threshold_entry'] = ctk.CTkEntry(settings_frame, width=80); widgets['token_threshold_entry'].insert(0, str(DEFAULT_SETTINGS['token_threshold'])); widgets['token_threshold_entry'].grid(row=0, column=3, padx=(0,5), pady=2, sticky="ew"); ctk.CTkLabel(settings_frame, text="Sleep:", width=50).grid(row=0, column=4, padx=(5,0), pady=2, sticky="e"); widgets['sleep_duration_entry'] = ctk.CTkEntry(settings_frame, width=50); widgets['sleep_duration_entry'].insert(0, str(DEFAULT_SETTINGS['sleep_duration'])); widgets['sleep_duration_entry'].grid(row=0, column=5, padx=(0,5), pady=2, sticky="ew"); ctk.CTkLabel(settings_frame, text="#/Page:", width=50).grid(row=0, column=6, padx=(5,0), pady=2, sticky="e"); widgets['num_per_page_entry'] = ctk.CTkEntry(settings_frame, width=50); widgets['num_per_page_entry'].insert(0, str(DEFAULT_SETTINGS['num_per_page'])); widgets['num_per_page_entry'].grid(row=0, column=7, padx=(0,5), pady=2, sticky="ew"); # noqa

    # Action Buttons Frame (Row 2 - Unchanged)
    button_frame = ctk.CTkFrame(main_frame); button_frame.grid(row=2, column=0, sticky="ew", pady=5); widgets['scrape_button'] = ctk.CTkButton(button_frame, text="1. Scrape", command=scrape_callback, width=100); widgets['scrape_button'].pack(side="left", padx=5, pady=5); widgets['stop_button'] = ctk.CTkButton(button_frame, text="Stop Scraping", command=stop_scrape_callback, width=100, state="disabled", fg_color="darkred", hover_color="red"); widgets['stop_button'].pack(side="left", padx=5, pady=5); widgets['optimize_button'] = ctk.CTkButton(button_frame, text="2. Optimize", command=optimize_callback, width=100); widgets['optimize_button'].pack(side="left", padx=5, pady=5); widgets['load_button'] = ctk.CTkButton(button_frame, text="Load Existing", command=load_callback, width=100); widgets['load_button'].pack(side="left", padx=5, pady=5); # noqa

    # Steam Filter Frame (Row 3 - Unchanged)
    filter_frame = ctk.CTkFrame(main_frame); filter_frame.grid(row=3, column=0, sticky="nsew", pady=5); filter_frame.grid_columnconfigure((1, 3, 5), weight=1); ctk.CTkLabel(filter_frame, text="Language:").grid(row=0, column=0, padx=(5, 2), pady=3, sticky="e"); lang_options = list(STEAM_LANGUAGES.keys()); widgets['filter_language_combo'] = ctk.CTkComboBox(filter_frame, values=lang_options, state="readonly"); widgets['filter_language_combo'].set("All Languages"); widgets['filter_language_combo'].grid(row=0, column=1, padx=(0, 5), pady=3, sticky="ew"); ctk.CTkLabel(filter_frame, text="Type:").grid(row=0, column=2, padx=(10, 2), pady=3, sticky="e"); type_options = list(STEAM_REVIEW_TYPES.keys()); widgets['filter_review_type_option'] = ctk.CTkOptionMenu(filter_frame, values=type_options); widgets['filter_review_type_option'].set("All"); widgets['filter_review_type_option'].grid(row=0, column=3, padx=(0, 5), pady=3, sticky="ew"); ctk.CTkLabel(filter_frame, text="Purchase:").grid(row=0, column=4, padx=(10, 2), pady=3, sticky="e"); purchase_options = list(STEAM_PURCHASE_TYPES.keys()); widgets['filter_purchase_type_option'] = ctk.CTkOptionMenu(filter_frame, values=purchase_options); widgets['filter_purchase_type_option'].set("All"); widgets['filter_purchase_type_option'].grid(row=0, column=5, padx=(0, 5), pady=3, sticky="ew"); ctk.CTkLabel(filter_frame, text="Date Range:").grid(row=1, column=0, padx=(5, 2), pady=3, sticky="e"); date_options = list(STEAM_DATE_RANGES.keys()); widgets['filter_date_range_option'] = ctk.CTkOptionMenu(filter_frame, values=date_options); widgets['filter_date_range_option'].set("All Time"); widgets['filter_date_range_option'].grid(row=1, column=1, padx=(0, 5), pady=3, sticky="ew"); ctk.CTkLabel(filter_frame, text="Min Playtime:").grid(row=1, column=2, padx=(10, 2), pady=3, sticky="e"); playtime_options = list(STEAM_PLAYTIME_FILTERS.keys()); widgets['filter_playtime_option'] = ctk.CTkOptionMenu(filter_frame, values=playtime_options); widgets['filter_playtime_option'].set("Any"); widgets['filter_playtime_option'].grid(row=1, column=3, padx=(0, 5), pady=3, sticky="ew"); ctk.CTkLabel(filter_frame, text="Filter By:").grid(row=1, column=4, padx=(10, 2), pady=3, sticky="e"); filterby_options = list(STEAM_FILTER_BY.keys()); widgets['filter_filter_by_option'] = ctk.CTkOptionMenu(filter_frame, values=filterby_options); widgets['filter_filter_by_option'].set("Most Helpful (Default)"); widgets['filter_filter_by_option'].grid(row=1, column=5, padx=(0, 5), pady=3, sticky="ew"); widgets['filter_beta_checkbox'] = ctk.CTkCheckBox(filter_frame, text="Include Beta/Early Access"); widgets['filter_beta_checkbox'].grid(row=2, column=0, columnspan=6, padx=5, pady=(5, 5), sticky="w"); # noqa

    # Log Display Frame (Row 4 - Shifted)
    # (Unchanged)
    log_outer_frame = ctk.CTkFrame(main_frame); log_outer_frame.grid(row=4, column=0, sticky="nsew", pady=5); log_outer_frame.grid_rowconfigure(1, weight=1); log_outer_frame.grid_columnconfigure(0, weight=1); log_outer_frame.grid_columnconfigure(1, weight=0); ctk.CTkLabel(log_outer_frame, text="Log Output", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=5, pady=(2,0)); widgets['scrape_progress_label'] = ctk.CTkLabel(log_outer_frame, text="Scraping: Idle", width=150, anchor='e'); widgets['scrape_progress_label'].grid(row=0, column=1, sticky="e", padx=5, pady=(2,0)); widgets['log_box'] = ctk.CTkTextbox(log_outer_frame, wrap="word", state="disabled"); widgets['log_box'].grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=(0,5)); # noqa

    # Progress Bar Frame (Row 5 - Shifted)
    # (Unchanged)
    progress_bar_frame = ctk.CTkFrame(main_frame, fg_color="transparent"); progress_bar_frame.grid(row=5, column=0, sticky="ew", pady=(0,5)); progress_bar_frame.grid_columnconfigure(0, weight=1); widgets['progress_bar'] = ctk.CTkProgressBar(progress_bar_frame); widgets['progress_bar'].set(0); widgets['progress_bar'].grid(row=0, column=0, sticky="ew"); progress_bar_frame.grid_remove(); # noqa

    # Token Estimate Label (Row 6 - Shifted)
    # (Unchanged)
    widgets['token_estimate_label'] = ctk.CTkLabel(main_frame, text="Token Estimates: N/A", anchor="w", font=ctk.CTkFont(size=11)); widgets['token_estimate_label'].grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 5)); # noqa

    # AI Analysis Frame (Row 7 - Shifted)
    # (Unchanged)
    ai_outer_frame = ctk.CTkFrame(main_frame); ai_outer_frame.grid(row=7, column=0, sticky="nsew", pady=5); ai_outer_frame.grid_columnconfigure(0, weight=1); ai_outer_frame.grid_rowconfigure(3, weight=1); ctk.CTkLabel(ai_outer_frame, text="AI Analysis", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(2,0)); model_select_frame = ctk.CTkFrame(ai_outer_frame, fg_color="transparent"); model_select_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 5), padx=5); ctk.CTkLabel(model_select_frame, text="Select Model:", anchor="w").pack(side="left", padx=(0,5)); model_names = [m["name"] for m in SUPPORTED_MODELS] if SUPPORTED_MODELS else ["No Models"]; widgets['model_combobox'] = ctk.CTkComboBox(model_select_frame, values=model_names, state="readonly"); widgets['model_combobox'].pack(side="left", padx=5, fill="x", expand=True); # noqa
    if SUPPORTED_MODELS:
        widgets['model_combobox'].set(SUPPORTED_MODELS[0]['name'])
    else:
        widgets['model_combobox'].set(model_names[0])
    widgets['model_combobox'].configure(state="disabled")  # noqa
    ctk.CTkLabel(ai_outer_frame, text="Query for AI:").grid(row=2, column=0, columnspan=2, sticky="sw", padx=5, pady=(5,0)); widgets['ai_query_text'] = ctk.CTkTextbox(ai_outer_frame, wrap="word", height=100); widgets['ai_query_text'].grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5, pady=(0, 5)); ai_buttons_frame = ctk.CTkFrame(ai_outer_frame, fg_color="transparent"); ai_buttons_frame.grid(row=4, column=0, columnspan=2, pady=(5,10)); widgets['ai_send_optimized_button'] = ctk.CTkButton(ai_buttons_frame, text="3a. Send OPTIMIZED", command=ai_optimized_callback, width=180); widgets['ai_send_optimized_button'].pack(side="left", padx=10); widgets['ai_send_original_button'] = ctk.CTkButton(ai_buttons_frame, text="3b. Send ORIGINAL", command=ai_original_callback, width=180); widgets['ai_send_original_button'].pack(side="left", padx=10); # noqa

    # --- Right Panel (Tabs) ---
    right_panel = ctk.CTkFrame(root, fg_color="transparent"); right_panel.grid(row=0, column=2, sticky="nsew", padx=(5, 10), pady=10); right_panel.grid_rowconfigure(0, weight=1); right_panel.grid_columnconfigure(0, weight=1); # noqa
    widgets['right_tabview'] = ctk.CTkTabview(right_panel); widgets['right_tabview'].grid(row=0, column=0, sticky="nsew"); widgets['right_tabview'].add("Extracted Data"); widgets['right_tabview'].add("AI Response Text"); # noqa

    # Extracted Data Tab
    data_tab = widgets['right_tabview'].tab("Extracted Data"); data_tab.grid_columnconfigure(0, weight=1); data_tab.grid_rowconfigure(1, weight=1); filter_data_frame = ctk.CTkFrame(data_tab, fg_color="transparent"); filter_data_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 10)); filter_data_frame.columnconfigure(1, weight=1); ctk.CTkLabel(filter_data_frame, text="Filter (Col 1):", anchor="w").grid(row=0, column=0, padx=(0, 5)); widgets['filter_menu'] = ctk.CTkOptionMenu(filter_data_frame, values=["Show All"]); widgets['filter_menu'].grid(row=0, column=1, sticky="ew"); tree_frame = ctk.CTkFrame(data_tab, fg_color="transparent"); tree_frame.grid(row=1, column=0, sticky="nsew"); tree_frame.grid_columnconfigure(0, weight=1); tree_frame.grid_rowconfigure(0, weight=1); # noqa

    # --- Treeview Styling ---
    # NOTE: The actual tag configuration (colors, fonts) is now done
    #       in gui_manager.py's _configure_treeview_tags method.
    #       This section just sets up the general ttk style base.
    style = ttk.Style()
    # Get theme colors for base style
    bg_color = root._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
    text_color = root._apply_appearance_mode(ctk.ThemeManager.theme["CTkLabel"]["text_color"])
    selected_color = root._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["fg_color"])
    header_bg = root._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["hover_color"])

    # Apply base style
    style.theme_use("default")
    style.configure("Treeview",
                    background=bg_color, foreground=text_color,
                    fieldbackground=bg_color, borderwidth=0, rowheight=25)
    style.configure("Treeview.Heading",
                    background=header_bg, foreground=text_color,
                    relief="flat", padding=(5, 5), font=('Segoe UI', 10, 'bold'))
    style.map("Treeview.Heading",
              background=[('active', root._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["fg_color"]))]) # noqa
    style.map("Treeview",
              background=[('selected', selected_color)],
              foreground=[('selected', text_color)]) # Ensure text color on selection if needed

    # --- ADD COMMENTS FOR COLOR CUSTOMIZATION ---
    # To easily change the alternating row colors:
    # 1. Go to `gui_manager.py`.
    # 2. Find the `_configure_treeview_tags` method.
    # 3. Modify the `bg_color` and `alt_row_color` variables:
    #    - They currently try to use theme colors (frame background and border).
    #    - You can replace them with hardcoded hex color strings, e.g.:
    #      bg_color = "#FFFFFF"  # White for light mode 'odd' rows
    #      alt_row_color = "#F0F0F0" # Light gray for light mode 'even' rows
    #      # OR for dark mode:
    #      # bg_color = "#2B2B2B"
    #      # alt_row_color = "#313131"
    #    - You can adjust the calculation based on border_color or make it slightly
    #      darker/lighter than bg_color manually.
    # --- END COLOR CUSTOMIZATION COMMENTS ---

    # Create Treeview widget
    widgets['spreadsheet'] = ttk.Treeview(tree_frame, show='headings', style="Treeview")
    # Scrollbars
    tree_vsb = ctk.CTkScrollbar(tree_frame, orientation="vertical", command=widgets['spreadsheet'].yview)
    tree_hsb = ctk.CTkScrollbar(tree_frame, orientation="horizontal", command=widgets['spreadsheet'].xview)
    widgets['spreadsheet'].configure(yscrollcommand=tree_vsb.set, xscrollcommand=tree_hsb.set)
    # Grid layout
    widgets['spreadsheet'].grid(row=0, column=0, sticky='nsew')
    tree_vsb.grid(row=0, column=1, sticky='ns')
    tree_hsb.grid(row=1, column=0, sticky='ew')
    # Initial content
    widgets['spreadsheet']['columns'] = ('Status',)
    widgets['spreadsheet'].heading('Status', text='Status')
    widgets['spreadsheet'].column('Status', anchor='w', width=200)
    # Initial row - tag configured by gui_manager
    widgets['spreadsheet'].insert("", "end", values=["Load data..."])


    # AI Response Text Tab
    # (Unchanged)
    text_tab = widgets['right_tabview'].tab("AI Response Text"); text_tab.grid_columnconfigure(0, weight=1); text_tab.grid_rowconfigure(0, weight=1); widgets['ai_response_textbox'] = ctk.CTkTextbox(text_tab, wrap="word", state="disabled", font=('Segoe UI', 11)); widgets['ai_response_textbox'].grid(row=0, column=0, sticky="nsew", padx=5, pady=5); widgets['ai_response_textbox'].insert("1.0", "[AI Response Text]"); widgets['ai_response_textbox'].configure(state="disabled"); # noqa

    widgets['right_tabview'].set("Extracted Data") # Default tab

    return widgets