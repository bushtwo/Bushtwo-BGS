import os
import sys
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

# Registry values for Windows wallpaper styles
# (WallpaperStyle, TileWallpaper)
SCALING_STYLES = {
    'Fill': ('10', '0'),     # Crop to fill screen
    'Fit': ('6', '0'),       # Fit screen with letterbox
    'Stretch': ('2', '0'),   # Stretch image to fill screen
    'Tile': ('0', '1'),      # Repeat image in tiles
    'Center': ('0', '0'),    # Center image without scaling
    'Span': ('22', '0')      # Span across multiple monitors
}


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
    def is_startup_enabled(self) -> bool:
        """Checks if app is set to run at startup."""
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

    def get_display_info(self) -> dict:
        """Gets primary display resolution, refresh rate, and color depth."""
        user32 = ctypes.windll.user32
        # SM_CXSCREEN = 0, SM_CYSCREEN = 1
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
                ('dmPosition_x', ctypes.c_long),
                ('dmPosition_y', ctypes.c_long),
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
            # ENUM_CURRENT_SETTINGS = -1
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

            # SetPosition
            DWPO_MAP = {'Center': 0, 'Tile': 1, 'Stretch': 2, 'Fit': 3, 'Fill': 4, 'Span': 5}
            pos_val = DWPO_MAP.get(scaling_mode, 4)
            SetPosition = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int)(vtable[10])
            SetPosition(pWallpaper, pos_val)

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
        """
        Sets desktop wallpaper with smooth cross-fade animation.
        Converts format to universal BMP cache if necessary.
        """
        if not image_path or not os.path.exists(image_path):
            return False

        # Apply registry scaling style for system persistence
        self._apply_scaling_registry(scaling_mode)

        ext = os.path.splitext(image_path)[1].lower()
        target_path = image_path

        # If it's a format like .webp or .jfif, convert to cached BMP file
        needs_conversion = ext in {'.webp', '.jfif', '.tif', '.tiff'}
        if needs_conversion:
            try:
                with Image.open(image_path) as img:
                    if img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')
                    img.save(self.cached_wallpaper_path, 'BMP')
                    target_path = self.cached_wallpaper_path
            except Exception as e:
                print(f"Error converting image {image_path}: {e}")
                target_path = image_path

        # Primary: Modern COM IDesktopWallpaper with DWM smooth cross-fade
        if self._set_wallpaper_com(target_path, scaling_mode):
            return True

        # Fallback: legacy SystemParametersInfoW
        try:
            result = ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER,
                0,
                target_path,
                SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
            )
            return bool(result)
        except Exception as e:
            print(f"Error setting wallpaper via SystemParametersInfoW: {e}")
            return False

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
        """Adds or removes the startup entry in HKCU Run registry."""
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
        if getattr(sys, 'frozen', False):
            target = os.path.abspath(sys.executable)
            cmd = f'"{target}" --minimized'
        else:
            app_main = os.path.abspath(os.path.join(self.app_dir, 'main.py'))
            python_dir = os.path.dirname(sys.executable)
            pythonw_path = os.path.join(python_dir, 'pythonw.exe')
            if not os.path.exists(pythonw_path):
                pythonw_path = sys.executable
            cmd = f'"{pythonw_path}" "{app_main}" --minimized'

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE
            )
            # Remove legacy key if still present
            try:
                winreg.DeleteValue(key, 'WallpaperSwitcher')
            except FileNotFoundError:
                pass

            if enable:
                winreg.SetValueEx(key, 'BushtwoBGS', 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, 'BushtwoBGS')
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Error updating startup registry: {e}")
            return False


class LinuxWallpaperEngine(WallpaperEngineBase):
    """
    Placeholder/skeleton for Linux wallpaper switching (GNOME, KDE, XFCE, feh, etc.).
    Ready for future expansion as requested by user.
    """

    def get_display_info(self) -> dict:
        return {'width': 1920, 'height': 1080, 'refresh_rate': 60, 'bpp': 24, 'formatted': '1920 × 1080 @ 60Hz'}

    def get_current_system_wallpaper(self) -> str:
        return ""

    def set_wallpaper(self, image_path: str, scaling_mode: str = 'Fill') -> bool:
        # To be implemented for GNOME/KDE/feh
        return False

    def is_startup_enabled(self) -> bool:
        # Check ~/.config/autostart/wallpaper-switcher.desktop
        return False

    def set_startup(self, enable: bool) -> bool:
        return False


def get_wallpaper_engine() -> WallpaperEngineBase:
    """Factory function returning the appropriate engine for the current OS."""
    if sys.platform == 'win32':
        return WindowsWallpaperEngine()
    else:
        return LinuxWallpaperEngine()
