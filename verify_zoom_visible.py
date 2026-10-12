import ctypes,time,tkinter as tk
from pathlib import Path
from PIL import Image,ImageGrab
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
    renderer=e._zoom_renderer
    print('Native surface:',renderer.width,renderer.height)
    timings=[]
    for _ in range(20):
        began=time.monotonic();renderer.render(1.05);timings.append(time.monotonic()-began)
    print('Render cost average/max ms:',round(sum(timings)/len(timings)*1000,2),round(max(timings)*1000,2))
    colors=[]
    for phase in (0,5):
        e._freeze_zoom();e._zoom_started=time.monotonic()-phase;e._zoom_tick()
        for _ in range(4):e.root.update();time.sleep(.02)
        x,y=renderer.width//4,renderer.height//2
        actual=ImageGrab.grab(bbox=(x,y,x+1,y+1)).getpixel((0,0))
        g=renderer.g
        g.GetPixel.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int];g.GetPixel.restype=ctypes.c_ulong
        pixel=g.GetPixel(renderer.buffers[1][0],x,y)
        expected=(pixel&255,(pixel>>8)&255,(pixel>>16)&255)
        assert all(abs(a-b)<=2 for a,b in zip(actual,expected)),(actual,expected)
        colors.append(actual)
    assert colors[0]!=colors[1],'Zoom did not change the visible desktop'
    print('Visible zoom colors:',colors)
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
    print('Native zoom, pause/resume, outgoing fade retention and disabling passed')
finally:
    e._cancel_fade();e.stop_zoom();e.root.destroy();p.unlink(missing_ok=True)
