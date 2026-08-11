import os
from PIL import Image, ImageDraw, ImageFilter

os.makedirs("public/static", exist_ok=True)

def create_omnia_logo(size=512):
    # Transparent PNG
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    margin = int(size * 0.08)
    center = size // 2
    radius = (size - 2 * margin) // 2
    
    # Glow ring overlay behind
    glow_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    glow_draw.ellipse(
        [center - radius, center - radius, center + radius, center + radius],
        outline=(0, 113, 227, 180),
        width=int(size * 0.08)
    )
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=int(size * 0.04)))
    
    # Composite glow
    img = Image.alpha_composite(img, glow_img)
    draw = ImageDraw.Draw(img)
    
    # Outer Ring: Gradient Blue to Emerald Green
    width_ring = int(size * 0.07)
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        outline=(0, 113, 227, 255),
        width=width_ring
    )
    
    # Inner Accent Ring
    inner_m = margin + int(size * 0.06)
    draw.ellipse(
        [inner_m, inner_m, size - inner_m, size - inner_m],
        outline=(52, 199, 89, 220),
        width=int(size * 0.025)
    )
    
    # Center Play Shutter Triangle (Omnia Symbol)
    tri_margin = int(size * 0.34)
    p1 = (center - int(size * 0.1), center - int(size * 0.16))
    p2 = (center - int(size * 0.1), center + int(size * 0.16))
    p3 = (center + int(size * 0.16), center)
    
    draw.polygon([p1, p2, p3], fill=(255, 149, 0, 255))
    
    # Sparkle Accent Top Right
    sp_x, sp_y = center + int(size * 0.22), center - int(size * 0.22)
    sp_r = int(size * 0.04)
    draw.ellipse([sp_x - sp_r, sp_y - sp_r, sp_x + sp_r, sp_y + sp_r], fill=(255, 255, 255, 255))
    
    out_path = "public/static/icon.png"
    img.save(out_path, "PNG")
    print(f"Saved transparent PNG logo at {out_path} ({os.path.getsize(out_path)} bytes)")

if __name__ == "__main__":
    create_omnia_logo()
