import tkinter as tk
from unittest.mock import Mock
from ui import WallpaperSwitcherUI
root=tk.Tk();root.attributes('-alpha',0)
c=Mock();c.get.side_effect=lambda key,default=None:{'interval_seconds':5}.get(key,default)
e=Mock();e.is_startup_enabled.return_value=False;e.get_current_system_wallpaper.return_value='';e.get_display_info.return_value={'formatted':'Test display'}
p=Mock();p.folders=[];p.get_folder_counts.return_value={};p.get_total_count.return_value=0;p.has_images.return_value=False
try:
    ui=WallpaperSwitcherUI(root,c,e,p,Mock());root.update()
    controls=[ui.cb_startup,ui.cb_tray,ui.cb_zoom]
    assert all(w.master==ui.card_options.inner for w in controls)
    for a,b in zip(controls,controls[1:]):
        gap=b.winfo_y()-a.winfo_y()-a.winfo_height()
        assert gap==16,gap
    assert ui.cb_zoom.text_label.cget('font')==ui.cb_startup.text_label.cget('font')
    assert ui.cb_zoom.text_label.cget('fg')==ui.cb_startup.text_label.cget('fg')
    assert ui.cb_zoom.winfo_reqwidth()<=ui.card_options.inner.winfo_width()
    for radio in ui.zoom_radios:
        assert radio.checked_icon is ui.icons['radio_checked']
        assert radio.unchecked_icon is ui.icons['radio_unchecked']
    ui.zoom_effect.set(True);ui._sync_zoom()
    ui.zoom_radios[0]._toggle()
    assert ui.zoom_style.get()=='pulse'
    ui.zoom_radios[1]._toggle()
    assert ui.zoom_style.get()=='smooth'
    print('Options share the card, with 16px gaps and matching font/colors')
finally:root.destroy()
