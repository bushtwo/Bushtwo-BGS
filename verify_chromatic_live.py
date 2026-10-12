"""Check actual compositor output: neutral -> colored peak -> neutral."""
import ctypes,time,tkinter as tk,winreg
from pathlib import Path
from PIL import Image,ImageDraw,ImageGrab,ImageChops,ImageStat
from wallpaper_engine import WindowsWallpaperEngine,SCALING_STYLES,_render_scaled_image
from zoom_effect import zoom_frame,zoom_scale,pulse_parameters,pulse_texture

ctypes.windll.shcore.SetProcessDpiAwareness(1)
e=WindowsWallpaperEngine();e.root=tk.Tk();e.root.withdraw()
original=e.get_current_system_wallpaper()
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Control Panel\Desktop') as k:
    pair=(winreg.QueryValueEx(k,'WallpaperStyle')[0],winreg.QueryValueEx(k,'TileWallpaper')[0])
mode=next((m for m,v in SCALING_STYLES.items() if v==pair),'Fill')
p=Path(e.cache_dir)/'chromatic-check.bmp'
im=Image.new('RGB',(1920,1080),'black');draw=ImageDraw.Draw(im)
for x in range(0,1920,32):draw.rectangle((x,0,x+9,1079),fill='white')
im.save(p)
try:
    e.configure_zoom(True,'Fill','interval',5,False,str(p),'pulse')
    deadline=time.monotonic()+10
    while not getattr(e,'_zoom_overlay',None):
        e.root.update();assert time.monotonic()<deadline
    s=e._zoom_overlay
    assert s.backend_name=='GPU lens compositor',(s.backend_name,s.error)
    s.pause();time.sleep(.1)
    colors=[];geometry=[];warp_errors=[]
    base=_render_scaled_image(im,s.width,s.height,'Fill')
    for elapsed in (0,.5,.8,1,1.2,1.5,2):
        with s._lock:s._elapsed=elapsed;s._command='pause'
        s._wake.set();time.sleep(.12)
        x,y=s.width//4,s.height//2
        shot=ImageGrab.grab(bbox=(x,y,x+200,y+80)).convert('RGB')
        r,g,b=shot.split()
        amount=max(ImageChops.difference(r,g).getextrema()[1],ImageChops.difference(b,g).getextrema()[1])
        colors.append(amount)
        expected=zoom_frame(base,zoom_scale(elapsed,5,'pulse')+.002).crop((x,y,x+200,y+80))
        geometry.append(ImageStat.Stat(ImageChops.difference(g,expected.getchannel('G'))).mean[0])
        lens=pulse_texture(base,lens_strength=pulse_parameters(elapsed)[0],chromatic_strength=0)
        expected_warp=zoom_frame(lens,zoom_scale(elapsed,5,'pulse')+.002).crop((x,y,x+200,y+80))
        warp_errors.append(ImageStat.Stat(ImageChops.difference(g,expected_warp.getchannel('G'))).mean[0])
    assert colors[0]==colors[1]==colors[-1]==colors[-2]==0,colors
    assert colors[3]>=145 and colors[2]>0 and colors[4]>0,colors
    assert geometry[-1]<5 and geometry[1]>20 and geometry[3]>20,('Residual or missing lens distortion',geometry)
    assert max(warp_errors[i] for i in (0,1,3,5,6))<5,('Lens is fading rather than warping',warp_errors)
    print('Actual RGB separation at 0/.5/.8/1/1.2/1.5/2s:',colors)
    print('Error against continuously warped geometry:',[round(v,2) for v in warp_errors])
    s.start_zoom(5,'pulse');started=time.monotonic();cpu=time.process_time();live=[]
    for elapsed in (.35,.85,1,1.7,2.2):
        time.sleep(max(0,started+elapsed-time.monotonic()))
        shot=ImageGrab.grab(bbox=(x,y,x+200,y+80)).convert('RGB')
        r,g,b=shot.split()
        live.append(max(ImageChops.difference(r,g).getextrema()[1],ImageChops.difference(b,g).getextrema()[1]))
    assert live[0]==live[-1]==live[-2]==0 and live[2]>20,live
    print('Running native timeline RGB separation:',live)
    print('CPU seconds during 2.2s pulse:',round(time.process_time()-cpu,3),'render thread:',round(s.render_cpu_seconds,3),'frames:',s.draw_count)
    assert not s.error,s.error
    print('Opaque moving lens, timed aberration, neutral start/end and GPU shader passed')
finally:
    e._cancel_fade();e.stop_zoom();e.root.destroy()
    if original:e.set_wallpaper(original,mode)
    p.unlink(missing_ok=True)
