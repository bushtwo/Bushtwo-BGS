from unittest.mock import Mock
from pathlib import Path
import tempfile
from ui import WallpaperSwitcherUI
with tempfile.TemporaryDirectory(dir='.cache') as d:
    a=Path(d)/'bad.jpg';b=Path(d)/'valid.png';a.write_text('not an image');b.write_bytes(b'valid fixture')
    u=WallpaperSwitcherUI.__new__(WallpaperSwitcherUI);u._unreadable_wallpapers={};u.playlist=Mock()
    u.playlist.all_images=[str(a),str(b)];u.playlist.get_next_wallpaper.side_effect=[str(a),str(b)]
    u._update_current_wallpaper_display=Mock(side_effect=[False,True])
    assert u._readable_wallpaper()==str(b)
    assert str(a) in u._unreadable_wallpapers
print('Unreadable wallpaper entries are skipped rather than interrupting motion')
