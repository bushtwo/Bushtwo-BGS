import os
import time
import datetime
import ctypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ---------------------------------------------------------
# Material 3 (M3) Dark Theme Design Tokens
# ---------------------------------------------------------
M3_SURFACE = "#141218"                    # Base window surface
M3_SURFACE_CONTAINER_LOW = "#1D1B20"      # Low-elevation surface
M3_SURFACE_CONTAINER = "#211F26"          # Standard card background
M3_SURFACE_CONTAINER_HIGH = "#2B2930"     # Elevated surface (dropdowns, inputs)
M3_SURFACE_CONTAINER_HIGHEST = "#36343B"  # Buttons, hover states

M3_PRIMARY = "#D0BCFF"                    # M3 Dark Primary Accent (Lavender Purple)
M3_ON_PRIMARY = "#381E72"                 # Contrast text on primary filled button
M3_PRIMARY_HOVER = "#B69DF8"

M3_PRIMARY_CONTAINER = "#4F378B"          # Tonal button background
M3_ON_PRIMARY_CONTAINER = "#EADDFF"

M3_ON_SURFACE = "#E6E0E9"                 # High-emphasis text
M3_ON_SURFACE_VARIANT = "#CAC4D0"         # Medium-emphasis text (subtitles, labels)
M3_MUTED = "#938F99"

M3_GREEN_CONTAINER = "#1D3B2B"            # Active status pill
M3_GREEN_TEXT = "#7DDA58"

M3_AMBER_CONTAINER = "#3B2D1D"            # Paused status pill
M3_AMBER_TEXT = "#FFB74D"

FONT_FAMILY = "Segoe UI"

SCALING_MODES_MAP = {
    "Fill (Crop to screen)": "Fill",
    "Fit (Preserve aspect ratio)": "Fit",
    "Stretch (Distort to fill)": "Stretch",
    "Tile (Repeat image)": "Tile",
    "Center (Actual size)": "Center",
    "Span (Multi-display)": "Span"
}

SCALING_REVERSE_MAP = {v: k for k, v in SCALING_MODES_MAP.items()}

TIMER_PRESETS = [
    "5 seconds",
    "15 seconds",
    "30 seconds",
    "1 minute",
    "5 minutes",
    "10 minutes",
    "15 minutes",
    "30 minutes",
    "1 Day (12:00 AM Midnight)"
]


