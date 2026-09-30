import sys
import os
import ctypes

# 1. Set Windows AppUserModelID before Tkinter initialization
# This ensures Windows Taskbar groups under Bushtwo BGS and uses our custom icon instead of the Python snake
if sys.platform == 'win32':
    try:
        app_user_model_id = 'bushtwo.bgs.wallpaperswitcher.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_user_model_id)
    except Exception as e:
        print(f"Warning: Could not set AppUserModelID: {e}")

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import tkinter as tk
from config_manager import ConfigManager
from wallpaper_engine import get_wallpaper_engine
from playlist_manager import PlaylistManager
from tray_manager import TrayManager
from ui import WallpaperSwitcherUI


def main():
    start_minimized = "--minimized" in sys.argv or "--startup" in sys.argv

    config_mgr = ConfigManager()
    engine = get_wallpaper_engine()

    folders = config_mgr.get("folders", [])
    include_subfolders = config_mgr.get("include_subfolders", True)
    history = config_mgr.get("history", [])

    playlist_mgr = PlaylistManager(
        folders=folders,
        include_subfolders=include_subfolders,
        history=history
    )

    root = tk.Tk()

    # Load custom icons immediately for taskbar & titlebar
    app_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    p16 = os.path.join(app_dir, "Bushtwo BGS 16 x16 pixels.png")
    p32 = os.path.join(app_dir, "Bushtwo BGS 32x32 pixels.png")
    p64 = os.path.join(app_dir, "Bushtwo BGS 64x64 pixels.png")
    ico_path = os.path.join(app_dir, "bushtwo_bgs.ico")

    try:
        if os.path.exists(p64) and os.path.exists(p32) and os.path.exists(p16):
            i16 = tk.PhotoImage(file=p16)
            i32 = tk.PhotoImage(file=p32)
            i64 = tk.PhotoImage(file=p64)
            root.iconphoto(True, i64, i32, i16)
        if os.path.exists(ico_path):
            root.iconbitmap(ico_path)
    except Exception as e:
        print(f"Icon setup warning: {e}")

    ui_holder = [None]

    def tray_show():
        if ui_holder[0]:
            root.after(0, ui_holder[0].show_window)

    def tray_next():
        if ui_holder[0]:
            root.after(0, ui_holder[0].action_next)

    def tray_prev():
        if ui_holder[0]:
            root.after(0, ui_holder[0].action_previous)

    def tray_pause():
        if ui_holder[0]:
            root.after(0, ui_holder[0].action_toggle_pause)

    def tray_exit():
        if ui_holder[0]:
            root.after(0, ui_holder[0].exit_app)
        else:
            root.after(0, root.destroy)

    tray_mgr = TrayManager(
        on_show=tray_show,
        on_next=tray_next,
        on_prev=tray_prev,
        on_toggle_pause=tray_pause,
        on_exit=tray_exit
    )
    tray_mgr.start()

    app_ui = WallpaperSwitcherUI(
        root=root,
        config_mgr=config_mgr,
        wallpaper_engine=engine,
        playlist_mgr=playlist_mgr,
        tray_mgr=tray_mgr
    )
    ui_holder[0] = app_ui

    if start_minimized or config_mgr.get("start_minimized", False):
        root.withdraw()

    try:
        root.mainloop()
    finally:
        tray_mgr.stop()


if __name__ == "__main__":
    main()
