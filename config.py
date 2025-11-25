from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

ensue_token = os.getenv("ENSUE_TOKEN")

if not ensue_token:
    raise RuntimeError("ENSUE_TOKEN is not set")
