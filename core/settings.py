import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ...existing settings code...

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# ...existing settings code...
