"""One-off: renders the SEVER/ wordmark PNG for the Cognito hosted UI."""

from PIL import Image, ImageDraw, ImageFont

INK = (23, 34, 28)      # #17221C
LEAK = (194, 47, 47)    # #C22F2F
PAPER = (238, 242, 236, 0)  # transparent background

W, H = 560, 140
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("arialbd.ttf", 96)
except OSError:
    font = ImageFont.load_default()

text = "SEVER"
bbox = draw.textbbox((0, 0), text, font=font)
tw = bbox[2] - bbox[0]
th = bbox[3] - bbox[1]
x = (W - tw - 40) // 2 - bbox[0]
y = (H - th) // 2 - bbox[1]

draw.text((x, y), text, font=font, fill=INK)
slash_x = x + tw + 6
draw.text((slash_x, y), "/", font=font, fill=LEAK)

img.save("deploy/sever-logo.png")
print("wrote deploy/sever-logo.png")
