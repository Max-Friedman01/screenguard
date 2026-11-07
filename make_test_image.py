from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


output = Path("tests/screens/privacy-test.png")

image = Image.new(
    "RGB",
    (1280, 720),
    "white",
)

draw = ImageDraw.Draw(image)

try:
    font = ImageFont.truetype("arial.ttf", 42)
except OSError:
    font = ImageFont.load_default()

lines = [
    "University helpdesk",
    "Email: asher@example.com",
    "Phone: 07123 456789",
    "Test card: 4111 1111 1111 1111",
    "Opening hours: 9:00 AM to 5:00 PM",
]

y = 80

for line in lines:
    draw.text(
        (80, y),
        line,
        fill="black",
        font=font,
    )
    y += 90

image.save(output)
print(f"Created: {output.resolve()}")
