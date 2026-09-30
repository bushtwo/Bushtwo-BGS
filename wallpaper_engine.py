import os
import sys
import time
import math
import threading
import ctypes
from ctypes import wintypes
import winreg
from abc import ABC, abstractmethod
from PIL import Image

SPI_SETDESKWALLPAPER = 20
SPI_GETDESKWALLPAPER = 0x0073
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.jfif', '.tiff', '.tif'}

SCALING_STYLES = {
    'Fill': ('10', '0'),     # Crop to fill screen
    'Fit': ('6', '0'),       # Fit screen with letterbox
    'Stretch': ('2', '0'),   # Stretch image to fill screen
    'Tile': ('0', '1'),      # Repeat image in tiles
    'Center': ('0', '0'),    # Center image without scaling
    'Span': ('22', '0')      # Span across multiple monitors
}


def _render_scaled_image(img: Image.Image, screen_w: int, screen_h: int, mode: str) -> Image.Image:
    """Helper to render an image properly fitted/cropped for display dimensions."""
    from PIL import ImageOps
    
    # Respect EXIF orientation before any size calculations
    img = ImageOps.exif_transpose(img)
    
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    iw, ih = img.size

    if mode == 'Stretch':
        return img.resize((screen_w, screen_h), Image.Resampling.BILINEAR)

    elif mode == 'Fit':
        canvas = Image.new('RGB', (screen_w, screen_h), (0, 0, 0))
        ratio = min(screen_w / iw, screen_h / ih)
        new_w = max(1, int(iw * ratio))
        new_h = max(1, int(ih * ratio))
        resized = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
        offset_x = (screen_w - new_w) // 2
        offset_y = (screen_h - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y))
        return canvas

    elif mode == 'Center':
        canvas = Image.new('RGB', (screen_w, screen_h), (0, 0, 0))
        offset_x = (screen_w - iw) // 2
        offset_y = (screen_h - ih) // 2
        if iw > screen_w or ih > screen_h:
            left = max(0, -offset_x)
            top = max(0, -offset_y)
            cropped = img.crop((left, top, left + min(iw, screen_w), top + min(ih, screen_h)))
            canvas.paste(cropped, (max(0, offset_x), max(0, offset_y)))
        else:
            canvas.paste(img, (offset_x, offset_y))
        return canvas

    elif mode == 'Tile':
        canvas = Image.new('RGB', (screen_w, screen_h), (0, 0, 0))
        for x in range(0, screen_w, iw):
            for y in range(0, screen_h, ih):
                canvas.paste(img, (x, y))
        return canvas

    else:  # 'Fill' or 'Span'
        # ImageOps.fit precisely crops the original image before resizing, 
        # matching how Windows DWM texture samplers map the rects,
        # completely preventing subpixel vertical rounding shifts.
        return ImageOps.fit(img, (screen_w, screen_h), method=Image.Resampling.BILINEAR, centering=(0.5, 0.5))


class WallpaperEngineBase(ABC):
    """Abstract base class for wallpaper engines to support Windows now and Linux later."""

    @abstractmethod
    def get_display_info(self) -> dict:
        """Returns monitor information dictionary."""
        pass

    @abstractmethod
    def get_current_system_wallpaper(self) -> str:
        """Returns path of the current system wallpaper."""
        pass

    @abstractmethod
    def set_wallpaper(self, image_path: str, scaling_mode: str = 'Fill') -> bool:
        """Sets the system wallpaper with given scaling mode."""
        pass

    @abstractmethod
    def fade_transition(self, old_path: str, new_path: str, scaling_mode: str = 'Fill', duration: float = 0.5, callback=None):
        """Cross-fade transition from old_path to new_path over given duration."""
        pass

    @abstractmethod
    def is_startup_enabled(self) -> bool:
        """Checks if app is registered to run on startup."""
        pass

    @abstractmethod
    def set_startup(self, enable: bool) -> bool:
        """Enables or disables running at startup."""
        pass


