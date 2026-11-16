import os
from PIL import Image

def get_iigs_color(r, g, b):
    # Apple IIGS SHR colors are 12-bit RGB (0-15 for each channel) -> 0x0RGB
    r12 = (r >> 4) & 0x0F
    g12 = (g >> 4) & 0x0F
    b12 = (b >> 4) & 0x0F
    return (r12 << 8) | (g12 << 4) | b12

def process_image(img_path, array_name, out_file, palette_map):
    img = Image.open(img_path).convert("RGBA")
    img = img.resize((32, 32), Image.Resampling.LANCZOS)
    w, h = img.size
    
    # Needs to be even width for 4-bit SHR (2 pixels per byte)
    assert w % 2 == 0, f"Image {img_path} width must be even."


    pixel_data = []
    
    for y in range(h):
        for x in range(0, w, 2):
            r1, g1, b1, a1 = img.getpixel((x, y))
            r2, g2, b2, a2 = img.getpixel((x+1, y))
            
            # Use transparent color (index 0) if alpha is 0
            idx1 = 0 if a1 < 128 else palette_map.get((r1,g1,b1), 1)
            idx2 = 0 if a2 < 128 else palette_map.get((r2,g2,b2), 1)
            
            # IIGS SHR: High nibble is left pixel, Low nibble is right pixel (usually)
            # Actually, bits 4-7 = first pixel, bits 0-3 = second pixel
            byte_val = (idx1 << 4) | idx2
            pixel_data.append(byte_val)
            
    out_file.write(f"const unsigned char {array_name}[{len(pixel_data)}] = {{\n")
    for i in range(0, len(pixel_data), 16):
        chunk = pixel_data[i:i+16]
        hex_chunk = ", ".join(f"0x{v:02X}" for v in chunk)
        out_file.write(f"    {hex_chunk},\n")
    out_file.write(f"}};\n\n")

def main():
    media_dir = "../media"
    out_c = "src/assets.c"
    out_h = "src/assets.h"
    
    # Read gem1.png to build a master 16-color palette
    # (Since gems are colorful, we'll extract colors from them. 
    # For a real game we would use a fixed 16-color optimal palette).
    
    # For simplicity in this demo, let's create a generic 16-color palette
    # 0 = Transparent/Black
    # 1 = White
    # 2 = Red
    # 3 = Green
    # 4 = Blue
    # 5 = Yellow
    # 6 = Cyan
    # 7 = Magenta
    # 8 = Orange
    # 9 = Purple
    # 10 = Dark Gray
    # 11 = Light Gray
    # 12 = Dark Red
    # 13 = Dark Green
    # 14 = Dark Blue
    # 15 = Brown
    
    generic_palette = [
        (0,0,0), (255,255,255), (255,0,0), (0,255,0),
        (0,0,255), (255,255,0), (0,255,255), (255,0,255),
        (255,128,0), (128,0,255), (64,64,64), (192,192,192),
        (128,0,0), (0,128,0), (0,0,128), (128,64,0)
    ]
    
    # Build closest color map logic
    def closest_color(r, g, b):
        min_dist = 999999
        best_idx = 1
        for idx, (pr, pg, pb) in enumerate(generic_palette):
            if idx == 0: continue # 0 is transparent
            dist = (r-pr)**2 + (g-pg)**2 + (b-pb)**2
            if dist < min_dist:
                min_dist = dist
                best_idx = idx
        return best_idx
        
    # We will build a dynamic palette if we want, but closest_color is safer for un-quantized PNGs.
    
    with open(out_c, "w") as fc, open(out_h, "w") as fh:
        fh.write("#ifndef ASSETS_H\n#define ASSETS_H\n\n")
        fc.write('#include "assets.h"\n\n')
        
        # Write Palette
        fc.write("const unsigned int game_palette[16] = {\n    ")
        pal_hex = [f"0x{get_iigs_color(*c):04X}" for c in generic_palette]
        fc.write(", ".join(pal_hex))
        fc.write("\n};\n\n")
        
        fh.write("extern const unsigned int game_palette[16];\n")
        
        # We need a dynamic palette map for the image processor
        # Since we use closest_color, we don't need a static dictionary
        class PaletteMap:
            def get(self, color, default):
                return closest_color(*color)
                
        pmap = PaletteMap()
        
        gems = ['gemBlue.png', 'gemGreen.png', 'gemOrange.png', 'gemPurple.png', 'gemRed.png', 'gemWhite.png', 'gemYellow.png']
        for i, gem_file in enumerate(gems):
            path = os.path.join(media_dir, gem_file)
            if os.path.exists(path):
                arr_name = f"gem{i+1}_data"
                process_image(path, arr_name, fc, pmap)
                fh.write(f"extern const unsigned char {arr_name}[];\n")

                
        fh.write("\n#endif\n")

if __name__ == "__main__":
    main()
