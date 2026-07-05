import os
import requests
from dotenv import load_dotenv

load_dotenv()

LANE_URL = os.environ["PRIVATE_LANE_URL"]
LANE_TOKEN = os.environ["PRIVATE_LANE_TOKEN"]
REVIEW_URL = os.environ["REVIEW_LANE_URL"]

def generate(prompt: str, max_new_tokens: int = 512) -> str:
    # send a prompt to the private LLM lane and return the generated text
    resp = requests.post(
        LANE_URL,
        json={"prompt": prompt, "token": LANE_TOKEN, "max_new_tokens": max_new_tokens},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["text"]

def generate_review(prompt: str, max_new_tokens:int =256) -> str :
    #send a prompt to the 14B review lane and return the generated text
    resp = requests.post(
        REVIEW_URL,
        json = {"prompt": prompt,"token": LANE_TOKEN, "max_new_tokens": max_new_tokens},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["text"]
    