"""Exercise the real UI, shuffle timer, native commit and fade cleanup together."""
import argparse,ctypes,time,tkinter as tk,winreg,json
from pathlib import Path
from unittest.mock import Mock
from PIL import Image,ImageGrab
from wallpaper_engine import WindowsWallpaperEngine,SCALING_STYLES,_render_scaled_image
from playlist_manager import PlaylistManager
from ui import WallpaperSwitcherUI
from zoom_effect import zoom_scale,pulse_parameters

parser=argparse.ArgumentParser()
parser.add_argument('--interval',type=int,choices=(5,15,30),default=5)
parser.add_argument('--pulse',action='store_true')
args=parser.parse_args()

ctypes.windll.shcore.SetProcessDpiAwareness(1)
engine=WindowsWallpaperEngine()
original=engine.get_current_system_wallpaper()
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Control Panel\Desktop') as k:
    style=winreg.QueryValueEx(k,'WallpaperStyle')[0];tile=winreg.QueryValueEx(k,'TileWallpaper')[0]
mode=next((m for m,v in SCALING_STYLES.items() if v==(style,tile)),'Fill')
folder=Path(engine.cache_dir)/'playback-check';folder.mkdir(exist_ok=True)
for n in range(2):
    im=Image.new('RGB',(1920,1080))
    row=Image.new('RGB',(1920,1))
    for x in range(1920):row.putpixel((x,0),(round(x*255/1919),90,50+100*n))
    im=row.resize((1920,1080));im.save(folder/f'{n}.bmp')
settings={'zoom_effect':True,'zoom_style':'pulse' if args.interval==5 else 'smooth','interval_seconds':args.interval,'scaling_mode':'Fill',
          'last_wallpaper':str(folder/'0.bmp'),'folders':[str(folder)]}
config=Mock();config.get.side_effect=lambda k,d=None:settings.get(k,d)
config.set.side_effect=lambda k,v:settings.__setitem__(k,v)
root=tk.Tk();root.withdraw();records=[];errors=[];peaks=[]
display=engine.get_display_info()
with Image.open(folder/'0.bmp') as source:
    base=_render_scaled_image(source,display['width'],display['height'],'Fill')
try:
    ui=WallpaperSwitcherUI(root,config,engine,PlaylistManager([str(folder)]),Mock());root.withdraw()
    started=time.monotonic();next_sample=0;selected=False
    while time.monotonic()-started<args.interval+7:
        root.update();elapsed=time.monotonic()-started
        if elapsed>.3 and not selected and args.interval==5 and not args.pulse:
            ui.zoom_radios[1]._toggle();selected=True
        if elapsed>=next_sample:
            s=getattr(engine,'_zoom_overlay',None)
            x,y=ctypes.windll.user32.GetSystemMetrics(0)//4,ctypes.windll.user32.GetSystemMetrics(1)//2
            pixel=ImageGrab.grab(bbox=(x,y,x+1,y+1)).getpixel((0,0))
            records.append((round(elapsed,2),s._effect if s else None,round(s.elapsed,2) if s else None,round(s.last_scale,4) if s else None,pixel))
            if s and s.elapsed>.2 and not s._paused and s._effect==ui.zoom_style.get():
                scale=zoom_scale(s.elapsed,args.interval,s._effect)+(.002 if s._effect=='pulse' else 0)
                texture=base
                sx=round(texture.width/2+(x-texture.width/2)/scale)
                sy=round(texture.height/2+(y-texture.height/2)/scale)
                expected=texture.getpixel((sx,sy))[0]
                if s._effect=='pulse':
                    lens,fringe,separation=pulse_parameters(s.elapsed)
                    nx=2*sx/base.width-1;ny=2*sy/base.height-1
                    radius2=(nx*nx+ny*ny)/2
                    def red_at(strength):
                        source_x=round(base.width*(1+nx*(1-strength*(1-radius2)))/2)
                        return base.getpixel((min(base.width-1,max(0,source_x)),sy))[0]
                    expected=round(red_at(lens)*(1-fringe)+red_at(lens+separation)*fringe)
                errors.append(abs(pixel[0]-expected))
                assert errors[-1]<=2,('Visible motion covered or wrong curve',records[-1],expected,s.error)
                if s._effect=='smooth' and 4.7<s.elapsed<5.1:peaks.append(pixel[0])
            next_sample+=.25
        time.sleep(.005)
    assert len(errors)>args.interval*2,('Insufficient visible motion samples',len(errors))
    if not args.pulse:assert peaks and min(peaks)>=73,('Did not visibly reach 20%',peaks)
    assert engine._deferred_wallpaper,'Static wallpaper must be deferred during motion'
    assert engine.get_current_system_wallpaper()==original,'Native wallpaper changed during live motion'
    engine._cancel_fade()
    deferred=engine._deferred_wallpaper[0]
    engine.stop_zoom()
    assert engine.get_current_system_wallpaper()==deferred,'Stopping did not restore the current static wallpaper'
    if args.pulse:
        held=[p for p in records if p[1]=='pulse' and p[2]==2.0]
        assert len(held)>=6,'Pulse must finish at 2s and hold until shuffle'
        assert all(abs(p[3]-1.0)<.003 for p in held),'Pulse repeated after its first cycle'
    print('PASS:',args.interval,'seconds', 'pulse' if args.pulse else 'smooth',len(errors),'desktop samples; max pixel error',max(errors),'; real shuffle, cleanup and static restore passed',flush=True)
finally:
    engine._cancel_fade();engine.stop_zoom();root.destroy()
    if original:engine.set_wallpaper(original,mode)
    for p in folder.glob('*.bmp'):p.unlink()
    folder.rmdir()
