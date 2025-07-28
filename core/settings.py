import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ...existing settings code...

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# LLM Configuration
LLM_CALLS_DIR = os.path.join(BASE_DIR, "llm_calls")

# ...existing settings code...
