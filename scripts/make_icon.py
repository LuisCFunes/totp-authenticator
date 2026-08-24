import os

from PIL import Image, ImageDraw

BG = (24, 26, 34, 255)
BORDER = (47, 180, 113, 255)
LOCK = (47, 180, 113, 255)
SHACKLE = (168, 175, 190, 255)
KEYHOLE = (16, 18, 24, 255)

SIZE = 512


def draw_base():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=100, fill=BG)
    d.rounded_rectangle(
        (8, 8, SIZE - 8, SIZE - 8), radius=100, outline=BORDER, width=14
    )

    d.arc((156, 92, 356, 292), start=180, end=360, fill=SHACKLE, width=46)

    d.rounded_rectangle((136, 236, 376, 428), radius=40, fill=LOCK)

    d.ellipse((222, 292, 290, 360), fill=KEYHOLE)
    d.rectangle((240, 330, 272, 396), fill=KEYHOLE)
    return img


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets = os.path.join(root, "assets")
    os.makedirs(assets, exist_ok=True)
    out = os.path.join(assets, "icon.ico")
    img = draw_base()
    img.save(out, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("icon written:", out)


if __name__ == "__main__":
    main()
