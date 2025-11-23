from PIL import Image, ImageDraw

def create_placeholder_image(filename):
    width = 256
    height = 224
    # Create an indexed image
    image = Image.new("P", (width, height), 0)
    
    # Define a simple palette (up to 16 colors)
    # 0: Black (Background)
    # 1: White (Text)
    # 2: Red
    # 3: Green
    # 4: Blue
    # 5: Yellow
    palette = [
        0, 0, 0,    # 0
        255, 255, 255, # 1
        255, 0, 0,  # 2
        0, 255, 0,  # 3
        0, 0, 255,  # 4
        255, 255, 0, # 5
    ]
    # Pad the rest with black
    palette.extend([0, 0, 0] * (256 - 6))
    image.putpalette(palette)

    draw = ImageDraw.Draw(image)

    # Draw background (already 0)
    
    # Draw some rectangles
    draw.rectangle([(10, 10), (246, 214)], outline=1) # Border
    
    # Draw "Text" using simple rectangles since default font might be messy in indexed mode
    # or just draw some shapes to represent text
    
    # Title "HIGH SCORES"
    draw.rectangle([(100, 20), (156, 30)], fill=5)
    
    # Table headers
    draw.rectangle([(40, 50), (80, 60)], fill=1)
    draw.rectangle([(180, 50), (220, 60)], fill=1)
    
    # Rows
    for i in range(5):
        y = 70 + i * 20
        draw.rectangle([(40, y), (100, y+10)], fill=2)
        draw.rectangle([(180, y), (220, y+10)], fill=3)

    image.save(filename)
    print(f"Created {filename}")

if __name__ == "__main__":
    create_placeholder_image("high_score_placeholder.png")
