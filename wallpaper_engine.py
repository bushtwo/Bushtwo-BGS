import os
import sys
import ctypes
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

    def set_wallpaper(self, image_path: str, scaling_mode: str = 'Fill') -> bool:
        """
        Sets desktop wallpaper. Converts format to universal BMP cache if necessary
        or ensures Windows can load it reliably.
        """
        if not image_path or not os.path.exists(image_path):
            return False

        # First apply registry scaling style
        self._apply_scaling_registry(scaling_mode)

        ext = os.path.splitext(image_path)[1].lower()
        target_path = image_path

        # If it's a format like .webp or .jfif, or if we want 100% crash-proof Windows support,
        # convert it into the cached BMP/PNG file
        needs_conversion = ext in {'.webp', '.jfif', '.tif', '.tiff'}
        if needs_conversion:
            try:
                with Image.open(image_path) as img:
                    # Convert to RGB if RGBA or P
                    if img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')
                    img.save(self.cached_wallpaper_path, 'BMP')
                    target_path = self.cached_wallpaper_path
            except Exception as e:
                print(f"Error converting image {image_path}: {e}")
                target_path = image_path

        # Call Windows API
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
        """Checks if startup entry exists in HKCU Run registry."""
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
                return bool(val)
            except FileNotFoundError:
                try:
                    val, _ = winreg.QueryValueEx(key, 'WallpaperSwitcher')
                    winreg.CloseKey(key)
                    return bool(val)
                except FileNotFoundError:
                    winreg.CloseKey(key)
                    return False
        except Exception:
            return False

    def set_startup(self, enable: bool) -> bool:
        """Adds or removes the startup entry in HKCU Run registry."""
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
        if getattr(sys, 'frozen', False):
            cmd = f'"{sys.executable}" --minimized'
        else:
            app_main = os.path.join(self.app_dir, 'main.py')
            python_dir = os.path.dirname(sys.executable)
            pythonw_path = os.path.join(python_dir, 'pythonw.exe')
            if not os.path.exists(pythonw_path):
                pythonw_path = sys.executable
            cmd = f'"{pythonw_path}" "{app_main}" --minimized'

        try:
            if enable:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    key_path,
                    0,
                    winreg.KEY_SET_VALUE
                )
                winreg.SetValueEx(key, 'BushtwoBGS', 0, winreg.REG_SZ, cmd)
                winreg.CloseKey(key)
                return True
            else:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    key_path,
                    0,
                    winreg.KEY_SET_VALUE
                )
                for k in ['BushtwoBGS', 'WallpaperSwitcher']:
                    try:
                        winreg.DeleteValue(key, k)
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
