from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

ensue_token = os.getenv("ENSUE_API_KEY")

if not ensue_token:
    raise RuntimeError("ENSUE_API_KEY is not set")
