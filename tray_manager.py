import os
import sys
import threading
import tempfile
import ctypes
from PIL import Image
import pystray
from pystray import MenuItem as item

IMAGE_BITMAP = 0
LR_LOADFROMFILE = 0x0010
MIIM_BITMAP = 0x00000080


def _load_hbitmap(png_path):
    """Converts a PNG image to a 32-bit PARGB Windows HBITMAP handle for transparent tray menu icons."""
    if not os.path.exists(png_path):
        return None
    try:
        from ctypes import wintypes

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)
            ]

        img = Image.open(png_path).convert('RGBA').resize((16, 16), Image.Resampling.LANCZOS)
        width, height = img.size

        bih = BITMAPINFOHEADER()
        bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bih.biWidth = width
        bih.biHeight = height
        bih.biPlanes = 1
        bih.biBitCount = 32
        bih.biCompression = 0

        hdc = ctypes.windll.user32.GetDC(None)
        ppvBits = ctypes.c_void_p()
        hbitmap = ctypes.windll.gdi32.CreateDIBSection(
            hdc, ctypes.byref(bih), 0, ctypes.byref(ppvBits), None, 0
        )
        ctypes.windll.user32.ReleaseDC(None, hdc)

        if not hbitmap or not ppvBits.value:
            return None

        raw_data = bytearray(width * height * 4)
        pixels = img.load()
        idx = 0
        for y in reversed(range(height)):
            for x in range(width):
                r, g, b, a = pixels[x, y]
                alpha_f = a / 255.0
                raw_data[idx] = int(b * alpha_f)
                raw_data[idx + 1] = int(g * alpha_f)
                raw_data[idx + 2] = int(r * alpha_f)
                raw_data[idx + 3] = a
                idx += 4

        ctypes.memmove(ppvBits, bytes(raw_data), len(raw_data))
        return hbitmap
    except Exception as e:
        print(f"Error loading HBITMAP for {png_path}: {e}")
        return None


# Enable Windows native menu item icons in pystray
if sys.platform == 'win32':
    try:
        import pystray._win32
        _orig_create_menu_item = pystray._win32.Icon._create_menu_item

        def _custom_create_menu_item(self, descriptor, callbacks):
            info = _orig_create_menu_item(self, descriptor, callbacks)
            bmp = getattr(descriptor, '_hbmp', None)
            if bmp:
                info.fMask |= MIIM_BITMAP
                info.hbmpItem = bmp
            return info

        pystray._win32.Icon._create_menu_item = _custom_create_menu_item
    except Exception as e:
        print(f"Could not patch pystray for menu bitmaps: {e}")


class TrayManager:
    """
    Manages the Windows Notification Area (System Tray) icon,
    Phosphor icon menu items, and background actions for Bushtwo BGS.
    """

    def __init__(self, on_show, on_next, on_prev, on_toggle_pause, on_exit):
        self.on_show = on_show
        self.on_next = on_next
        self.on_prev = on_prev
        self.on_toggle_pause = on_toggle_pause
        self.on_exit = on_exit

        self.app_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icons_dir = os.path.join(self.app_dir, "icons")

        # Load Phosphor HBITMAPs for tray menu (transparent 32-bit PARGB)
        self.hbmp_shuffle = _load_hbitmap(os.path.join(icons_dir, "shuffle_primary_16.png"))
        self.hbmp_prev = _load_hbitmap(os.path.join(icons_dir, "skip-back_primary_16.png"))
        self.hbmp_pause = _load_hbitmap(os.path.join(icons_dir, "pause_primary_16.png"))
        self.hbmp_play = _load_hbitmap(os.path.join(icons_dir, "play_primary_16.png"))
        self.hbmp_desktop = _load_hbitmap(os.path.join(icons_dir, "desktop_primary_16.png"))
        self.hbmp_exit = _load_hbitmap(os.path.join(icons_dir, "x_primary_16.png"))

        # Main tray icon image
        icon_path = os.path.join(self.app_dir, "Bushtwo BGS 64x64 pixels.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(self.app_dir, "Bushtwo BGS 32x32 pixels.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(self.app_dir, "bushtwo_bgs.ico")

        if os.path.exists(icon_path):
            try:
                self.icon_image = Image.open(icon_path)
            except Exception:
                self.icon_image = Image.new('RGB', (64, 64), color=(208, 188, 255))
        else:
            self.icon_image = Image.new('RGB', (64, 64), color=(208, 188, 255))

        self.is_paused = False
        self.current_title = "Bushtwo BGS"
        self.icon = None
        self._thread = None

    def start(self):
        """Starts the system tray icon in a dedicated daemon thread."""
        self._thread = threading.Thread(target=self._run_icon, daemon=True)
        self._thread.start()

    def _get_menu(self):
        pause_label = "Resume Slideshow" if self.is_paused else "Pause Slideshow"
        hbmp_pause_or_play = self.hbmp_play if self.is_paused else self.hbmp_pause

        m_title = item(self.current_title, lambda: None, enabled=False)

        m_next = item("Next / Shuffle", lambda icon, item: self.on_next())
        m_next._hbmp = self.hbmp_shuffle

        m_prev = item("Previous Wallpaper", lambda icon, item: self.on_prev())
        m_prev._hbmp = self.hbmp_prev

        m_pause = item(pause_label, lambda icon, item: self.on_toggle_pause())
        m_pause._hbmp = hbmp_pause_or_play

        m_show = item("Open Bushtwo BGS", lambda icon, item: self.on_show(), default=True)
        m_show._hbmp = self.hbmp_desktop

        m_exit = item("Exit", lambda icon, item: self.on_exit())
        m_exit._hbmp = self.hbmp_exit

        return pystray.Menu(
            m_title,
            pystray.Menu.SEPARATOR,
            m_next,
            m_prev,
            m_pause,
            pystray.Menu.SEPARATOR,
            m_show,
            m_exit
        )

    def _run_icon(self):
        try:
            self.icon = pystray.Icon(
                "bushtwo_bgs",
                self.icon_image,
                self.current_title,
                menu=self._get_menu()
            )
            self.icon.run()
        except Exception as e:
            print(f"Tray icon error: {e}")

    def update_status(self, wallpaper_name: str, is_paused: bool):
        """Updates the tray tooltip and menu to reflect pause state and active wallpaper."""
        self.is_paused = is_paused
        short_name = os.path.basename(wallpaper_name) if wallpaper_name else "No Wallpaper"
        self.current_title = f"{'⏸ (Paused) ' if is_paused else ''}{short_name}"

        if self.icon:
            try:
                self.icon.title = f"Bushtwo BGS - {short_name}"
                self.icon.menu = self._get_menu()
                self.icon.update_menu()
            except Exception:
                pass

    def stop(self):
        """Stops the system tray icon cleanly."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
