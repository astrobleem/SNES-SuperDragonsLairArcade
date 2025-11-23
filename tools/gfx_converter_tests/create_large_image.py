from PIL import Image, ImageDraw

def create_large_test_image(filename):
    width = 500
    height = 500
    image = Image.new("RGB", (width, height), "blue")
    draw = ImageDraw.Draw(image)
    
    # Draw a red circle in the center
    draw.ellipse([(100, 100), (400, 400)], fill="red", outline="white")
    
    # Draw text
    draw.text((10, 10), "TOP LEFT", fill="white")
    draw.text((400, 400), "BOTTOM RIGHT", fill="white")
    
    image.save(filename)
    print(f"Created {filename}")

if __name__ == "__main__":
    create_large_test_image("tools/gfx_converter_tests/large_test.png")
