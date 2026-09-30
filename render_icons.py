import os
import io
import resvg_py
from PIL import Image

def generate_icons():
    icon_dir = "icons"
    os.makedirs(icon_dir, exist_ok=True)
    
    icon_names = [
        'shuffle', 'skip-back', 'pause', 'play', 
        'folder-plus', 'trash', 'arrows-clockwise', 'desktop',
        'folder', 'check-square', 'square'
    ]
    colors = {
        'white': '#FFFFFF',
        'primary': '#D0BCFF',
        'on_primary': '#381E72',
        'text': '#E6E0E9',
        'muted': '#938F99'
    }
    
    sizes = [16, 18, 20, 24]
    
    for name in icon_names:
        svg_file = f"{name}.svg"
        if not os.path.exists(svg_file):
            continue
        with open(svg_file, "r", encoding="utf-8") as f:
            svg_template = f.read()
            
        for color_name, hex_color in colors.items():
            colored_svg = svg_template.replace('currentColor', hex_color)
            for sz in sizes:
                png_bytes = resvg_py.svg_to_bytes(colored_svg, width=sz, height=sz)
                img = Image.open(io.BytesIO(png_bytes))
                out_path = os.path.join(icon_dir, f"{name}_{color_name}_{sz}.png")
                img.save(out_path, "PNG")

    print("All Phosphor icons generated successfully in icons/ directory!")

if __name__ == "__main__":
    generate_icons()