class WindowsWallpaperEngine(WallpaperEngineBase):
    """Windows implementation of wallpaper switching, display detection, and startup."""

    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_dir = os.path.join(self.app_dir, '.cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cached_wallpaper_path = os.path.join(self.cache_dir, 'active_wallpaper.bmp')
        self.root = None
        self._active_overlay = None
        self._fade_anim_id = None
        self._fade_cleanup_id = None

    def get_display_info(self) -> dict:
        """Gets primary display resolution, refresh rate, and color depth."""
        user32 = ctypes.windll.user32
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
        freq = 60
        bpp = 32

        class DEVMODE(ctypes.Structure):
            _fields_ = [
                ('dmDeviceName', ctypes.c_wchar * 32),
                ('dmSpecVersion', ctypes.c_ushort),
                ('dmDriverVersion', ctypes.c_ushort),
                ('dmSize', ctypes.c_ushort),
                ('dmDriverExtra', ctypes.c_ushort),
                ('dmFields', ctypes.c_ulong),
                ('dmPositionX', ctypes.c_long),
                ('dmPositionY', ctypes.c_long),
                ('dmDisplayOrientation', ctypes.c_ulong),
                ('dmDisplayFixedOutput', ctypes.c_ulong),
                ('dmColor', ctypes.c_short),
                ('dmDuplex', ctypes.c_short),
                ('dmYResolution', ctypes.c_short),
                ('dmTTOption', ctypes.c_short),
                ('dmCollate', ctypes.c_short),
                ('dmFormName', ctypes.c_wchar * 32),
                ('dmLogPixels', ctypes.c_ushort),
                ('dmBitsPerPel', ctypes.c_ulong),
                ('dmPelsWidth', ctypes.c_ulong),
                ('dmPelsHeight', ctypes.c_ulong),
                ('dmDisplayFlags', ctypes.c_ulong),
                ('dmDisplayFrequency', ctypes.c_ulong),
            ]

        try:
            dm = DEVMODE()
            dm.dmSize = ctypes.sizeof(DEVMODE)
            if user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):
                if dm.dmPelsWidth and dm.dmPelsHeight:
                    width = dm.dmPelsWidth
                    height = dm.dmPelsHeight
                if dm.dmDisplayFrequency:
                    freq = dm.dmDisplayFrequency
                if dm.dmBitsPerPel:
                    bpp = dm.dmBitsPerPel
        except Exception:
            pass

        formatted = f"{width} × {height} @ {freq}Hz ({bpp}-bit color)"
        return {
            'width': width,
            'height': height,
            'refresh_rate': freq,
            'bpp': bpp,
            'formatted': formatted
        }

    def get_current_system_wallpaper(self) -> str:
        """Retrieves the file path of the currently active desktop wallpaper."""
        try:
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, len(buf), buf, 0)
            path = buf.value
            if path and os.path.exists(path):
                return path
        except Exception:
            pass
        return ""

    def _apply_scaling_registry(self, scaling_mode: str):
        """Updates Windows Registry with the chosen wallpaper scaling style."""
        style_vals = SCALING_STYLES.get(scaling_mode, SCALING_STYLES['Fill'])
        wp_style, tile = style_vals

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Control Panel\Desktop',
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, 'WallpaperStyle', 0, winreg.REG_SZ, wp_style)
            winreg.SetValueEx(key, 'TileWallpaper', 0, winreg.REG_SZ, tile)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Warning: Failed to set wallpaper style in registry: {e}")

    def _set_wallpaper_com(self, image_path: str, scaling_mode: str = 'Fill') -> bool:
        """Sets wallpaper via modern IDesktopWallpaper COM interface to trigger smooth DWM cross-fade transition."""
        try:
            ctypes.windll.ole32.CoInitialize(None)

            class GUID(ctypes.Structure):
                _fields_ = [
                    ('Data1', wintypes.DWORD),
                    ('Data2', wintypes.WORD),
                    ('Data3', wintypes.WORD),
                    ('Data4', ctypes.c_byte * 8)
                ]

            clsid = GUID()
            iid = GUID()
            ctypes.windll.ole32.CLSIDFromString('{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}', ctypes.byref(clsid))
            ctypes.windll.ole32.CLSIDFromString('{B92B56A9-8B55-4E14-9A89-0199BBB6F93B}', ctypes.byref(iid))

            pWallpaper = ctypes.c_void_p()
            hr = ctypes.windll.ole32.CoCreateInstance(
                ctypes.byref(clsid),
                None,
                23,  # CLSCTX_ALL
                ctypes.byref(iid),
                ctypes.byref(pWallpaper)
            )
            if hr != 0 or not pWallpaper.value:
                return False

            vtable = ctypes.cast(pWallpaper, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents

            # SetPosition (only if changed to avoid unnecessary Explorer reposition/redraw)
            DWPO_MAP = {'Center': 0, 'Tile': 1, 'Stretch': 2, 'Fit': 3, 'Fill': 4, 'Span': 5}
            pos_val = DWPO_MAP.get(scaling_mode, 4)
            if getattr(self, '_last_pos_val', None) != pos_val:
                SetPosition = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int)(vtable[10])
                SetPosition(pWallpaper, pos_val)
                self._last_pos_val = pos_val

            # SetWallpaper(this, monitorID=None, path) -> triggers smooth Windows DWM crossfade
            abs_path = os.path.abspath(image_path)
            SetWallpaper = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p)(vtable[3])
            hr_set = SetWallpaper(pWallpaper, None, abs_path)

            Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
            Release(pWallpaper)

            return hr_set == 0
        except Exception as e:
            print(f"IDesktopWallpaper COM transition notice: {e}")
            return False

    def set_wallpaper(self, image_path: str, scaling_mode: str = 'Fill') -> bool:
        """Sets desktop wallpaper natively (fallback for direct sets without fade)."""
        if not image_path or not os.path.exists(image_path): return False
        ext = os.path.splitext(image_path)[1].lower()
        target_path = image_path
        if ext in {'.webp', '.jfif', '.tif', '.tiff'}:
            try:
                from PIL import ImageOps
                with Image.open(image_path) as img:
                    img = ImageOps.exif_transpose(img)
                    if img.mode not in ('RGB', 'L'): img = img.convert('RGB')
                    img.save(self.cached_wallpaper_path, 'BMP')
                    target_path = self.cached_wallpaper_path
            except Exception: pass
        
        self._apply_scaling_registry(scaling_mode)
        if self._set_wallpaper_com(target_path, scaling_mode): return True
        try:
            return bool(ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, target_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE))
        except Exception: return False

    def fade_transition(self, old_path: str, new_path: str, scaling_mode: str = 'Fill', duration: float = 0.5, callback=None):
        if not new_path or not os.path.exists(new_path): return
        if not old_path or not os.path.exists(old_path) or os.path.abspath(old_path) == os.path.abspath(new_path):
            self.set_wallpaper(new_path, scaling_mode)
            if callback: callback()
            return

        if getattr(self, 'root', None) and self.root.winfo_exists():
            self._fade_overlay_transition(new_path, scaling_mode, duration, callback)
            return

        self.set_wallpaper(new_path, scaling_mode)
        if callback: callback()

    def _fade_overlay_transition(self, new_path: str, scaling_mode: str, duration: float, callback):
        try:
            import tkinter as tk
            from PIL import ImageTk

            if getattr(self, '_fade_anim_id', None):
                try: self.root.after_cancel(self._fade_anim_id)
                except Exception: pass
                self._fade_anim_id = None

            if getattr(self, '_fade_cleanup_id', None):
                try: self.root.after_cancel(self._fade_cleanup_id)
                except Exception: pass
                self._fade_cleanup_id = None

            if getattr(self, '_active_overlay', None) and self._active_overlay.winfo_exists():
                try: self._active_overlay.destroy()
                except Exception: pass
                self._active_overlay = None

            disp = self.get_display_info()
            sw = disp.get('width', 1920)
            sh = disp.get('height', 1080)

            # Pre-render perfectly cropped image to screen dimensions
            with Image.open(new_path) as im:
                img_rendered = _render_scaled_image(im, sw, sh, scaling_mode)
            img_rendered.save(self.cached_wallpaper_path, 'BMP')

            # Create invisible overlay window
            top = tk.Toplevel(self.root)
            top.withdraw()
            top.overrideredirect(True)
            top.attributes('-alpha', 0.0)
            top.geometry(f'{sw}x{sh}+0+0')
            self._active_overlay = top

            photo = ImageTk.PhotoImage(img_rendered)
            lbl = tk.Label(top, image=photo, bd=0, highlightthickness=0, bg='black')
            lbl.photo = photo
            lbl.pack(fill='both', expand=True)
            top.update_idletasks()

            HWND_BOTTOM = 1
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000

            hwnd = int(top.wm_frame(), 16) if hasattr(top, 'wm_frame') else (ctypes.windll.user32.GetParent(top.winfo_id()) or top.winfo_id())
            old_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, old_style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, sw, sh, SWP_NOACTIVATE)

            top.deiconify()
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, sw, sh, SWP_NOACTIVATE | SWP_SHOWWINDOW)

            step = [0]
            total_steps = max(10, int(duration * 50))
            interval_ms = max(10, int((duration * 1000) / total_steps))
            wp_set_triggered = [False]
            
            def _set_instant_wallpaper():
                # INSTANT BACKGROUND SWAP: bypasses COM slide animations by using legacy SPI!
                self._apply_scaling_registry('Center')
                try:
                    ctypes.windll.user32.SystemParametersInfoW(
                        SPI_SETDESKWALLPAPER, 0, self.cached_wallpaper_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
                    )
                except Exception: pass

            def _step_animation():
                if not top.winfo_exists(): return
                step[0] += 1
                t_norm = step[0] / float(total_steps)
                alpha = 0.5 * (1.0 - math.cos(math.pi * t_norm))
                if alpha > 1.0: alpha = 1.0

                try: top.attributes('-alpha', alpha)
                except Exception: pass

                if step[0] >= int(total_steps * 0.8) and not wp_set_triggered[0]:
                    wp_set_triggered[0] = True
                    threading.Thread(target=_set_instant_wallpaper, daemon=True).start()

                if step[0] < total_steps:
                    self._fade_anim_id = self.root.after(interval_ms, _step_animation)
                else:
                    self._fade_anim_id = None
                    try: top.attributes('-alpha', 1.0)
                    except Exception: pass

                    if not wp_set_triggered[0]:
                        wp_set_triggered[0] = True
                        threading.Thread(target=_set_instant_wallpaper, daemon=True).start()

                    def _destroy_overlay():
                        try: top.destroy()
                        except Exception: pass
                        if getattr(self, '_active_overlay', None) == top: self._active_overlay = None
                        self._fade_cleanup_id = None
                        if callback: callback()

                    self._fade_cleanup_id = self.root.after(1200, _destroy_overlay)

            self._fade_anim_id = self.root.after(interval_ms, _step_animation)

        except Exception as e:
            print(f"Overlay fade notice: {e}")
            self.set_wallpaper(new_path, scaling_mode)
            if callback: callback()

    def is_startup_enabled(self) -> bool:
        """Checks if startup entry exists and points to a valid file in HKCU Run registry."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run',
                0,
                winreg.KEY_READ
            )
            try:
                val, _ = winreg.QueryValueEx(key, 'BushtwoBGS')
                winreg.CloseKey(key)
                if val:
                    cmd_path = val.split('"')[1] if '"' in val else val.split()[0]
                    return os.path.exists(cmd_path)
                return False
            except FileNotFoundError:
                try:
                    val, _ = winreg.QueryValueEx(key, 'WallpaperSwitcher')
                    winreg.CloseKey(key)
                    if val:
                        cmd_path = val.split('"')[1] if '"' in val else val.split()[0]
                        return os.path.exists(cmd_path)
                    return False
                except FileNotFoundError:
                    winreg.CloseKey(key)
                    return False
        except Exception:
            return False

    def set_startup(self, enable: bool) -> bool:
        """Adds or removes the application from Windows Run startup registry with full executable path."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Run',
                0,
                winreg.KEY_SET_VALUE
            )
            if enable:
                if getattr(sys, 'frozen', False):
                    target_exec = sys.executable
                    reg_val = f'"{target_exec}" --minimized'
                else:
                    py_exec = sys.executable.replace("python.exe", "pythonw.exe")
                    main_py = os.path.abspath(os.path.join(self.app_dir, 'main.py'))
                    reg_val = f'"{py_exec}" "{main_py}" --minimized'

                winreg.SetValueEx(key, 'BushtwoBGS', 0, winreg.REG_SZ, reg_val)
            else:
                for name in ('BushtwoBGS', 'WallpaperSwitcher'):
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Error configuring startup registry: {e}")
            return False


class LinuxWallpaperEngine(WallpaperEngineBase):
    """Placeholder implementation for Linux desktop environments."""

    def get_display_info(self) -> dict:
        return {'width': 1920, 'height': 1080, 'refresh_rate': 60, 'bpp': 24, 'formatted': '1920 × 1080 @ 60Hz'}

    def get_current_system_wallpaper(self) -> str:
        return ""

    def set_wallpaper(self, image_path: str, scaling_mode: str = 'Fill') -> bool:
        return True

    def fade_transition(self, old_path: str, new_path: str, scaling_mode: str = 'Fill', duration: float = 0.5, callback=None):
        self.set_wallpaper(new_path, scaling_mode)
        if callback:
            callback()

    def is_startup_enabled(self) -> bool:
        return False

    def set_startup(self, enable: bool) -> bool:
        return False


def get_wallpaper_engine() -> WallpaperEngineBase:
    """Factory function returning the OS-appropriate wallpaper engine."""
    if sys.platform == 'win32':
        return WindowsWallpaperEngine()
    else:
        return LinuxWallpaperEngine()
