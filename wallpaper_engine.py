import os
import sys
import time
import math
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
        pWallpaper = ctypes.c_void_p()
        com_initialized = False
        try:
            hr_init = ctypes.windll.ole32.CoInitialize(None)
            com_initialized = hr_init in (0, 1)

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

            # Read the actual Windows position; another app may have changed it.
            DWPO_MAP = {'Center': 0, 'Tile': 1, 'Stretch': 2, 'Fit': 3, 'Fill': 4, 'Span': 5}
            pos_val = DWPO_MAP.get(scaling_mode, 4)
            current_pos = ctypes.c_int()
            GetPosition = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))(vtable[11])
            hr_pos = GetPosition(pWallpaper, ctypes.byref(current_pos))
            if hr_pos < 0 or current_pos.value != pos_val:
                SetPosition = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int)(vtable[10])
                if SetPosition(pWallpaper, pos_val) < 0:
                    return False

            # SetWallpaper(this, monitorID=None, path) -> triggers smooth Windows DWM crossfade
            abs_path = os.path.abspath(image_path)
            SetWallpaper = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p)(vtable[3])
            hr_set = SetWallpaper(pWallpaper, None, abs_path)

            return hr_set == 0
        except Exception as e:
            print(f"IDesktopWallpaper COM transition notice: {e}")
            return False
        finally:
            if pWallpaper.value:
                vtable = ctypes.cast(pWallpaper, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
                Release(pWallpaper)
            if com_initialized:
                ctypes.windll.ole32.CoUninitialize()

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
        
        if self._set_wallpaper_com(target_path, scaling_mode): return True
        self._apply_scaling_registry(scaling_mode)
        try:
            return bool(ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, target_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE))
        except Exception: return False

    def _wallpaper_layer(self):
        """Ask Explorer for its wallpaper-only WorkerW, below the icon surface."""
        u = ctypes.windll.user32
        u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        u.FindWindowW.restype = wintypes.HWND
        u.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
        u.FindWindowExW.restype = wintypes.HWND
        progman = u.FindWindowW('Progman', None)
        u.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
        result = ctypes.c_size_t()
        u.SendMessageTimeoutW(progman, 0x052c, 0, 0, 2, 1000, ctypes.byref(result))
        layers = []
        enum_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @enum_type
        def visit(hwnd, _):
            if u.FindWindowExW(hwnd, None, 'SHELLDLL_DefView', None):
                worker = u.FindWindowExW(None, hwnd, 'WorkerW', None)
                if worker:
                    layers.append(worker)
            return True

        u.EnumWindows.argtypes = [enum_type, wintypes.LPARAM]
        u.EnumWindows(visit, 0)
        return layers[0] if layers else u.FindWindowExW(progman, None, 'WorkerW', None)

    def fade_transition(self, old_path: str, new_path: str, scaling_mode: str = 'Fill', duration: float = 0.5, callback=None):
        """Composite the new image in Explorer's wallpaper layer over 500 ms."""
        if not new_path or not os.path.exists(new_path):
            return
        self._cancel_fade()
        top = None
        try:
            if not self.root or duration <= 0:
                self.set_wallpaper(new_path, scaling_mode)
                if callback:
                    callback()
                return
            import tkinter as tk
            from PIL import ImageTk
            u = ctypes.windll.user32
            parent = self._wallpaper_layer()
            if not parent:
                raise RuntimeError('Explorer wallpaper layer unavailable')
            disp = self.get_display_info()
            sw, sh = disp['width'], disp['height']
            x, y = 0, 0
            if scaling_mode == 'Span':
                sw, sh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
                x, y = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
            origin = wintypes.POINT(x, y)
            u.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
            u.ScreenToClient(parent, ctypes.byref(origin))
            with Image.open(new_path) as im:
                rendered = _render_scaled_image(im, sw, sh, scaling_mode)
            self._fade_serial = getattr(self, '_fade_serial', 0) + 1
            path = os.path.join(self.cache_dir, f'fade_{os.getpid()}_{self._fade_serial}.bmp')
            rendered.save(path, 'BMP')
            top = tk.Toplevel(self.root)
            top.withdraw()
            top.overrideredirect(True)
            # Tk restores its own alpha when mapping the wrapper. Set Tk's
            # initial opacity too, or deiconify briefly reveals the next image.
            top.attributes('-alpha', 0.0)
            top.geometry(f'{sw}x{sh}+0+0')
            photo = ImageTk.PhotoImage(rendered)
            label = tk.Label(top, image=photo, bd=0, highlightthickness=0)
            label.photo = photo
            label.pack(fill='both', expand=True)
            top.update_idletasks()
            hwnd = int(top.wm_frame(), 16)
            u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
            u.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
            u.SetWindowLongW(hwnd, -16, (u.GetWindowLongW(hwnd, -16) & ~0x80000000) | 0x40000000)
            u.SetWindowLongW(hwnd, -20, u.GetWindowLongW(hwnd, -20) | 0x80000 | 0x20 | 0x08000000)
            set_parent = ctypes.WinDLL('user32', use_last_error=True).SetParent
            set_parent.argtypes = [wintypes.HWND, wintypes.HWND]
            set_parent.restype = wintypes.HWND
            ctypes.set_last_error(0)
            if not set_parent(hwnd, parent) and ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())
            u.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.BYTE, wintypes.DWORD]
            u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            if not u.SetLayeredWindowAttributes(hwnd, 0, 0, 2):
                raise RuntimeError('Wallpaper opacity unavailable')
            top.deiconify()
            if not u.SetWindowPos(hwnd, 1, origin.x, origin.y, sw, sh, 0x10 | 0x40 | 0x20):
                raise RuntimeError('Wallpaper layer placement failed')
            self._active_overlay = top
            self._fade_target = (path, scaling_mode)
            started = time.monotonic()

            def animate():
                self._fade_anim_id = None
                progress = min(1.0, (time.monotonic() - started) / duration)
                alpha = round(255 * (1.0 - math.cos(math.pi * progress)) / 2.0)
                # Keep Tk's stored alpha in sync with the native window so a
                # shell settings refresh cannot restore an obsolete opacity.
                top.attributes('-alpha', alpha / 255.0)
                if progress < 1.0:
                    self._fade_anim_id = self.root.after(16, animate)
                else:
                    # Commit the identical pre-scaled bitmap under the opaque fade.
                    # This avoids any change of crop or scaling at the handoff.
                    self._commit_fade()
                    self._fade_anim_id = self.root.after(1000, finish)

            def finish():
                self._cancel_fade()
                if callback:
                    callback()

            self._fade_anim_id = self.root.after(16, animate)
        except Exception as e:
            with open(os.path.join(self.cache_dir, 'fade_error.log'), 'a', encoding='utf-8') as log:
                log.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")}: {e}\n')
            self._cancel_fade()
            if top is not None and top.winfo_exists():
                top.destroy()
            self.set_wallpaper(new_path, scaling_mode)
            if callback:
                callback()

    def _commit_fade(self):
        target = getattr(self, '_fade_target', None)
        if target:
            path, mode = target
            # COM SetWallpaper starts another Windows crossfade. Commit via SPI
            # while the new image is opaque, without broadcasting a shell redraw.
            self._apply_scaling_registry(mode)
            committed = bool(ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER, 0, path, SPIF_UPDATEINIFILE
            ))
            if committed:
                previous = getattr(self, '_fade_frame_path', None)
                self._fade_frame_path = path
                if previous and previous != path:
                    try:
                        os.remove(previous)
                    except OSError:
                        pass
            self._fade_target = None

    def _cancel_fade(self):
        anim = getattr(self, '_fade_anim_id', None)
        if anim is not None and self.root:
            self.root.after_cancel(anim)
        self._fade_anim_id = None
        self._commit_fade()
        top = getattr(self, '_active_overlay', None)
        if top is not None and top.winfo_exists():
            top.destroy()
        self._active_overlay = None

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
