"""One-off: renders the 1024x1024 SEVER app icon (S/) in brand colors."""

from PIL import Image, ImageDraw, ImageFont

INK = (23, 34, 28)       # #17221C
LEAK = (194, 47, 47)     # #C22F2F
PAPER = (238, 242, 236)  # #EEF2EC

SIZE = 1024
img = Image.new("RGB", (SIZE, SIZE), PAPER)
draw = ImageDraw.Draw(img)

font = ImageFont.truetype("deploy/Archivo-Variable.ttf", 640)
# Axes order in this font is [Weight, Width]: match the masthead (900, 75)
font.set_variation_by_axes([900, 75])

s_box = draw.textbbox((0, 0), "S", font=font)
slash_box = draw.textbbox((0, 0), "/", font=font)
s_w = s_box[2] - s_box[0]
slash_w = slash_box[2] - slash_box[0]
gap = 20
total_w = s_w + gap + slash_w

top = min(s_box[1], slash_box[1])
bottom = max(s_box[3], slash_box[3])
text_h = bottom - top

x = (SIZE - total_w) // 2
y = (SIZE - text_h) // 2 - top

draw.text((x - s_box[0], y), "S", font=font, fill=INK)
draw.text((x + s_w + gap - slash_box[0], y), "/", font=font, fill=LEAK)

img.save("deploy/sever-icon-1024.png")
print("wrote deploy/sever-icon-1024.png")
