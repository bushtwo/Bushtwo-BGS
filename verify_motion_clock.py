from unittest.mock import Mock,patch
from ui import WallpaperSwitcherUI
u=WallpaperSwitcherUI.__new__(WallpaperSwitcherUI)
u.root=Mock();u.root.after.return_value='scheduled'
u.playlist=Mock();u.playlist.has_images.return_value=True
u.timer_mode='interval';u.interval_seconds=5;u.is_paused=False
u._wallpaper_switching=True;u._shuffle_job=None;u.last_tick_time=10;u.time_remaining=5
u._update_timer_badge=Mock();u._update_pause_ui=Mock();u._sync_zoom=Mock();u.config_mgr=Mock();u.tray=None
with patch('ui.time.monotonic',return_value=100):
    u._timer_tick();assert u.time_remaining==5,'Preparation consumed the motion interval'
    u._wallpaper_ready();assert u.last_tick_time==100 and u.time_remaining==5
assert u.root.after.call_args.args[0]==5000,'Shuffle not scheduled at exact full interval'
with patch('ui.time.monotonic',return_value=101.25):u.action_toggle_pause()
assert u.is_paused and u.time_remaining==3.75 and u._shuffle_job is None
with patch('ui.time.monotonic',return_value=120):u.action_toggle_pause()
assert not u.is_paused and u.time_remaining==3.75
assert u.root.after.call_args.args[0]==3750
print('Full motion interval starts after commit; exact shuffle and pause clocks passed')
