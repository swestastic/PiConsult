from Resources import config
import Resources.OLED_2in42 as OLED_2in42
from PIL import Image,ImageDraw,ImageFont
import time

# OLED screen info
Device_SPI = config.Device_SPI
Device_I2C = config.Device_I2C
OLED_WIDTH   = 128
OLED_HEIGHT  = 64
font1 = ImageFont.truetype('Font.ttc', 18)
font2 = ImageFont.truetype('Font.ttc', 20)

disp = OLED_2in42.OLED_2in42(spi_freq = 1000000)
disp.Init()

def center_text(text, font, display_width, display_height):
    # Create a dummy image to calculate text size
    dummy_image = Image.new('1', (display_width, display_height), 255)
    draw = ImageDraw.Draw(dummy_image)
    
    # Calculate text width and height
    text_width, text_height = draw.textsize(text, font=font)
    
    # Calculate top-left corner position for centering
    x = (display_width - text_width) // 2
    y = (display_height - text_height) // 2
    
    return x, y

def flash_text(text, font, disp, flashes=10, flash_interval=0.5):
    display_width, display_height = 128, 64  # OLED display dimensions
    
    for _ in range(flashes):
        # Create image and draw object
        image = Image.new('1', (display_width, display_height), 255)  # White background
        draw = ImageDraw.Draw(image)
        
        # Get centered position
        x, y = center_text(text, font, display_width, display_height)
        
        # Draw the text (normal, black text on white background)
        draw.text((x, y), str(text), font=font, fill=0)  # Fill = 0 means black text
        
        # Rotate the image if needed
        image = image.rotate(180)
        
        # Display the image on the OLED
        disp.ShowImage(disp.getbuffer(image))
        
        # Wait for the flash interval
        time.sleep(flash_interval)
        
        # Invert the colors (white text on black background)
        image = Image.new('1', (display_width, display_height), 0)  # Black background
        draw = ImageDraw.Draw(image)
        draw.text((x, y), str(text), font=font, fill=1)  # Fill = 1 means white text
        
        # Rotate the image again
        image = image.rotate(180)
        
        # Display the inverted image on the OLED
        disp.ShowImage(disp.getbuffer(image))
        
        # Wait for the flash interval
        time.sleep(flash_interval)


# Example usage:
flash_text("OVERHEAT!", font1, disp, flashes=10, flash_interval=0.15)

disp.clear()