def make_pill_image(text, bg_hex, fg_hex, height=28, radius=14, pad_x=14, font_size=9.5):
    """Renders a pixel-perfect anti-aliased pill badge with 16px/14px rounded corners and centered text."""
    scale = 3
    h = height * scale
    font = None
    try:
        font = ImageFont.truetype("segoeuib.ttf", int(font_size * scale))
    except Exception:
        try:
            font = ImageFont.truetype("arialbd.ttf", int(font_size * scale))
        except Exception:
            font = ImageFont.load_default()

    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), text, font=font, anchor="mm")
    text_w = bbox[2] - bbox[0]

    px = pad_x * scale
    w = int(text_w + px * 2)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius * scale, fill=bg_hex)

    # Pixel-perfect horizontal and vertical center using anchor='mm'
    d.text((w // 2, h // 2), text, font=font, fill=fg_hex, anchor="mm")

    return img.resize((w // scale, height), Image.Resampling.LANCZOS)


def make_rounded_thumbnail(img, target_w, target_h, radius=16):
    """Applies a smooth anti-aliased 16px rounded corner mask to the wallpaper thumbnail."""
    thumb = img.convert("RGBA").resize((target_w, target_h), Image.Resampling.LANCZOS)
    scale = 3
    mask_w = target_w * scale
    mask_h = target_h * scale
    mask = Image.new("L", (mask_w, mask_h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, mask_w - 1, mask_h - 1], radius=radius * scale, fill=255)
    mask = mask.resize((target_w, target_h), Image.Resampling.LANCZOS)

    bg = Image.new("RGBA", (target_w, target_h), (20, 18, 24, 0))
    bg.paste(thumb, (0, 0), mask)
    return bg


class AutoRoundedCard(tk.Canvas):
    """
    16px Anti-aliased Rounded Container Card.
    Hugs contents dynamically with 24px tblr padding.
    No hardcoded height clipping!
    """

    def __init__(self, parent, bg_color=M3_SURFACE_CONTAINER, window_bg=M3_SURFACE, radius=16, pad_x=24, pad_y=24, **kwargs):
        super().__init__(parent, bg=window_bg, bd=0, highlightthickness=0, **kwargs)
        self.bg_color = bg_color
        self.window_bg = window_bg
        self.radius = radius
        self.pad_x = pad_x
        self.pad_y = pad_y
        self.inner = tk.Frame(self, bg=bg_color)
        self.card_img = None
        self.inner_win = None

        # Automatically adjust canvas height to hug inner frame content + 24px padding
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.bind("<Configure>", self._on_canvas_configure)

    def _on_inner_configure(self, event=None):
        req_h = self.inner.winfo_reqheight()
        target_h = req_h + self.pad_y * 2
        if str(self.cget("height")) != str(target_h):
            self.configure(height=target_h)

    def _on_canvas_configure(self, event=None):
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 10 or h <= 10:
            return

        scale = 2
        img = Image.new("RGBA", (w * scale, h * scale), self.window_bg)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w * scale - 1, h * scale - 1], radius=self.radius * scale, fill=self.bg_color)
        img = img.resize((w, h), Image.Resampling.LANCZOS)
        self.card_img = ImageTk.PhotoImage(img)

        self.delete("bg")
        self.create_image(0, 0, anchor="nw", image=self.card_img, tags="bg")

        inner_w = max(1, w - self.pad_x * 2)
        inner_h = max(1, h - self.pad_y * 2)
        if self.inner_win is None:
            self.inner_win = self.create_window(w // 2, h // 2, window=self.inner, width=inner_w, height=inner_h, tags="inner")
        else:
            self.coords(self.inner_win, w // 2, h // 2)
            self.itemconfig(self.inner_win, width=inner_w, height=inner_h)
        self.tag_lower("bg")


class RoundedPopupMenu:
    """
    Popup Dropdown Menu with 16px Rounded Corners and NO BORDERS.
    Uses Windows 11 DWM rounded window attribute + Anti-aliased Canvas.
    """

    def __init__(self, parent, values, callback, width=240, bg=M3_SURFACE_CONTAINER_HIGH, fg=M3_ON_SURFACE, active_bg=M3_PRIMARY_CONTAINER, active_fg=M3_ON_PRIMARY_CONTAINER, radius=16):
        self.parent = parent
        self.values = values
        self.callback = callback
        self.width = width
        self.bg = bg
        self.fg = fg
        self.active_bg = active_bg
        self.active_fg = active_fg
        self.radius = radius
        self.top = None
        self.bg_img = None

    def show(self, x, y):
        if self.top and self.top.winfo_exists():
            self.top.destroy()

        self.top = tk.Toplevel(self.parent)
        self.top.overrideredirect(True)
        self.top.configure(bg=M3_SURFACE)

        # Apply native Windows 11 rounded window attribute (DWMWCP_ROUND)
        try:
            hwnd = ctypes.windll.user32.GetParent(self.top.winfo_id()) or self.top.winfo_id()
            val = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass

        row_h = 32
        pad_v = 10
        total_h = len(self.values) * row_h + pad_v * 2

        canvas = tk.Canvas(self.top, width=self.width, height=total_h, bg=M3_SURFACE, bd=0, highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        # Anti-aliased rounded rectangle background with NO border
        scale = 2
        img = Image.new("RGBA", (self.width * scale, total_h * scale), M3_SURFACE)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, self.width * scale - 1, total_h * scale - 1], radius=self.radius * scale, fill=self.bg)
        img = img.resize((self.width, total_h), Image.Resampling.LANCZOS)
        self.bg_img = ImageTk.PhotoImage(img)
        canvas.create_image(0, 0, anchor="nw", image=self.bg_img)

        inner = tk.Frame(canvas, bg=self.bg)
        canvas.create_window(self.width // 2, total_h // 2, window=inner, width=self.width - 16, height=total_h - 16)

        for val in self.values:
            row = tk.Label(
                inner,
                text=f"  {val}",
                font=(FONT_FAMILY, 9),
                bg=self.bg,
                fg=self.fg,
                anchor="w",
                cursor="hand2",
                padx=8,
                pady=4
            )
            row.pack(fill="x", pady=1)

            def _bind_row(v, r):
                def _enter(e): r.configure(bg=self.active_bg, fg=self.active_fg)
                def _leave(e): r.configure(bg=self.bg, fg=self.fg)
                def _click(e):
                    self.callback(v)
                    self.top.destroy()
                r.bind("<Enter>", _enter)
                r.bind("<Leave>", _leave)
                r.bind("<Button-1>", _click)

            _bind_row(val, row)

        self.top.geometry(f"{self.width}x{total_h}+{x}+{y}")

        # Auto-dismiss on click outside
        def _on_focus_out(e):
            if self.top and self.top.winfo_exists():
                self.top.destroy()

        self.top.bind("<FocusOut>", _on_focus_out)
        self.top.focus_set()


class M3RoundedDropdown(tk.Frame):
    """
    Material 3 Dropdown Component with:
    - Readable 10pt Segoe UI font (no shrunk fonts!)
    - 12px Rounded Button Container
    - Borderless 16px Rounded Popup Menu when clicked
    - Strictly readonly selection (no user keyboard typing)
    """

    def __init__(self, parent, variable, values, callback=None, bg_color=M3_SURFACE_CONTAINER_HIGH, hover_bg=M3_SURFACE_CONTAINER_HIGHEST, text_color=M3_ON_SURFACE, radius=12, height=36, **kwargs):
        super().__init__(parent, bg=bg_color, cursor="hand2", bd=0, highlightthickness=0, height=height, **kwargs)
        self.variable = variable
        self.values = values
        self.callback = callback
        self.bg_color = bg_color
        self.hover_bg = hover_bg
        self.text_color = text_color
        self.radius = radius
        self.btn_height = height
        self.pack_propagate(False)

        # Text label with readable, crisp font
        self.label = tk.Label(
            self,
            text=str(self.variable.get()),
            font=(FONT_FAMILY, 10),
            bg=bg_color,
            fg=text_color,
            anchor="w",
            cursor="hand2"
        )
        self.label.pack(side="left", fill="both", expand=True, padx=(12, 4))

        # Caret down symbol
        self.caret = tk.Label(
            self,
            text="▼",
            font=(FONT_FAMILY, 8),
            bg=bg_color,
            fg=M3_PRIMARY,
            cursor="hand2"
        )
        self.caret.pack(side="right", padx=(4, 12))

        self.popup = RoundedPopupMenu(self, self.values, self._on_select, width=250, radius=16)

        for w in (self, self.label, self.caret):
            w.bind("<Button-1>", self._show_popup)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _show_popup(self, event=None):
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.btn_height + 4
        self.popup.show(x, y)

    def _on_select(self, val):
        self.variable.set(val)
        display_text = str(val)
        if len(display_text) > 30:
            display_text = display_text[:27] + "..."
        self.label.config(text=display_text)
        if self.callback:
            self.callback(val)

    def _on_enter(self, event=None):
        for w in (self, self.label, self.caret):
            w.configure(bg=self.hover_bg)

    def _on_leave(self, event=None):
        for w in (self, self.label, self.caret):
            w.configure(bg=self.bg_color)

    def set(self, val):
        self._on_select(val)


class PhosphorCheckbox(tk.Frame):
    """Custom checkbox using crisp Phosphor icons (check-square & square)."""

    def __init__(self, parent, text, variable, checked_icon, unchecked_icon, bg=M3_SURFACE_CONTAINER, fg=M3_ON_SURFACE, command=None):
        super().__init__(parent, bg=bg, cursor="hand2")
        self.variable = variable
        self.checked_icon = checked_icon
        self.unchecked_icon = unchecked_icon
        self.command = command

        self.icon_label = tk.Label(self, bg=bg, cursor="hand2")
        self.icon_label.pack(side="left", padx=(0, 6))

        self.text_label = tk.Label(self, text=text, font=(FONT_FAMILY, 9), bg=bg, fg=fg, cursor="hand2")
        self.text_label.pack(side="left")

        self.bind("<Button-1>", self._toggle)
        self.icon_label.bind("<Button-1>", self._toggle)
        self.text_label.bind("<Button-1>", self._toggle)

        self._update_icon()

    def _toggle(self, event=None):
        new_val = not self.variable.get()
        self.variable.set(new_val)
        self._update_icon()
        if self.command:
            self.command()

    def _update_icon(self):
        if self.variable.get():
            self.icon_label.config(image=self.checked_icon)
        else:
            self.icon_label.config(image=self.unchecked_icon)


class WallpaperSwitcherUI:
    """
    Bushtwo BGS - Material 3 User Interface
    Strict 24px tblr padding inside sections (auto-hugs content).
    16px spacing between sections.
    16px rounded corners, borderless rounded dropdown menus,
    and readable, full-size typography.
    """

    def __init__(self, root, config_mgr, wallpaper_engine, playlist_mgr, tray_mgr):
        self.root = root
        self.config_mgr = config_mgr
        self.engine = wallpaper_engine
        self.playlist = playlist_mgr
        self.tray = tray_mgr

        # State variables
        self.current_wallpaper_path = self.config_mgr.get("last_wallpaper") or self.engine.get_current_system_wallpaper()
        self.timer_mode = self.config_mgr.get("timer_mode", "interval")
        self.interval_seconds = self.config_mgr.get("interval_seconds", 300)
        self.scaling_mode = self.config_mgr.get("scaling_mode", "Fill")
        self.is_paused = self.config_mgr.get("is_paused", False)
        self.run_at_startup = tk.BooleanVar(value=self.engine.is_startup_enabled())
        self.close_to_tray = tk.BooleanVar(value=self.config_mgr.get("close_to_tray", True))
        self.include_subfolders = tk.BooleanVar(value=self.config_mgr.get("include_subfolders", True))

        self.time_remaining = self._get_initial_time_remaining()
        self.last_tick_time = time.time()

        # Cached icon images
        self.icons = {}
        self.preview_tk_image = None
        self.badge_active_tk = None
        self.badge_paused_tk = None
        self.badge_timer_tk = None

        self._load_app_icons()
        self._setup_window()
        self._configure_m3_styles()
        self._build_ui_layout()
        self._populate_initial_state()
        self._start_timer_loop()

    # ---------------------------------------------------------
    # ICONS & WINDOW SETUP
    # ---------------------------------------------------------
    def _load_app_icons(self):
        """Loads Phosphor icons and application taskbar icons."""
        app_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icons_dir = os.path.join(app_dir, "icons")

        icon_specs = [
            ("shuffle", "shuffle_on_primary_20.png"),
            ("prev", "skip-back_text_20.png"),
            ("pause", "pause_text_20.png"),
            ("play", "play_primary_20.png"),
            ("add_folder", "folder-plus_text_16.png"),
            ("remove_folder", "trash_text_16.png"),
            ("rescan", "arrows-clockwise_text_16.png"),
            ("desktop", "desktop_primary_20.png"),
            ("folder", "folder_primary_18.png"),
            ("check_checked", "check-square_primary_18.png"),
            ("check_unchecked", "square_muted_18.png"),
        ]

        for key, filename in icon_specs:
            path = os.path.join(icons_dir, filename)
            if os.path.exists(path):
                try:
                    self.icons[key] = ImageTk.PhotoImage(Image.open(path))
                except Exception as e:
                    print(f"Error loading icon {filename}: {e}")

        # Load user application icons
        p16 = os.path.join(app_dir, "Bushtwo BGS 16 x16 pixels.png")
        p32 = os.path.join(app_dir, "Bushtwo BGS 32x32 pixels.png")
        p64 = os.path.join(app_dir, "Bushtwo BGS 64x64 pixels.png")

        try:
            self.app_icon_16 = tk.PhotoImage(file=p16) if os.path.exists(p16) else None
            self.app_icon_32 = tk.PhotoImage(file=p32) if os.path.exists(p32) else None
            self.app_icon_64 = tk.PhotoImage(file=p64) if os.path.exists(p64) else None
        except Exception as e:
            print(f"Error loading user icon PNGs: {e}")

    def _setup_window(self):
        """Sets title, icons, adaptive fixed dimensions, and disables resizing."""
        self.root.title("Bushtwo BGS")
        self.root.configure(bg=M3_SURFACE)
        self.root.resizable(False, False)

        if self.app_icon_64 and self.app_icon_32 and self.app_icon_16:
            try:
                self.root.iconphoto(True, self.app_icon_64, self.app_icon_32, self.app_icon_16)
            except Exception:
                pass

        app_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(app_dir, "bushtwo_bgs.ico")
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass

        self.root.protocol("WM_DELETE_WINDOW", self.on_close_requested)

    def _configure_m3_styles(self):
        """Configures ttk styles for borderless Material 3 components."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Completely borderless Treeview layout
        style.layout("M3.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure(
            "M3.Treeview",
            background=M3_SURFACE_CONTAINER_LOW,
            foreground=M3_ON_SURFACE,
            fieldbackground=M3_SURFACE_CONTAINER_LOW,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            rowheight=26,
            font=(FONT_FAMILY, 9)
        )
        style.map(
            "M3.Treeview",
            background=[("selected", M3_PRIMARY_CONTAINER)],
            foreground=[("selected", M3_ON_PRIMARY_CONTAINER)]
        )

    # ---------------------------------------------------------
    # MAIN UI LAYOUT (24px TBLR PADDING IN SECTIONS, 16px SPACING)
    # ---------------------------------------------------------
    def _build_ui_layout(self):
        self.main_container = tk.Frame(self.root, bg=M3_SURFACE)
        self.main_container.pack(fill="both", expand=True, padx=8, pady=8)

        # 1. Current Wallpaper Preview Section (24px padding inside)
        self._build_section1_preview()

        # 2. Desktop Monitor Details Section (16px gap from above)
        self._build_section2_monitor_details()

        # 3. Wallpaper Name & Playback Controls (16px gap from above)
        self._build_section3_wallpaper_controls()

        # 4. Wallpaper Folders Section (16px gap from above, hugs contents)
        self._build_section4_folders()

        # 5. Side-by-Side: Scaling Mode & Shuffle Timer (16px gap from above, readable font)
        self._build_section5_scaling_and_timer_side_by_side()

        # 6. System & Background Options (16px gap from above)
        self._build_section6_options()

        # Automatically size window to hug all sections perfectly
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        req_w = 580
        req_h = self.main_container.winfo_reqheight() + 16
        pos_x = (screen_w - req_w) // 2
        pos_y = max(10, (screen_h - req_h) // 2 - 20)
        self.root.geometry(f"{req_w}x{req_h}+{pos_x}+{pos_y}")

    # ---------------------------------------------------------
    # 1. CURRENT DESKTOP WALLPAPER PREVIEW (24px PADDING)
    # ---------------------------------------------------------
    def _build_section1_preview(self):
        self.card_preview = AutoRoundedCard(self.main_container, radius=16, pad_x=24, pad_y=24)
        self.card_preview.pack(fill="x", pady=(0, 16))

        inner = self.card_preview.inner

        header_frame = tk.Frame(inner, bg=M3_SURFACE_CONTAINER)
        header_frame.pack(fill="x", pady=(0, 8))

        tk.Label(
            header_frame,
            text="CURRENT DESKTOP WALLPAPER",
            font=(FONT_FAMILY, 9, "bold"),
            fg=M3_ON_SURFACE_VARIANT,
            bg=M3_SURFACE_CONTAINER
        ).pack(side="left")

        # 16px Rounded Corner Active/Paused pill badge
        self.badge_active_tk = ImageTk.PhotoImage(make_pill_image("● ACTIVE", M3_GREEN_CONTAINER, M3_GREEN_TEXT, height=24, radius=12, font_size=8.5))
        self.badge_paused_tk = ImageTk.PhotoImage(make_pill_image("⏸ PAUSED", M3_AMBER_CONTAINER, M3_AMBER_TEXT, height=24, radius=12, font_size=8.5))

        self.status_badge = tk.Label(header_frame, image=self.badge_active_tk, bg=M3_SURFACE_CONTAINER, bd=0)
        self.status_badge.pack(side="right")

        # 16px Rounded Thumbnail container
        self.preview_height = 145
        self.preview_container = tk.Frame(inner, bg=M3_SURFACE_CONTAINER, height=self.preview_height)
        self.preview_container.pack(fill="x")
        self.preview_container.pack_propagate(False)

        self.preview_label = tk.Label(self.preview_container, bg=M3_SURFACE_CONTAINER, bd=0)
        self.preview_label.pack(expand=True, fill="both")

    # ---------------------------------------------------------
    # 2. UNDERNEATH CURRENT DESKTOP MONITOR DETAILS (24px PADDING, 16px GAP)
    # ---------------------------------------------------------
    def _build_section2_monitor_details(self):
        self.card_monitor = AutoRoundedCard(self.main_container, bg_color=M3_SURFACE_CONTAINER_LOW, radius=16, pad_x=24, pad_y=16)
        self.card_monitor.pack(fill="x", pady=(0, 16))

        inner = self.card_monitor.inner

        if "desktop" in self.icons:
            tk.Label(inner, image=self.icons["desktop"], bg=M3_SURFACE_CONTAINER_LOW, bd=0).pack(side="left", padx=(0, 8))

        tk.Label(
            inner,
            text="Primary Display:",
            font=(FONT_FAMILY, 9, "bold"),
            fg=M3_ON_SURFACE_VARIANT,
            bg=M3_SURFACE_CONTAINER_LOW
        ).pack(side="left")

        display_info = self.engine.get_display_info()
        disp_text = display_info.get("formatted", "2560 × 1440 @ 120Hz (32-bit color)")

        self.monitor_detail_label = tk.Label(
            inner,
            text=disp_text,
            font=(FONT_FAMILY, 9, "bold"),
            fg=M3_PRIMARY,
            bg=M3_SURFACE_CONTAINER_LOW
        )
        self.monitor_detail_label.pack(side="left", padx=8)

    # ---------------------------------------------------------
    # 3. WALLPAPER NAME & CONTROLS (24px PADDING, 16px GAP)
    # ---------------------------------------------------------
    def _build_section3_wallpaper_controls(self):
        self.card_controls = AutoRoundedCard(self.main_container, radius=16, pad_x=24, pad_y=24)
        self.card_controls.pack(fill="x", pady=(0, 16))

        inner = self.card_controls.inner

        self.wp_name_label = tk.Label(
            inner,
            text="No wallpaper loaded",
            font=(FONT_FAMILY, 11, "bold"),
            fg=M3_ON_SURFACE,
            bg=M3_SURFACE_CONTAINER,
            anchor="w"
        )
        self.wp_name_label.pack(fill="x")

        self.wp_sub_label = tk.Label(
            inner,
            text="Select image folders below to start shuffling",
            font=(FONT_FAMILY, 8),
            fg=M3_ON_SURFACE_VARIANT,
            bg=M3_SURFACE_CONTAINER,
            anchor="w"
        )
        self.wp_sub_label.pack(fill="x", pady=(2, 12))

        btn_frame = tk.Frame(inner, bg=M3_SURFACE_CONTAINER)
        btn_frame.pack(fill="x")

        self.btn_prev = tk.Button(
            btn_frame,
            text=" Prev",
            image=self.icons.get("prev"),
            compound="left",
            font=(FONT_FAMILY, 9),
            bg=M3_SURFACE_CONTAINER_HIGHEST,
            fg=M3_ON_SURFACE,
            activebackground="#4A4752",
            activeforeground=M3_ON_SURFACE,
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.action_previous
        )
        self.btn_prev.pack(side="left", padx=(0, 8))

        self.btn_next = tk.Button(
            btn_frame,
            text=" Shuffle / Next",
            image=self.icons.get("shuffle"),
            compound="left",
            font=(FONT_FAMILY, 9, "bold"),
            bg=M3_PRIMARY,
            fg=M3_ON_PRIMARY,
            activebackground=M3_PRIMARY_HOVER,
            activeforeground=M3_ON_PRIMARY,
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.action_next
        )
        self.btn_next.pack(side="left", padx=(0, 8))

        self.btn_pause = tk.Button(
            btn_frame,
            text=" Pause",
            image=self.icons.get("pause"),
            compound="left",
            font=(FONT_FAMILY, 9),
            bg=M3_SURFACE_CONTAINER_HIGHEST,
            fg=M3_ON_SURFACE,
            activebackground="#4A4752",
            activeforeground=M3_ON_SURFACE,
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.action_toggle_pause
        )
        self.btn_pause.pack(side="left", padx=(0, 8))

        self.timer_badge_label = tk.Label(btn_frame, bg=M3_SURFACE_CONTAINER, bd=0)
        self.timer_badge_label.pack(side="right")
        self._update_timer_badge()

    # ---------------------------------------------------------
    # 4. FOLDERS LIST & ACTIONS (24px PADDING, 16px GAP, HUGS CONTENTS)
    # ---------------------------------------------------------
    def _build_section4_folders(self):
        self.card_folders = AutoRoundedCard(self.main_container, radius=16, pad_x=24, pad_y=24)
        self.card_folders.pack(fill="x", pady=(0, 16))

        inner = self.card_folders.inner

        hdr = tk.Frame(inner, bg=M3_SURFACE_CONTAINER)
        hdr.pack(fill="x", pady=(0, 6))

        tk.Label(
            hdr,
            text="WALLPAPER FOLDERS",
            font=(FONT_FAMILY, 9, "bold"),
            fg=M3_ON_SURFACE_VARIANT,
            bg=M3_SURFACE_CONTAINER
        ).pack(side="left")

        self.total_count_label = tk.Label(
            hdr,
            text="0 images",
            font=(FONT_FAMILY, 9, "bold"),
            fg=M3_PRIMARY,
            bg=M3_SURFACE_CONTAINER
        )
        self.total_count_label.pack(side="right")

        # Treeview with Phosphor folder icon, NO borders
        self.folder_tree = ttk.Treeview(
            inner,
            style="M3.Treeview",
            show="tree",
            selectmode="browse",
            height=2
        )
        self.folder_tree.pack(fill="x", pady=(0, 10))

        # Actions Row: fully visible, never squeezed!
        actions_row = tk.Frame(inner, bg=M3_SURFACE_CONTAINER)
        actions_row.pack(fill="x")

        btn_add = tk.Button(
            actions_row,
            text=" Add Folder...",
            image=self.icons.get("add_folder"),
            compound="left",
            font=(FONT_FAMILY, 9),
            bg=M3_SURFACE_CONTAINER_HIGHEST,
            fg=M3_ON_SURFACE,
            activebackground="#4A4752",
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self.action_add_folder
        )
        btn_add.pack(side="left", padx=(0, 8))

        btn_remove = tk.Button(
            actions_row,
            text=" Remove",
            image=self.icons.get("remove_folder"),
            compound="left",
            font=(FONT_FAMILY, 9),
            bg=M3_SURFACE_CONTAINER_HIGHEST,
            fg=M3_ON_SURFACE,
            activebackground="#4A4752",
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self.action_remove_folder
        )
        btn_remove.pack(side="left", padx=(0, 8))

        btn_rescan = tk.Button(
            actions_row,
            text=" Rescan",
            image=self.icons.get("rescan"),
            compound="left",
            font=(FONT_FAMILY, 9),
            bg=M3_SURFACE_CONTAINER_HIGHEST,
            fg=M3_ON_SURFACE,
            activebackground="#4A4752",
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self.action_rescan
        )
        btn_rescan.pack(side="left", padx=(0, 12))

        self.cb_subfolders = PhosphorCheckbox(
            actions_row,
            text="Include subfolders",
            variable=self.include_subfolders,
            checked_icon=self.icons.get("check_checked"),
            unchecked_icon=self.icons.get("check_unchecked"),
            bg=M3_SURFACE_CONTAINER,
            fg=M3_ON_SURFACE_VARIANT,
            command=self.on_subfolders_toggle
        )
        self.cb_subfolders.pack(side="right")

    # ---------------------------------------------------------
    # 5. SIDE-BY-SIDE: SCALING MODE & SHUFFLE TIMER (24px PADDING, 16px GAP)
    # ---------------------------------------------------------
    def _build_section5_scaling_and_timer_side_by_side(self):
        row_frame = tk.Frame(self.main_container, bg=M3_SURFACE)
        row_frame.pack(fill="x", pady=(0, 16))

        # ---- LEFT COLUMN: SCALING MODE (24px padding inside) ----
        self.card_scaling = AutoRoundedCard(row_frame, radius=16, pad_x=24, pad_y=20)
        self.card_scaling.pack(side="left", fill="both", expand=True, padx=(0, 8))

        inner_left = self.card_scaling.inner

        tk.Label(
            inner_left,
            text="SCALING MODE",
            font=(FONT_FAMILY, 9, "bold"),
            fg=M3_ON_SURFACE_VARIANT,
            bg=M3_SURFACE_CONTAINER
        ).pack(anchor="w", pady=(0, 6))

        current_scaling_label = SCALING_REVERSE_MAP.get(self.scaling_mode, "Fill (Crop to screen)")
        self.scaling_var = tk.StringVar(value=current_scaling_label)

        # Readable font, 16px rounded popup menu without borders
        self.dd_scaling = M3RoundedDropdown(
            inner_left,
            variable=self.scaling_var,
            values=list(SCALING_MODES_MAP.keys()),
            callback=self.on_scaling_dropdown_changed,
            radius=12,
            height=36
        )
        self.dd_scaling.pack(fill="x", pady=(0, 6))

        self.scaling_desc_label = tk.Label(
            inner_left,
            text=self._get_scaling_hint(self.scaling_mode),
            font=(FONT_FAMILY, 8),
            fg=M3_MUTED,
            bg=M3_SURFACE_CONTAINER,
            anchor="w"
        )
        self.scaling_desc_label.pack(fill="x")

        # ---- RIGHT COLUMN: SHUFFLE TIMER (24px padding inside) ----
        self.card_timer = AutoRoundedCard(row_frame, radius=16, pad_x=24, pad_y=20)
        self.card_timer.pack(side="right", fill="both", expand=True, padx=(8, 0))

        inner_right = self.card_timer.inner

        tk.Label(
            inner_right,
            text="SHUFFLE TIMER",
            font=(FONT_FAMILY, 9, "bold"),
            fg=M3_ON_SURFACE_VARIANT,
            bg=M3_SURFACE_CONTAINER
        ).pack(anchor="w", pady=(0, 6))

        init_timer_text = "1 Day (12:00 AM Midnight)" if self.timer_mode == "day" else self._format_interval(self.interval_seconds)
        self.timer_var = tk.StringVar(value=init_timer_text)

        # Readable font, strictly selectable options, 16px rounded popup menu without borders
        self.dd_timer = M3RoundedDropdown(
            inner_right,
            variable=self.timer_var,
            values=TIMER_PRESETS,
            callback=self.on_timer_dropdown_changed,
            radius=12,
            height=36
        )
        self.dd_timer.pack(fill="x", pady=(0, 6))

        self.timer_desc_label = tk.Label(
            inner_right,
            text="Changes daily at 12:00 AM midnight" if self.timer_mode == "day" else "Select interval from options",
            font=(FONT_FAMILY, 8),
            fg=M3_MUTED,
            bg=M3_SURFACE_CONTAINER,
            anchor="w"
        )
        self.timer_desc_label.pack(fill="x")

    def _get_scaling_hint(self, mode: str) -> str:
        hints = {
            "Fill": "Crops to fill screen without black bars",
            "Fit": "Preserves aspect ratio with letterbox bars",
            "Stretch": "Stretches to fill exact screen size",
            "Tile": "Repeats image in pattern across screen",
            "Center": "Centers image at actual 1:1 pixel size",
            "Span": "Spans wallpaper across multi-monitors"
        }
        return hints.get(mode, "Select scaling mode")

    # ---------------------------------------------------------
    # 6. SYSTEM OPTIONS (24px PADDING)
    # ---------------------------------------------------------
    def _build_section6_options(self):
        self.card_options = AutoRoundedCard(self.main_container, bg_color=M3_SURFACE_CONTAINER_LOW, radius=16, pad_x=24, pad_y=16)
        self.card_options.pack(fill="x")

        inner = self.card_options.inner

        self.cb_startup = PhosphorCheckbox(
            inner,
            text="Run automatically when Windows starts up",
            variable=self.run_at_startup,
            checked_icon=self.icons.get("check_checked"),
            unchecked_icon=self.icons.get("check_unchecked"),
            bg=M3_SURFACE_CONTAINER_LOW,
            fg=M3_ON_SURFACE,
            command=self.on_startup_toggle
        )
        self.cb_startup.pack(side="left")

        self.cb_tray = PhosphorCheckbox(
            inner,
            text="Minimize to tray on close",
            variable=self.close_to_tray,
            checked_icon=self.icons.get("check_checked"),
            unchecked_icon=self.icons.get("check_unchecked"),
            bg=M3_SURFACE_CONTAINER_LOW,
            fg=M3_ON_SURFACE,
            command=self.on_close_to_tray_toggle
        )
        self.cb_tray.pack(side="right")

    # ---------------------------------------------------------
    # STATE POPULATION & THUMBNAIL RENDERING
    # ---------------------------------------------------------
    def _populate_initial_state(self):
        self._refresh_folders_treeview()
        if self.current_wallpaper_path and os.path.exists(self.current_wallpaper_path):
            self._update_current_wallpaper_display(self.current_wallpaper_path)
        else:
            self._display_placeholder()
        self._update_pause_ui()

    def _refresh_folders_treeview(self):
        for item in self.folder_tree.get_children():
            self.folder_tree.delete(item)

        counts = self.playlist.get_folder_counts()
        folder_icon = self.icons.get("folder")

        for folder in self.playlist.folders:
            count = counts.get(folder, 0)
            text_str = f"  {folder} ({count} images)"
            if folder_icon:
                self.folder_tree.insert("", "end", text=text_str, image=folder_icon)
            else:
                self.folder_tree.insert("", "end", text=text_str)

        total = self.playlist.get_total_count()
        self.total_count_label.config(text=f"{total} image{'s' if total != 1 else ''}")

    def _display_placeholder(self):
        self.wp_name_label.config(text="No wallpaper set yet")
        self.wp_sub_label.config(text="Add one or more image folders above to begin shuffling")
        img = Image.new("RGBA", (480, self.preview_height), (20, 18, 24, 255))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, 479, self.preview_height - 1], radius=16, fill="#1D1B20")
        self.preview_tk_image = ImageTk.PhotoImage(img)
        self.preview_label.config(
            image=self.preview_tk_image,
            text="➕ Add folders below to begin shuffling",
            compound="center",
            fg=M3_ON_SURFACE_VARIANT,
            font=(FONT_FAMILY, 9)
        )

    def _update_current_wallpaper_display(self, path: str):
        if not path or not os.path.exists(path):
            self._display_placeholder()
            return

        filename = os.path.basename(path)
        self.wp_name_label.config(text=filename)

        try:
            with Image.open(path) as img:
                orig_w, orig_h = img.size
                file_size_mb = os.path.getsize(path) / (1024 * 1024)
                parent_dir = os.path.dirname(path)

                sub_text = f"{orig_w} × {orig_h} • {file_size_mb:.1f} MB • {parent_dir}"
                self.wp_sub_label.config(text=sub_text)

                max_w = 500
                max_h = self.preview_height
                aspect = orig_w / orig_h

                if (max_w / max_h) > aspect:
                    target_h = max_h
                    target_w = int(max_h * aspect)
                else:
                    target_w = max_w
                    target_h = int(max_w / aspect)

                target_w = max(1, target_w)
                target_h = max(1, target_h)

                rounded_thumb = make_rounded_thumbnail(img, target_w, target_h, radius=16)
                self.preview_tk_image = ImageTk.PhotoImage(rounded_thumb)
                self.preview_label.config(image=self.preview_tk_image, text="")
        except Exception as e:
            print(f"Error loading preview for {path}: {e}")
            self.wp_sub_label.config(text=f"Error loading preview: {e}")

        if self.tray:
            self.tray.update_status(filename, self.is_paused)

    # ---------------------------------------------------------
    # USER ACTIONS: PREV / NEXT / PAUSE / FOLDERS / DROPDOWNS
    # ---------------------------------------------------------
    def action_next(self):
        if not self.playlist.has_images():
            messagebox.showinfo("No Images", "Please add at least one folder containing images first.")
            return

        next_wp = self.playlist.get_next_wallpaper()
        if next_wp and os.path.exists(next_wp):
            success = self.engine.set_wallpaper(next_wp, self.scaling_mode)
            if success:
                self.current_wallpaper_path = next_wp
                self.config_mgr.set("last_wallpaper", next_wp)
                self.config_mgr.set("history", self.playlist.history)
                self._update_current_wallpaper_display(next_wp)
                self.time_remaining = self._get_initial_time_remaining()
                self._update_timer_badge()

    def action_previous(self):
        prev_wp = self.playlist.get_previous_wallpaper()
        if prev_wp and os.path.exists(prev_wp):
            success = self.engine.set_wallpaper(prev_wp, self.scaling_mode)
            if success:
                self.current_wallpaper_path = prev_wp
                self.config_mgr.set("last_wallpaper", prev_wp)
                self._update_current_wallpaper_display(prev_wp)
                self.time_remaining = self._get_initial_time_remaining()
                self._update_timer_badge()

    def action_toggle_pause(self):
        self.is_paused = not self.is_paused
        self.config_mgr.set("is_paused", self.is_paused)
        self._update_pause_ui()
        if self.tray:
            self.tray.update_status(os.path.basename(self.current_wallpaper_path or ""), self.is_paused)

    def _update_pause_ui(self):
        if self.is_paused:
            self.btn_pause.config(
                text=" Resume",
                image=self.icons.get("play"),
                bg=M3_AMBER_CONTAINER,
                fg=M3_AMBER_TEXT
            )
            self.status_badge.config(image=self.badge_paused_tk)
        else:
            self.btn_pause.config(
                text=" Pause",
                image=self.icons.get("pause"),
                bg=M3_SURFACE_CONTAINER_HIGHEST,
                fg=M3_ON_SURFACE
            )
            self.status_badge.config(image=self.badge_active_tk)
        self._update_timer_badge()

    def action_add_folder(self):
        selected_dir = filedialog.askdirectory(title="Select Folder Containing Wallpapers")
        if selected_dir:
            added = self.playlist.add_folder(selected_dir)
            if added:
                self.config_mgr.set("folders", self.playlist.folders)
                self._refresh_folders_treeview()
                if not self.current_wallpaper_path or not os.path.exists(self.current_wallpaper_path):
                    self.action_next()

    def action_remove_folder(self):
        selected = self.folder_tree.selection()
        if not selected:
            messagebox.showinfo("Select Folder", "Please select a folder in the list to remove.")
            return

        item_idx = self.folder_tree.index(selected[0])
        if item_idx < len(self.playlist.folders):
            folder_to_remove = self.playlist.folders[item_idx]
            self.playlist.remove_folder(folder_to_remove)
            self.config_mgr.set("folders", self.playlist.folders)
            self._refresh_folders_treeview()

    def action_rescan(self):
        self.playlist.rescan()
        self._refresh_folders_treeview()

    def on_subfolders_toggle(self):
        val = self.include_subfolders.get()
        self.playlist.set_include_subfolders(val)
        self.config_mgr.set("include_subfolders", val)
        self._refresh_folders_treeview()

    # ---------------------------------------------------------
    # DROPDOWNS: SCALING & TIMER HANDLERS
    # ---------------------------------------------------------
    def on_scaling_dropdown_changed(self, selected_label: str):
        mode = SCALING_MODES_MAP.get(selected_label, "Fill")
        self.scaling_mode = mode
        self.config_mgr.set("scaling_mode", mode)
        self.scaling_desc_label.config(text=self._get_scaling_hint(mode))

        if self.current_wallpaper_path and os.path.exists(self.current_wallpaper_path):
            self.engine.set_wallpaper(self.current_wallpaper_path, self.scaling_mode)

    def on_timer_dropdown_changed(self, selected_text: str):
        if "Day" in selected_text:
            self.timer_mode = "day"
            self.config_mgr.set("timer_mode", "day")
            self.timer_desc_label.config(text="Changes daily at 12:00 AM midnight")
        else:
            self.timer_mode = "interval"
            self.config_mgr.set("timer_mode", "interval")
            secs = self._parse_preset_seconds(selected_text)
            self.interval_seconds = secs
            self.config_mgr.set("interval_seconds", secs)
            self.timer_desc_label.config(text="Select interval from options")

        self.time_remaining = self._get_initial_time_remaining()
        self._update_timer_badge()

    def _parse_preset_seconds(self, text: str) -> int:
        presets_map = {
            "5 seconds": 5,
            "15 seconds": 15,
            "30 seconds": 30,
            "1 minute": 60,
            "5 minutes": 300,
            "10 minutes": 600,
            "15 minutes": 900,
            "30 minutes": 1800
        }
        return presets_map.get(text, 300)

    def _format_interval(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds % 3600 == 0:
            hrs = seconds // 3600
            return f"{hrs} hour{'s' if hrs > 1 else ''}"
        elif seconds % 60 == 0:
            mins = seconds // 60
            return f"{mins} minute{'s' if mins > 1 else ''}"
        else:
            mins = seconds // 60
            secs = seconds % 60
            return f"{mins}m {secs}s"

    def _get_seconds_until_midnight(self) -> int:
        now = datetime.datetime.now()
        tomorrow = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1, int((tomorrow - now).total_seconds()))

    def _get_initial_time_remaining(self) -> float:
        if self.timer_mode == "day":
            return float(self._get_seconds_until_midnight())
        return float(self.interval_seconds)

    # ---------------------------------------------------------
    # TIMER LOOP
    # ---------------------------------------------------------
    def _start_timer_loop(self):
        self._timer_tick()

    def _timer_tick(self):
        now = time.time()
        elapsed = now - self.last_tick_time
        self.last_tick_time = now

        if not self.is_paused and self.playlist.has_images():
            if self.timer_mode == "day":
                now_dt = datetime.datetime.now()
                today_str = now_dt.strftime("%Y-%m-%d")
                last_switched = self.config_mgr.get("last_day_switched")

                if last_switched != today_str and now_dt.hour == 0 and now_dt.minute == 0:
                    self.action_next()
                    self.config_mgr.set("last_day_switched", today_str)

                self._update_timer_badge()
            else:
                self.time_remaining -= elapsed
                if self.time_remaining <= 0:
                    self.action_next()
                    self.time_remaining = float(self.interval_seconds)

                self._update_timer_badge()

        self.root.after(1000, self._timer_tick)

    def _update_timer_badge(self):
        if self.is_paused:
            text = "Timer Paused"
            bg = M3_AMBER_CONTAINER
            fg = M3_AMBER_TEXT
        elif self.timer_mode == "day":
            secs = self._get_seconds_until_midnight()
            hours = secs // 3600
            mins = (secs % 3600) // 60
            text = f"Next: 12:00 AM ({hours}h {mins:02d}m)"
            bg = M3_PRIMARY_CONTAINER
            fg = M3_ON_PRIMARY_CONTAINER
        else:
            total_sec = max(0, int(self.time_remaining))
            mins = total_sec // 60
            secs = total_sec % 60
            text = f"Next in: {mins:02d}:{secs:02d}"
            bg = M3_PRIMARY_CONTAINER
            fg = M3_ON_PRIMARY_CONTAINER

        self.badge_timer_tk = ImageTk.PhotoImage(
            make_pill_image(text, bg, fg, height=28, radius=14, pad_x=14, font_size=9.5)
        )
        self.timer_badge_label.config(image=self.badge_timer_tk)

    # ---------------------------------------------------------
    # STARTUP & WINDOW MANAGEMENT
    # ---------------------------------------------------------
    def on_startup_toggle(self):
        val = self.run_at_startup.get()
        self.engine.set_startup(val)
        self.config_mgr.set("run_at_startup", val)

    def on_close_to_tray_toggle(self):
        self.config_mgr.set("close_to_tray", self.close_to_tray.get())

    def on_close_requested(self):
        if self.close_to_tray.get():
            self.hide_window()
        else:
            self.exit_app()

    def hide_window(self):
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def exit_app(self):
        if self.tray:
            self.tray.stop()
        self.root.destroy()
