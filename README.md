# 🌿 Bushtwo BGS

> **A modern, lightweight, Material 3 wallpaper shuffle and desktop background manager for Windows.**

Built for creators and designers who appreciate pixel precision, zero visual clutter, and clean system integration. Redesigned with Google's **Material Design 3 (M3)** visual language and **Phosphor Icons**.

---

## ⚡ Quick Start

### Option 1: Standalone Portable Executable (Recommended)
1. Download or locate **`Bushtwo BGS.exe`**.
2. **Double-click to run** — zero installation, zero dependencies, no console window.
3. Add your wallpaper folders and enjoy seamless automated shuffling!

> **Portable by design**: Place `Bushtwo BGS.exe` anywhere (Desktop, USB drive, portable tools folder). It saves `config.json` in the same directory.

---

### Option 2: Running from Source
Requires Python 3.10+:

```bash
# Clone the repository
git clone https://github.com/your-username/bushtwo-bgs.git
cd bushtwo-bgs

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

---

## 🖥️ User Interface Layout

Bushtwo BGS uses a **16px Spacing System** with **24px internal card padding**, **16px rounded corners**, borderless components, and adaptive monitor scaling:

```
┌────────────────────────────────────────────────────────┐
│  1. CURRENT DESKTOP WALLPAPER                          │
│     [ 16:9 Rounded Preview Box ]     [● ACTIVE Badge]  │
├────────────────────────────────────────────────────────┤
│  2. DISPLAY SPECIFICATIONS                             │
│     🖥 Primary Display: 2560 × 1440 @ 120Hz (32-bit)    │
├────────────────────────────────────────────────────────┤
│  3. WALLPAPER DETAILS & CONTROLS                       │
│     • Active Image: Mountain_Sunset_4K.jpg             │
│     • Dimensions & Path: 3840 × 2160 • D:\Wallpapers   │
│     • [◀ Prev]   [🔀 Shuffle / Next]   [⏸ Pause]       │
│     • Countdown Badge: Next in: 04:32 (or Next: 12 AM) │
├────────────────────────────────────────────────────────┤
│  4. WALLPAPER DIRECTORIES                              │
│     • Clean borderless folder list with image counts   │
│     • [➕ Add Folder...]   [🗑 Remove]   [🔄 Rescan]     │
│     • [✓] Include subfolders                           │
├────────────────────────────────────────────────────────┤
│  5. SIDE-BY-SIDE CONTROLS                              │
│     ┌──────────────────────┬─────────────────────────┐ │
│     │ SCALING MODE         │ SHUFFLE TIMER           │ │
│     │ [ Fill (Crop)      ▼]│ [ 5 minutes           ▼]│ │
│     │ Crops without bars   │ Strictly selectable     │ │
│     └──────────────────────┴─────────────────────────┘ │
├────────────────────────────────────────────────────────┤
│  6. SYSTEM & BACKGROUND OPTIONS                        │
│     • [✓] Run automatically when Windows starts up     │
│     • [✓] Minimize to system tray on close             │
└────────────────────────────────────────────────────────┘
```

---

## ✨ Features

### 🎨 Material Design 3 (M3) Dark Theme
- **Color System**:
  - Surface: `#141218`
  - Cards & Containers: `#211F26` / `#2B2930`
  - Primary Accent: `#D0BCFF` (Lavender Purple)
  - On-Primary: `#381E72`
  - Outline & Variants: `#49454F` / `#CAC4D0`
- **Curvature**: 16px corner radius across all cards, badges, and popup menus.
- **Elevation & Layout**: Hugs content dynamically with zero scrollbars and zero awkward dead space.

### 📐 Pixel-Precise Spacing Architecture
- **8px** outer container window margin.
- **16px** vertical spacing between all cards and sections.
- **24px** internal top/bottom/left/right padding inside cards.
- **Fixed & Adaptive**: Disables accidental user resizing while adapting smoothly to 1080p, 2K, and 4K displays.

