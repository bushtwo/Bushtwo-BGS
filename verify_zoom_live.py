import ctypes,time,tkinter as tk
from pathlib import Path
from PIL import Image
from wallpaper_engine import WindowsWallpaperEngine
from zoom_effect import zoom_scale,zoom_frame
ctypes.windll.shcore.SetProcessDpiAwareness(1)
e=WindowsWallpaperEngine();e.root=tk.Tk();e.root.withdraw()
e._commit_fade=lambda:setattr(e,'_fade_target',None)
e._zoom_enabled=True;e._zoom_interval=15;e._zoom_paused=False
p=Path(e.cache_dir)/'zoom_check.bmp'
im=Image.new('RGB',(320,180))
for x in range(320):
    for y in range(180):im.putpixel((x,y),(x%256,y%256,(x+y)%256))
im.save(p)
try:
    e.fade_transition('',str(p),'Fill',.001)
    until=time.monotonic()+1.5
    while time.monotonic()<until:e.root.update()
    assert e._zoom_overlay is not None and e._active_overlay is None
    for phase in (2.5,5,7.5,10,12.5):
        e._freeze_zoom();e._zoom_started=time.monotonic()-phase;e._zoom_tick()
        assert e._zoom_renderer.draw_count > 0
        print('Live zoom phase:',phase,'scale:',round(zoom_scale(phase,15),3))
    e.configure_zoom(True,'Fill','interval',15,True,str(p))
    assert e._zoom_after is None
    frozen=e._zoom_elapsed
    e.root.update();assert e._zoom_elapsed==frozen
    e.configure_zoom(True,'Fill','interval',15,False,str(p))
    assert e._zoom_after is not None
    previous=e._zoom_overlay
    e.fade_transition(str(p),str(p),'Fill',.1)
    assert previous.winfo_exists(),'Outgoing zoom was removed before the fade'
    until=time.monotonic()+1.4
    while time.monotonic()<until:e.root.update()
    assert e._zoom_overlay is not None and e._zoom_overlay!=previous
    e.configure_zoom(True,'Fit','interval',15,False,str(p))
    assert e._zoom_overlay is None
    user=ctypes.windll.user32
    user.GetGuiResources.argtypes=[ctypes.c_void_p,ctypes.c_uint]
    process=ctypes.c_void_p(-1)
    before=user.GetGuiResources(process,0)
    e._zoom_enabled=True
    for _ in range(5):
        e.fade_transition('',str(p),'Fill',.001)
        until=time.monotonic()+.08
        while time.monotonic()<until:e.root.update()
        e._cancel_fade();e.stop_zoom();e.root.update()
    after=user.GetGuiResources(process,0)
    assert after<=before+2,(before,after)
    print('Repeated toggle cleanup GDI handles:',before,after)
    print('Native zoom, pause/resume, outgoing fade retention and disabling passed')
finally:
    e._cancel_fade();e.stop_zoom();e.root.destroy();p.unlink(missing_ok=True)
