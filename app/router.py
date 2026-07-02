import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

LANE_URL = os.environ["PRIVATE_LANE_URL"]
LANE_TOKEN = os.environ["PRIVATE_LANE_TOKEN"]

def generate(prompt: str, max_new_tokens: int = 512) -> str:
    #se4nd a prompt to the private LLM lane and return the generated text
    resp = requests.post(
        LANE_URL,
        json={"prompt": prompt, "token": LANE_TOKEN, "max_new_tokens": max_new_tokens},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["text"]