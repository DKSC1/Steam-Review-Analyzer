# gui_manager.py
import customtkinter as ctk
from tkinter import ttk, TclError, messagebox
import os
import traceback

# Assume config.py and utils.py are accessible
import config
import utils  # For calculate_and_format_token_estimates

class GuiManager:
    """Manages updates and interactions with the GUI elements."""

    def __init__(self, root, widgets, log_func):
        self.root = root
        self.widgets = widgets
        self.log_func = log_func
        self.full_csv_data = None  # Store data for filtering
        # --- Define tag names ---
        self.tag_odd = "oddrow"
        self.tag_even = "evenrow"
        # REMOVED: self.tag_summary = "summaryrow"

        self._configure_treeview_tags()  # Configure only odd/even

    def _configure_treeview_tags(self):
        """Configures the appearance of Treeview tags for alternating rows."""
        treeview_widget = self.widgets.get('spreadsheet')
        if not treeview_widget:
            self.log_func("Warn: Spreadsheet widget not ready for tag configuration.")
            return

        try:
            # --- Alternating Row Colors (as before) ---
            bg_color = self.root._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
            alt_row_color = self.root._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["border_color"])
            if alt_row_color == bg_color or not alt_row_color:
                alt_row_color = "#e8e8e8" if ctk.get_appearance_mode() == "Light" else "#2f2f2f"

            treeview_widget.tag_configure(self.tag_odd, background=bg_color)
            treeview_widget.tag_configure(self.tag_even, background=alt_row_color)

            # REMOVED: Summary tag configuration
            # treeview_widget.tag_configure(self.tag_summary, ...)

            self.log_func("Configured Treeview tags (odd, even).")
        except Exception as tag_e:
            self.log_func(f"Warn: Could not configure Treeview row tags: {tag_e}")
            try:  # Fallback definitions
                treeview_widget.tag_configure(self.tag_odd)
                treeview_widget.tag_configure(self.tag_even)
            except Exception:
                self.log_func("Error: Failed fallback tag configure.")

    def update_spreadsheet(self, data):
        """Clears/populates the Treeview, applies tags, adjusts column width."""
        treeview_widget = self.widgets.get('spreadsheet')
        widget_exists = treeview_widget and hasattr(treeview_widget, 'winfo_exists') and treeview_widget.winfo_exists()
        if not widget_exists:
            self.log_func("Spreadsheet widget unavailable.")
            return

        self.full_csv_data = data
        is_placeholder = not data or not any(data)
        if is_placeholder:
            display_data = [['Status'], ['No data available or extracted.']]
            self.update_filter_options(None)
        else:
            display_data = data
            self.update_filter_options(data)

        try:
            # --- Clear Treeview ---
            for item_id in treeview_widget.get_children():
                try:
                    treeview_widget.delete(item_id)
                except Exception:
                    pass
            treeview_widget["columns"] = ()

            # --- Setup Columns ---
            header = display_data[0]
            treeview_widget["columns"] = tuple(header)
            treeview_widget['show'] = 'headings'

            # --- Configure Tags ---
            self._configure_treeview_tags()

            # --- Configure Headings and Columns based solely on text width ---
            for col_num, col_name in enumerate(header):
                col_id = header[col_num]  # Use header name as ID
                try:
                    # Estimate width based on header and first 20 rows
                    col_width_chars = len(str(col_name))
                    for i in range(1, min(21, len(display_data))):
                        try:
                            if len(display_data[i]) > col_num:
                                col_width_chars = max(col_width_chars, len(str(display_data[i][col_num])))
                        except Exception:
                            pass  # Ignore errors checking specific cells

                    # Calculate pixel width (approximate) based solely on longest text length
                    col_pixel_width = col_width_chars * 9  # Adjust multiplier as needed

                    treeview_widget.heading(col_id, text=col_name, anchor='w')
                    treeview_widget.column(col_id, anchor='w', width=int(col_pixel_width), stretch=False)
                except Exception as e_col:
                    self.log_func(f"Error config col '{col_name}': {e_col}")
                    try:  # Fallback
                        col_id_fb = f"#{col_num+1}"  # Use index if header name fails
                        treeview_widget.heading(col_id_fb, text=f"Col{col_num+1}", anchor='w')
                        treeview_widget.column(col_id_fb, anchor='w', width=100, stretch=False)
                    except Exception:
                        pass

            # --- Insert data rows with tags ---
            for i, row_data in enumerate(display_data[1:]):
                try:
                    base_tag = self.tag_even if i % 2 == 0 else self.tag_odd
                    # Ensure row data length matches header length
                    values = (row_data + [''] * len(header))[:len(header)]
                    treeview_widget.insert("", "end", values=values, tags=(base_tag,))
                except Exception as e_row:
                    self.log_func(f"Error inserting spreadsheet row {i}: {e_row}")

        except Exception as e:
            self.log_func(f"Critical Error updating spreadsheet: {e}\n{traceback.format_exc()}")
            try:  # Attempt error display
                for item_id in treeview_widget.get_children():
                    treeview_widget.delete(item_id)
                treeview_widget["columns"] = ('Error',)
                treeview_widget.heading('Error', text='Error', anchor='w')
                treeview_widget.column('Error', anchor='w', width=300)
                treeview_widget.insert("", "end", values=[f"Failed display: {e}"], tags=(self.tag_odd,))
            except Exception:
                pass

    def update_filter_options(self, data):
        # ... (Keep existing implementation) ...
        filter_menu = self.widgets.get('filter_menu')
        if not filter_menu or not filter_menu.winfo_exists():
            self.log_func("Filter menu unavailable.")
            return
        options = ["Show All"]
        unique = set()
        if data and len(data) > 1:
            try:
                for row in data[1:]:
                    if row and len(row) > 0 and str(row[0]).strip():
                        unique.add(str(row[0]))
                options.extend(sorted(list(unique)))
            except Exception as e:
                self.log_func(f"Warn: Err get filter opts: {e}")
        try:
            filter_menu.configure(values=options)
            filter_menu.set("Show All")
        except Exception as e:
            self.log_func(f"Err update filter menu: {e}")

    def on_filter_change(self, selected_category):
        self.log_func(f"Filtering spreadsheet by: {selected_category}")
        spreadsheet = self.widgets.get('spreadsheet')
        if not spreadsheet or not spreadsheet.winfo_exists():
            self.log_func("Err: Spreadsheet missing for filter.")
            return
        if self.full_csv_data is None or not isinstance(self.full_csv_data, list) or len(self.full_csv_data) < 1:
            self.log_func("No data to filter.")
            self.update_spreadsheet(None)
            return
        filtered = []
        try:
            header = self.full_csv_data[0]
            filtered.append(header)
            if selected_category == "Show All":
                filtered.extend(self.full_csv_data[1:])
            else:
                for row in self.full_csv_data[1:]:
                    if row and len(row) > 0 and str(row[0]) == selected_category:
                        filtered.append(row)
            self._display_filtered_data(filtered)
        except Exception as e:
            self.log_func(f"Error filtering: {e}")
            self._display_filtered_data(self.full_csv_data)

    def _display_filtered_data(self, filtered_data):
        """Internal: Updates Treeview display for filtering, applies tags, adjusts col width"""
        treeview_widget = self.widgets.get('spreadsheet')
        if not treeview_widget or not treeview_widget.winfo_exists():
            return

        if not filtered_data or len(filtered_data) <= 1:
            display_data = [['Status'], ['Filter returned no results.']]
        else:
            display_data = filtered_data

        try:
            for item_id in treeview_widget.get_children():
                treeview_widget.delete(item_id)
            treeview_widget["columns"] = ()
            header = display_data[0]
            treeview_widget["columns"] = tuple(header)
            treeview_widget['show'] = 'headings'
            self._configure_treeview_tags()  # Ensure base tags configured

            # Configure headings/columns based solely on longest text size
            for col_num, col_name in enumerate(header):
                col_id = header[col_num]  # Use header name as ID
                try:
                    col_width_chars = len(str(col_name))
                    # Check only a few rows for filter redraw width
                    for i in range(1, min(6, len(display_data))):
                        try:
                            if len(display_data[i]) > col_num:
                                col_width_chars = max(col_width_chars, len(str(display_data[i][col_num])))
                        except Exception:
                            pass
                    col_pixel = col_width_chars * 9

                    treeview_widget.heading(col_id, text=col_name, anchor='w')
                    treeview_widget.column(col_id, anchor='w', width=int(col_pixel), stretch=False)
                except Exception as e:
                    try:
                        fid = f"#{col_num+1}"
                        treeview_widget.heading(fid, text=f"C{col_num+1}", anchor='w')
                        treeview_widget.column(fid, anchor='w', width=100, stretch=False)
                    except Exception:
                        pass

            # Insert filtered rows with base tags
            for i, row_data in enumerate(display_data[1:]):
                try:
                    base_tag = self.tag_even if i % 2 == 0 else self.tag_odd
                    values = (row_data + [''] * len(header))[:len(header)]
                    treeview_widget.insert("", "end", values=values, tags=(base_tag,))
                except Exception as e_row:
                    self.log_func(f"Error inserting filtered row {i}: {e_row}")

        except Exception as e:
            self.log_func(f"Error displaying filtered data: {e}")

    def update_ai_response_text(self, text_content):
        textbox = self.widgets.get('ai_response_textbox')
        if not textbox or not textbox.winfo_exists():
            self.log_func("AI text box unavailable.")
            return
        try:
            textbox.configure(state="normal")
            textbox.delete("1.0", "end")
            textbox.insert("1.0", text_content if text_content else "[No text content]")
            textbox.configure(state="disabled")
        except Exception as e:
            self.log_func(f"Error update AI text: {e}")
            try:
                if textbox.winfo_exists():
                    textbox.configure(state="normal")
                    textbox.delete("1.0", "end")
                    textbox.insert("1.0", f"[Error: {e}]")
                    textbox.configure(state="disabled")
            except Exception as inner_e:
                self.log_func(f"Error handling exception in AI text update: {inner_e}")

    def update_token_display(self):
        token_label = self.widgets.get('token_estimate_label')
        entry_name = self.widgets.get('game_name_entry')
        entry_id = self.widgets.get('steam_id_entry')
        display = "Token Estimates: N/A"
        name = ""
        steam_id = ""
        try:
            if entry_name and entry_name.winfo_exists():
                name = entry_name.get().strip()
            if entry_id and entry_id.winfo_exists():
                steam_id = entry_id.get().strip()
        except Exception as e:
            self.log_func(f"Error get name/id token: {e}")
        if name and steam_id and steam_id.isdigit():
            try:
                display, _, _ = utils.calculate_and_format_token_estimates(name, steam_id, self.log_func)
            except Exception as calc_e:
                self.log_func(f"Error calc token: {calc_e}")
                display = "Token Estimates: Error"
        elif not name and not steam_id:
            display = "Token Estimates: N/A"
        else:
            display = "Token Estimates: (Enter Valid Game/ID)"
        if token_label and token_label.winfo_exists():
            try:
                token_label.configure(text=display)
            except Exception as e:
                self.log_func(f"Error update token label: {e}")
        else:
            self.log_func("Token label not found.")

    def populate_game_browser(self):
        browser_frame = self.widgets.get('game_browser_frame')
        if not browser_frame or not browser_frame.winfo_exists():
            self.log_func("Err: Browser frame miss.")
            return
        try:
            list(map(lambda w: w.destroy(), browser_frame.winfo_children()))
        except Exception as e:
            self.log_func(f"Warn: Err clear browser: {e}")
            return
        base_dir = config.BASE_REVIEW_DIR
        self.log_func(f"Refresh list: {base_dir}")
        folders = []
        if os.path.isdir(base_dir):
            try:
                for item in os.listdir(base_dir):
                    p = os.path.join(base_dir, item)
                    if os.path.isdir(p):
                        try:
                            parts = item.rsplit('_', 1)
                            if len(parts) == 2 and parts[1].isdigit():
                                folders.append({"name": parts[0].replace('_', ' '), "id": parts[1]})
                        except Exception as e:
                            self.log_func(f"Err parse folder '{item}': {e}")
            except OSError as e:
                self.log_func(f"Err read dir '{base_dir}': {e}")
                messagebox.showerror("Error", f"Read dir fail:\n{e}")
                return
        else:
            self.log_func(f"Base dir '{base_dir}' not found.")
        folders.sort(key=lambda x: x['name'])
        if not folders:
            try:
                ctk.CTkLabel(browser_frame, text="(No saved games)", text_color="gray").pack(pady=5)
            except Exception as e:
                self.log_func(f"Err 'no games' label: {e}")
        else:
            from functools import partial
            for info in folders:
                try:
                    cmd = partial(self.select_game_from_browser, info['name'], info['id'])
                    btn = ctk.CTkButton(browser_frame, text=info['name'], command=cmd, anchor="w", height=25)
                    btn.pack(fill="x", padx=2, pady=(1, 2))
                except Exception as e:
                    self.log_func(f"Err button {info['name']}: {e}")
        self.log_func(f"Browser refresh done. Found {len(folders)} folders.")

    def select_game_from_browser(self, game_name, game_id):
        self.log_func(f"Select: {game_name} (ID: {game_id})")
        try:
            n_entry = self.widgets.get('game_name_entry')
            id_entry = self.widgets.get('steam_id_entry')
            if n_entry and n_entry.winfo_exists():
                n_entry.delete(0, "end")
                n_entry.insert(0, game_name)
            if id_entry and id_entry.winfo_exists():
                id_entry.delete(0, "end")
                id_entry.insert(0, game_id)
            if self.root and hasattr(self.root, 'after'):
                self.root.after(50, self.update_token_display)
            else:
                self.log_func("Warn: No schedule token update.")
                self.update_token_display()
        except Exception as e:
            self.log_func(f"Error populate fields: {e}")

    def set_widget_state(self, widgets_list, state):
        if not isinstance(widgets_list, list):
            widgets_list = [widgets_list]
        for w in widgets_list:
            try:
                if w and hasattr(w, 'winfo_exists') and w.winfo_exists() and hasattr(w, 'configure'):
                    if isinstance(w, ctk.CTkComboBox) and state == "normal":
                        w.configure(state="readonly")
                    elif isinstance(w, ctk.CTkScrollableFrame):
                        pass
                    else:
                        w.configure(state=state)
            except (TclError, AttributeError):
                pass
            except Exception as e:
                self.log_func(f"Warn: Err set state {w}: {e}")