### ⚡ Phosphor Icons Across the Board
Clean, consistent vector iconography powered by [Phosphor Icons](https://phosphoricons.com/):
- **Playback**: Bold `shuffle`, `skip-back`, `pause`, and `play` icons.
- **Folders**: Phosphor `folder`, `folder-plus`, `trash`, and `arrows-clockwise`.
- **System**: Phosphor `desktop` monitor and customized `check-square` / `square` checkboxes.
- **System Tray**: Native Win32 32-bit PARGB alpha-blended Phosphor icons directly on the taskbar context menu.

### 🎛️ Side-by-Side Dropdown Controls
- **Scaling Mode Dropdown**:
  - `Fill (Crop to screen)`: Fills entire screen maintaining aspect ratio without black borders.
  - `Fit (Letterbox)`: Preserves original aspect ratio with bars.
  - `Stretch`: Stretches image to exact monitor dimensions.
  - `Tile`: Patterns smaller textures across the display.
  - `Center`: Displays image at 1:1 actual pixel resolution.
  - `Span`: Spans wide panoramic wallpapers across multi-monitor setups.
- **Shuffle Timer Dropdown**:
  - Strictly selectable presets: `5s`, `15s`, `30s`, `1m`, `5m`, `10m`, `15m`, `30m`.
  - **1 Day (12:00 AM Midnight)**: Automates wallpaper changes to coincide with the start of each new day!
- **16px Rounded Dropdown Menus**: Custom borderless popup menus with Windows 11 DWM rounded corners.

### 🖥️ Deep Windows OS Integration
- **Notification Area (System Tray)**:
  - Left-click opens/focuses the window.
  - Right-click brings up a context menu with native Phosphor icons.
  - Live tooltip showing current active wallpaper and pause status.
- **Per-Monitor DPI Awareness**: Automatically sets `Per-Monitor V2` DPI awareness via Windows Win32 API to avoid any blurriness or scaling artifacts.
- **Taskbar Icon Grouping**: Explicit `SetCurrentProcessExplicitAppUserModelID` prevents generic Python icon grouping and binds your custom taskbar icon.
- **Universal Format Support**: Reads JPG, JPEG, PNG, WEBP, BMP, JFIF, and TIFF. High-compression web formats are converted to cached desktop bitmaps automatically.
- **Windows Startup**: Optional single-click registry integration (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`) to launch minimized at boot.

---

## 🛠️ Building the Standalone `.exe`

To package Bushtwo BGS into a single portable binary:

```bash
pip install pyinstaller pillow pystray

python -m PyInstaller --clean --noconfirm --onefile --windowed \
  --name "Bushtwo BGS" \
  --icon "bushtwo_bgs.ico" \
  --add-data "icons;icons" \
  --add-data "Bushtwo BGS 64x64 pixels.png;." \
  --add-data "Bushtwo BGS 32x32 pixels.png;." \
  --add-data "Bushtwo BGS 16 x16 pixels.png;." \
  --add-data "Bushtwo BGS 8 x 8 pixels.png;." \
  --add-data "bushtwo_bgs.ico;." \
  main.py
```

The resulting `Bushtwo BGS.exe` will be located in the root / `dist/` directory.

---

## 📁 Project Architecture

```
Bushtwo BGS/
├── Bushtwo BGS.exe             # Portable standalone executable
├── main.py                     # Entry point, DPI awareness & event loops
├── ui.py                       # Material 3 UI, custom controls & styling
├── tray_manager.py             # Win32 system tray integration & icon menu
├── wallpaper_engine.py         # Win32 desktop API & registry scaling
├── playlist_manager.py         # Folder scanner, image queues & history
├── config_manager.py           # Persistent JSON settings manager
├── icons/                      # Phosphor icons (16px, 18px, 20px, 24px)
├── bushtwo_bgs.ico             # Windows multi-resolution icon
└── config.json                 # Persistent user settings
```

---

## 📜 License

MIT License. Designed and developed with care for personal and open-source use.
