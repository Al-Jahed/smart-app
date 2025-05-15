import io
import json
import os
import re
import shutil
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from docx import Document
from PIL import Image, ImageTk


class FileManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced File Manager")
        self.root.geometry("1200x700")

        self.target_folder = ""
        self.recently_added = []
        self.favorites = self.load_favorites()
        self.current_sort = {"column": "Name", "reverse": False}

        # For multiple selection
        self.selected_items = []

        self.setup_ui()
        self.initialize_target_folder()

    def setup_ui(self):
        # Main frames
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left sidebar for favorites
        self.sidebar_frame = ttk.Frame(main_frame, width=150, padding=5)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)

        # Middle frame for file listing
        middle_frame = ttk.Frame(main_frame, padding=10)
        middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Right frame for preview
        right_frame = ttk.Frame(main_frame, padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Setup favorites sidebar
        self.setup_favorites_sidebar()

        # Middle frame components
        control_frame = ttk.Frame(middle_frame)
        control_frame.pack(fill=tk.X)

        result_frame = ttk.Frame(middle_frame)
        result_frame.pack(fill=tk.BOTH, expand=True)

        # Folder selection
        ttk.Label(control_frame, text="Target Location:").grid(
            row=0, column=0, sticky=tk.W
        )
        self.folder_path_var = tk.StringVar()
        ttk.Entry(control_frame, textvariable=self.folder_path_var, width=40).grid(
            row=0, column=1, padx=5
        )
        ttk.Button(
            control_frame, text="Browse", command=self.change_target_folder
        ).grid(row=0, column=2)
        ttk.Button(
            control_frame, text="Add to Favorites", command=self.add_to_favorites
        ).grid(row=0, column=3, padx=5)

        # Search bar
        search_frame = ttk.Frame(control_frame)
        search_frame.grid(row=1, column=0, columnspan=4, pady=10, sticky=tk.W + tk.E)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame, textvariable=self.search_var, width=30
        )
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<Return>", lambda e: self.search_files())
        ttk.Button(search_frame, text="Search", command=self.search_files).pack(
            side=tk.LEFT
        )

        # Filter dropdown
        ttk.Label(search_frame, text="Filter:").pack(side=tk.LEFT, padx=(20, 5))
        self.filter_var = tk.StringVar(value="All Files")
        filter_options = [
            "All Files",
            "Documents",
            "Images",
            "Videos",
            "Audio",
            "Archives",
            "Folders Only",
        ]
        filter_dropdown = ttk.Combobox(
            search_frame, textvariable=self.filter_var, values=filter_options, width=15
        )
        filter_dropdown.pack(side=tk.LEFT)
        filter_dropdown.bind("<<ComboboxSelected>>", lambda e: self.view_contents())

        # Action buttons
        action_frame = ttk.Frame(control_frame)
        action_frame.grid(row=2, column=0, columnspan=4, pady=10)

        ttk.Button(action_frame, text="Add Files", command=self.add_files).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(action_frame, text="Add Folder", command=self.add_folder).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(
            action_frame, text="Create Subfolder", command=self.create_subfolder
        ).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Rename", command=self.rename_selected).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(action_frame, text="Delete", command=self.delete_selected).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Button(action_frame, text="Move To...", command=self.move_selected).pack(
            side=tk.LEFT, padx=3
        )

        # File list
        self.result_tree = ttk.Treeview(
            result_frame,
            columns=(
                "Name",
                "Type",
                "Size",
                "Modified",
                "Question Available",
            ),  # Updated column name
            show="headings",
            selectmode="extended",
        )
        for col in [
            "Name",
            "Type",
            "Size",
            "Modified",
            "Question Available",
        ]:  # Updated column name
            self.result_tree.heading(
                col, text=col, command=lambda c=col: self.sort_treeview(c)
            )
            self.result_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(
            result_frame, orient="vertical", command=self.result_tree.yview
        )
        self.result_tree.configure(yscrollcommand=scrollbar.set)

        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.result_tree.bind("<Double-1>", lambda e: self.open_selected())
        self.result_tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Text Preview Panel
        preview_label_frame = ttk.Frame(right_frame)
        preview_label_frame.pack(fill=tk.X)
        ttk.Label(preview_label_frame, text="Preview:").pack(side=tk.LEFT)

        # Preview frame will contain either text or image preview
        self.preview_frame = ttk.Frame(right_frame)
        self.preview_frame.pack(fill=tk.BOTH, expand=True)

        # Text preview
        self.preview_text = ScrolledText(self.preview_frame, wrap=tk.WORD, height=38)
        self.preview_text.pack(fill=tk.BOTH, expand=True)

        # Image preview (initially hidden)
        self.image_label = ttk.Label(self.preview_frame)

        # Status bar
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_favorites_sidebar(self):
        # Clear existing widgets
        for widget in self.sidebar_frame.winfo_children():
            widget.destroy()

        ttk.Label(self.sidebar_frame, text="Favorites", font=("", 10, "bold")).pack(
            anchor=tk.W, pady=(0, 5)
        )

        # Add favorites list
        favorites_frame = ttk.Frame(self.sidebar_frame)
        favorites_frame.pack(fill=tk.BOTH, expand=True)

        for i, (name, path) in enumerate(self.favorites.items()):
            fav_frame = ttk.Frame(favorites_frame)
            fav_frame.pack(fill=tk.X, pady=2)

            ttk.Button(
                fav_frame,
                text=name,
                command=lambda p=path: self.set_target_folder(p),
                width=15,
            ).pack(side=tk.LEFT)
            ttk.Button(
                fav_frame,
                text="×",
                width=2,
                command=lambda n=name: self.remove_favorite(n),
            ).pack(side=tk.LEFT)

    def load_favorites(self):
        try:
            favorites_path = os.path.join(
                os.path.expanduser("~"), ".file_manager_favorites.json"
            )
            if os.path.exists(favorites_path):
                with open(favorites_path, "r") as f:
                    return json.load(f)
        except:
            pass
        return {}

    def save_favorites(self):
        favorites_path = os.path.join(
            os.path.expanduser("~"), ".file_manager_favorites.json"
        )
        with open(favorites_path, "w") as f:
            json.dump(self.favorites, f)

    def add_to_favorites(self):
        if not self.target_folder:
            return

        name = simpledialog.askstring(
            "Add to Favorites", "Enter a name for this favorite:"
        )
        if not name:
            return

        self.favorites[name] = self.target_folder
        self.save_favorites()
        self.setup_favorites_sidebar()
        self.status_var.set(f"Added '{self.target_folder}' to favorites as '{name}'")

    def remove_favorite(self, name):
        if name in self.favorites:
            del self.favorites[name]
            self.save_favorites()
            self.setup_favorites_sidebar()
            self.status_var.set(f"Removed '{name}' from favorites")

    def initialize_target_folder(self):
        default_path = os.path.join(os.path.expanduser("~"), "Documents")
        if os.path.exists(default_path):
            self.set_target_folder(default_path)
        else:
            self.change_target_folder()

    def set_target_folder(self, path):
        if not os.path.exists(path):
            messagebox.showerror("Error", f"The path {path} does not exist")
            return

        self.target_folder = path
        self.folder_path_var.set(path)
        self.view_contents()
        self.root.title(f"Enhanced File Manager - {os.path.basename(path)}")
        self.status_var.set(f"Current location: {path}")

    def change_target_folder(self):
        folder = filedialog.askdirectory(title="Select Target Folder")
        if folder:
            self.set_target_folder(folder)

    def get_file_type_category(self, file_path):
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext in [".docx", ".doc", ".txt", ".pdf", ".rtf", ".odt", ".md"]:
            return "Documents"
        elif ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".svg"]:
            return "Images"
        elif ext in [".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"]:
            return "Videos"
        elif ext in [".mp3", ".wav", ".ogg", ".flac", ".aac"]:
            return "Audio"
        elif ext in [".zip", ".rar", ".7z", ".tar", ".gz"]:
            return "Archives"
        else:
            return "Other"

    def view_contents(self):
        self.result_tree.delete(*self.result_tree.get_children())
        if not os.path.exists(self.target_folder) or not self.target_folder:
            return

        try:
            items = []

            # Add "..." entry to go back to the previous folder
            parent_folder = os.path.dirname(self.target_folder)
            if parent_folder and parent_folder != self.target_folder:
                self.result_tree.insert(
                    "", tk.END, values=("...", "Folder", "-", "-", "-")
                )

            for item in os.listdir(self.target_folder):
                full_path = os.path.join(self.target_folder, item)

                # Skip hidden files
                if item.startswith("."):
                    continue

                if os.path.isfile(full_path):
                    file_type = "File"
                    type_category = self.get_file_type_category(full_path)
                    try:
                        size = os.path.getsize(full_path)
                        size_str = self.format_file_size(size)
                    except:
                        size_str = "Unknown"

                    # Count numbered passages for text-based files
                    if type_category == "Documents":
                        try:
                            with open(
                                full_path, "r", encoding="utf-8", errors="ignore"
                            ) as f:
                                content = f.read()
                                numbered_passages_count = self.count_numbered_passages(
                                    content
                                )
                        except:
                            numbered_passages_count = "N/A"
                    else:
                        numbered_passages_count = "N/A"
                else:
                    file_type = "Folder"
                    type_category = "Folder"
                    size_str = "-"
                    numbered_passages_count = "-"

                # Apply filter if not "All Files"
                filter_category = self.filter_var.get()
                if filter_category != "All Files":
                    if filter_category == "Folders Only" and file_type != "Folder":
                        continue
                    elif (
                        filter_category != "Folders Only"
                        and type_category != filter_category
                    ):
                        continue

                try:
                    modified = datetime.fromtimestamp(
                        os.path.getmtime(full_path)
                    ).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    modified = "Unknown"

                items.append(
                    (item, file_type, size_str, modified, numbered_passages_count)
                )

            # Sort items according to current sort settings
            col_index = [
                "Name",
                "Type",
                "Size",
                "Modified",
                "Question Available",
            ].index(self.current_sort["column"])
            items.sort(key=lambda x: x[col_index], reverse=self.current_sort["reverse"])

            for item, file_type, size, modified, numbered_passages_count in items:
                self.result_tree.insert(
                    "",
                    tk.END,
                    values=(item, file_type, size, modified, numbered_passages_count),
                )

            self.status_var.set(f"Displayed {len(items)} items in {self.target_folder}")

        except Exception as e:
            messagebox.showerror("Error", f"Error reading directory: {e}")

    def format_file_size(self, size_bytes):
        # Convert file size to a human-readable format
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    def search_files(self):
        search_term = self.search_var.get().strip().lower()
        if not search_term:
            self.view_contents()
            return

        self.result_tree.delete(*self.result_tree.get_children())
        if not os.path.exists(self.target_folder):
            return

        try:
            matching_items = []
            for root, dirs, files in os.walk(self.target_folder):
                for item in files + dirs:
                    if search_term in item.lower():
                        full_path = os.path.join(root, item)
                        rel_path = os.path.relpath(full_path, self.target_folder)

                        if os.path.isfile(full_path):
                            file_type = "File"
                            try:
                                size = os.path.getsize(full_path)
                                size_str = self.format_file_size(size)
                            except:
                                size_str = "Unknown"
                        else:
                            file_type = "Folder"
                            size_str = "-"

                        try:
                            modified = datetime.fromtimestamp(
                                os.path.getmtime(full_path)
                            ).strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            modified = "Unknown"

                        matching_items.append((rel_path, file_type, size_str, modified))

            for item_path, file_type, size, modified in matching_items:
                self.result_tree.insert(
                    "", tk.END, values=(item_path, file_type, size, modified)
                )

            self.status_var.set(
                f"Found {len(matching_items)} items matching '{search_term}'"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Error during search: {e}")

    def sort_treeview(self, column):
        # Toggle sort order if clicking the same column
        if self.current_sort["column"] == column:
            self.current_sort["reverse"] = not self.current_sort["reverse"]
        else:
            self.current_sort["column"] = column
            self.current_sort["reverse"] = False

        self.view_contents()

        # Update column header to show sort direction
        for col in ["Name", "Type", "Size", "Modified"]:
            if col == column:
                direction = " ↓" if self.current_sort["reverse"] else " ↑"
                self.result_tree.heading(col, text=f"{col}{direction}")
            else:
                self.result_tree.heading(col, text=col)

    def on_tree_select(self, event):
        selected = self.result_tree.selection()
        if not selected:
            return

        # Get the selected item
        item = self.result_tree.item(selected[0])["values"]
        if not item:
            return

        # Handle "..." entry to go back to the previous folder
        if item[0] == "...":
            self.set_target_folder(os.path.dirname(self.target_folder))
            return

        # Store all selected items
        self.selected_items = []
        for item_id in selected:
            item_values = self.result_tree.item(item_id)["values"]
            if item_values:
                self.selected_items.append(item_values[0])  # Store filename

        # If there's exactly one item selected, preview it
        if len(selected) == 1:
            self.preview_selected(selected[0])

        # Update status bar
        if len(selected) > 1:
            self.status_var.set(f"{len(selected)} items selected")
        elif len(selected) == 1:
            item = self.result_tree.item(selected[0])["values"][0]
            self.status_var.set(f"Selected: {item}")

    def preview_selected(self, selected_id):
        item = self.result_tree.item(selected_id)["values"]
        if not item:
            return

        name = item[0]
        file_path = os.path.join(self.target_folder, name)

        # Hide both preview widgets
        self.preview_text.pack_forget()
        self.image_label.pack_forget()

        if os.path.isdir(file_path):
            self.preview_text.pack(fill=tk.BOTH, expand=True)
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(tk.END, f"{name} (Folder)\n\n")

            try:
                contents = os.listdir(file_path)
                self.preview_text.insert(tk.END, f"Contains {len(contents)} items:\n\n")
                for i, item in enumerate(contents[:30]):
                    self.preview_text.insert(tk.END, f"• {item}\n")
                if len(contents) > 30:
                    self.preview_text.insert(
                        tk.END, f"\n... and {len(contents) - 30} more items"
                    )
            except Exception as e:
                self.preview_text.insert(tk.END, f"Error reading folder contents: {e}")
            return

        # Determine file type for preview
        _, ext = os.path.splitext(name)
        ext = ext.lower()

        # Text files
        if ext in [
            ".txt",
            ".md",
            ".py",
            ".java",
            ".html",
            ".css",
            ".js",
            ".json",
            ".xml",
            ".csv",
        ]:
            self.preview_text.delete(1.0, tk.END)  # Clear the preview text
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(50000)  # Limit to 50K to avoid performance issues

                    # Count numbered passages
                    count = self.count_numbered_passages(content)
                    print(f"Numbered Passages Count: {count}")

                    # Insert the count at the top
                    self.preview_text.insert(
                        1.0, f"[Numbered Passages Count: {count}]\n\n"
                    )

                    # Insert the content below the count
                    self.preview_text.insert(tk.END, content)

                    if len(content) == 50000:
                        self.preview_text.insert(
                            tk.END, "\n\n[Content truncated - file too large]"
                        )

                    # Update the Treeview with the correct count
                    self.result_tree.item(
                        selected_id,
                        values=(
                            item[0],  # Name
                            item[1],  # Type
                            item[2],  # Size
                            item[3],  # Modified
                            count,  # Numbered Passages
                        ),
                    )

            except Exception as e:
                self.preview_text.insert(tk.END, f"Error reading file: {e}")

        # Word documents
        elif ext == ".docx":
            self.preview_text.pack(fill=tk.BOTH, expand=True)
            self.preview_text.delete(1.0, tk.END)
            try:
                doc = Document(file_path)
                content = "\n\n".join([para.text for para in doc.paragraphs])
                self.preview_text.insert(
                    tk.END, content if content.strip() else "[Empty document]"
                )

                # Count numbered passages and display the count
                count = self.count_numbered_passages(content)
                self.preview_text.insert(
                    tk.END, f"\n\n[Numbered Passages Count: {count}]"
                )

                # Update the Treeview with the correct count
                self.result_tree.item(
                    selected_id,
                    values=(
                        item[0],  # Name
                        item[1],  # Type
                        item[2],  # Size
                        item[3],  # Modified
                        count,  # Numbered Passages
                    ),
                )

            except Exception as e:
                self.preview_text.insert(tk.END, f"Error reading .docx file:\n{e}")

        # Images
        elif ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp"]:
            try:
                # Show image preview
                img = Image.open(file_path)

                # Resize to fit the preview pane
                preview_width = self.preview_frame.winfo_width() - 20
                preview_height = self.preview_frame.winfo_height() - 20

                # If the preview frame hasn't been rendered yet, use default values
                if preview_width < 100:
                    preview_width = 400
                if preview_height < 100:
                    preview_height = 600

                img.thumbnail((preview_width, preview_height))
                photo = ImageTk.PhotoImage(img)

                self.image_label.configure(image=photo)
                self.image_label.image = (
                    photo  # Keep a reference to prevent garbage collection
                )
                self.image_label.pack(fill=tk.BOTH, expand=True)

            except Exception as e:
                self.preview_text.pack(fill=tk.BOTH, expand=True)
                self.preview_text.delete(1.0, tk.END)
                self.preview_text.insert(tk.END, f"Error displaying image: {e}")

        else:
            # Unsupported file type
            self.preview_text.pack(fill=tk.BOTH, expand=True)
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(tk.END, f"Preview not supported for {ext} files.")

    def count_numbered_passages(self, text):
        pattern = r"(?m)^\s*\d+[.,]"  # Start of line, digits, then . or ,
        return len(re.findall(pattern, text))

    def open_selected(self):
        selected = self.result_tree.focus()
        if not selected:
            return

        item = self.result_tree.item(selected)["values"]
        if not item:
            return

        name = item[0]
        file_path = os.path.join(self.target_folder, name)

        if os.path.isdir(file_path):
            # Navigate into directory
            self.set_target_folder(file_path)
        else:
            # Try to open the file with default system application
            try:
                (
                    os.startfile(file_path)
                    if os.name == "nt"
                    else os.system(f"xdg-open '{file_path}'")
                )
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file: {e}")

    def add_files(self):
        if not self.target_folder:
            messagebox.showerror("Error", "No target folder selected")
            return

        files = filedialog.askopenfilenames(title="Select Files to Add")
        if not files:
            return

        for file_path in files:
            try:
                file_name = os.path.basename(file_path)
                dest_path = os.path.join(self.target_folder, file_name)
                name, ext = os.path.splitext(file_name)
                counter = 1
                while os.path.exists(dest_path):
                    file_name = f"{name}_{counter}{ext}"
                    dest_path = os.path.join(self.target_folder, file_name)
                    counter += 1

                shutil.copy2(file_path, dest_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy {file_path}:\n{e}")
        self.view_contents()

    def add_folder(self):
        if not self.target_folder:
            messagebox.showerror("Error", "No target folder selected")
            return

        folder_path = filedialog.askdirectory(title="Select Folder to Add")
        if not folder_path:
            return

        folder_name = os.path.basename(folder_path)
        dest_path = os.path.join(self.target_folder, folder_name)

        counter = 1
        original_dest = dest_path
        while os.path.exists(dest_path):
            dest_path = f"{original_dest}_{counter}"
            counter += 1

        try:
            shutil.copytree(folder_path, dest_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy folder:\n{e}")
        self.view_contents()

    def create_subfolder(self):
        if not self.target_folder:
            messagebox.showerror("Error", "No target folder selected")
            return

        subfolder_name = simpledialog.askstring("New Folder", "Enter subfolder name:")
        if not subfolder_name:
            return

        new_folder_path = os.path.join(self.target_folder, subfolder_name)
        if os.path.exists(new_folder_path):
            messagebox.showerror("Error", "Folder already exists.")
            return

        try:
            os.mkdir(new_folder_path)
            self.view_contents()
        except Exception as e:
            messagebox.showerror("Error", f"Could not create folder:\n{e}")

    def rename_selected(self):
        if not self.selected_items or len(self.selected_items) != 1:
            messagebox.showinfo("Info", "Please select exactly one item to rename")
            return

        old_name = self.selected_items[0]
        old_path = os.path.join(self.target_folder, old_name)

        new_name = simpledialog.askstring(
            "Rename", "Enter new name:", initialvalue=old_name
        )
        if not new_name or new_name == old_name:
            return

        new_path = os.path.join(self.target_folder, new_name)
        if os.path.exists(new_path):
            messagebox.showerror("Error", "An item with that name already exists")
            return

        try:
            os.rename(old_path, new_path)
            self.view_contents()
            self.status_var.set(f"Renamed '{old_name}' to '{new_name}'")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to rename: {e}")

    def delete_selected(self):
        if not self.selected_items:
            messagebox.showinfo("Info", "No items selected")
            return

        count = len(self.selected_items)
        if count == 1:
            msg = f"Are you sure you want to delete '{self.selected_items[0]}'?"
        else:
            msg = f"Are you sure you want to delete {count} items?"

        if not messagebox.askyesno("Confirm Delete", msg):
            return

        deleted = 0
        for name in self.selected_items:
            path = os.path.join(self.target_folder, name)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                deleted += 1
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete '{name}': {e}")

        self.view_contents()
        self.status_var.set(f"Deleted {deleted} of {count} items")

    def move_selected(self):
        if not self.selected_items:
            messagebox.showinfo("Info", "No items selected")
            return

        dest_folder = filedialog.askdirectory(title="Select Destination Folder")
        if not dest_folder:
            return

        if dest_folder == self.target_folder:
            messagebox.showinfo("Info", "Source and destination folders are the same")
            return

        moved = 0
        for name in self.selected_items:
            src_path = os.path.join(self.target_folder, name)
            dest_path = os.path.join(dest_folder, name)

            # Handle name conflicts
            if os.path.exists(dest_path):
                base_name, ext = os.path.splitext(name)
                counter = 1
                while os.path.exists(dest_path):
                    new_name = f"{base_name}_{counter}{ext}"
                    dest_path = os.path.join(dest_folder, new_name)
                    counter += 1

            try:
                shutil.move(src_path, dest_path)
                moved += 1
            except Exception as e:
                messagebox.showerror("Error", f"Failed to move '{name}': {e}")

        self.view_contents()
        count = len(self.selected_items)
        self.status_var.set(
            f"Moved {moved} of {count} items to {os.path.basename(dest_folder)}"
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = FileManagerApp(root)
    root.mainloop()
