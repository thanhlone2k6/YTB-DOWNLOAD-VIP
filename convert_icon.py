from PIL import Image
import os

img_path = r"e:\Coding\YTB DOWLOAD\icon\Whisk_ab530ef69237bcba6a14ce2c4f6f3a12dr.jpeg"
ico_path = r"e:\Coding\YTB DOWLOAD\icon.ico"

try:
    img = Image.open(img_path)
    img.save(ico_path, format='ICO', sizes=[(256, 256)])
    print(f"Successfully converted to {ico_path}")
except Exception as e:
    print(f"Error converting: {e}")
