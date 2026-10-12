import ctypes,time,tkinter as tk
from pathlib import Path
from PIL import Image,ImageGrab
from wallpaper_engine import WindowsWallpaperEngine
from zoom_effect import zoom_scale,zoom_frame,pulse_texture
for mode,leg in [('pulse',1),('smooth',5)]:
    assert abs(zoom_scale(0,30,mode)-1)<1e-8
    assert abs(zoom_scale(leg,30,mode)-(1.1 if mode=='pulse' else 1.2))<1e-8
    assert abs(zoom_scale(2*leg,30,mode)-1)<1e-8
ctypes.windll.shcore.SetProcessDpiAwareness(1)
e=WindowsWallpaperEngine();e.root=tk.Tk();e.root.withdraw()
e._commit_fade=lambda:setattr(e,'_fade_target',None)
e._zoom_enabled=True;e._zoom_interval=5;e._zoom_paused=False;e._zoom_effect='smooth'
p=Path(e.cache_dir)/'motion_v2_check.bmp'
im=Image.new('RGB',(320,180))
for x in range(320):
    for y in range(180):im.putpixel((x,y),(round(x*255/319),round(y*255/179),64))
im.save(p)
try:
    e.fade_transition('',str(p),'Fill',.001)
    deadline=time.monotonic()+3
    while e._zoom_overlay is None if hasattr(e,'_zoom_overlay') else True:
        e.root.update()
        assert time.monotonic()<deadline
    s=e._zoom_overlay
    print('Renderer:',s.backend_name,'cadence:',s.fps,'native timeline:',getattr(s,'native_timeline',False))
    cpu=time.process_time();started=time.monotonic();samples=[]
    for target in (.2,1,2.5,4.8,5.1):
        wait=max(0,target-(time.monotonic()-started));time.sleep(wait)
        elapsed=s.elapsed;scale=s.last_scale
        assert abs(scale-zoom_scale(elapsed,5))<.003,(elapsed,scale)
        x,y=s.width//4,s.height//2
        pixel=ImageGrab.grab(bbox=(x,y,x+1,y+1)).getpixel((0,0))
        samples.append((round(elapsed,3),round(scale,5),pixel,s.draw_count))
    print('Five-second animation while UI thread sleeps:',samples)
    assert samples[1][1]<1.03 and samples[2][1]<1.105 and samples[3][1]>1.195
    assert samples[-1][1]>1.199
    assert samples[0][2]!=samples[-1][2],'Visible desktop zoom did not occur'
    print('Process CPU seconds across 5s motion:',round(time.process_time()-cpu,3),'render CPU:',round(s.render_cpu_seconds,3))
    # Check actual desktop pixels, not just the Python telemetry, for every
    # timer. Resume near the end to exercise the native endpoint and fade freeze.
    from wallpaper_engine import _render_scaled_image
    rendered=_render_scaled_image(im,s.width,s.height,'Fill')
    for interval in (5,15,30):
        s.start_zoom(interval,'smooth');time.sleep(.08);s.pause();time.sleep(.06)
        with s._lock:s._elapsed=interval-.4
        s.resume();time.sleep(.25)
        x,y=s.width//4,s.height//2
        before=ImageGrab.grab(bbox=(x,y,x+1,y+1)).getpixel((0,0))
        expected=zoom_frame(rendered,zoom_scale(s.elapsed,interval)).getpixel((x,y))
        assert max(abs(a-b) for a,b in zip(before,expected))<=2,(interval,before,expected)
        time.sleep(.2);s.pause();time.sleep(.08)
        after=ImageGrab.grab(bbox=(x,y,x+1,y+1)).getpixel((0,0))
        assert max(abs(a-b) for a,b in zip(before,after))<=2,('endpoint jump',interval,before,after,s.error,s.winfo_exists())
        print('Visible endpoint continuous:',interval,before,after)
    s.start_zoom(15,'smooth');time.sleep(.3);s.pause();frozen=s.elapsed;scale=s.last_scale
    time.sleep(.2);assert abs(s.elapsed-frozen)<.001 and s.last_scale==scale
    s.resume();time.sleep(.2);assert s.elapsed>frozen+.15
    s.start_zoom(5,'pulse');time.sleep(1);assert s.last_scale>1.095
    time.sleep(1.1);assert s.last_scale<1.005
    old=s
    e.fade_transition(str(p),str(p),'Fill',.1)
    assert old.winfo_exists(),'Outgoing zoom disappeared before fade'
    deadline=time.monotonic()+3
    while e._zoom_overlay is old:
        e.root.update();assert time.monotonic()<deadline
    assert e._zoom_overlay.last_scale<1.01,'Incoming image started already zoomed'
    # Turning off/on during the handoff must recreate a dead active surface.
    e.configure_zoom(False,'Fill','interval',5,False,str(p),'smooth')
    e.configure_zoom(True,'Fill','interval',5,False,str(p),'smooth')
    deadline=time.monotonic()+3
    while not e._zoom_overlay:
        e.root.update();assert time.monotonic()<deadline
    assert e._zoom_overlay.winfo_exists()
    print('Pause/resume, pulse period, transition continuity and rapid toggle passed')
finally:
    e._cancel_fade();e.stop_zoom();e.root.destroy();p.unlink(missing_ok=True)
