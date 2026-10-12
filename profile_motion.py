import time,ctypes
from PIL import Image
from animated_surface import AnimatedSurface
from wallpaper_engine import WindowsWallpaperEngine
ctypes.windll.shcore.SetProcessDpiAwareness(1)
e=WindowsWallpaperEngine();p=e._wallpaper_layer()
s=AnimatedSurface(p,Image.new('RGB',(2560,1440),(0,100,150)))
try:
    s.start_zoom(15,'smooth');time.sleep(.3)
    cpu=time.process_time();frames=s.draw_count;started=time.monotonic();time.sleep(2)
    print('Actual FPS:',round((s.draw_count-frames)/(time.monotonic()-started),1),'CPU seconds over 2s:',round(time.process_time()-cpu,3),'draw CPU:',round(s.render_cpu_seconds,3),'wall draw ms:',round(sum(s._frame_times)/max(1,len(s._frame_times))*1000,2))
    s.pause();cpu=time.process_time();frames=s.draw_count;time.sleep(.5)
    print('Paused frames:',s.draw_count-frames,'paused CPU:',round(time.process_time()-cpu,3))
finally:s.destroy()
