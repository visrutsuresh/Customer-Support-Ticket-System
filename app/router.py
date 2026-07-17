import os

import requests
from dotenv import load_dotenv

load_dotenv()

LANE_URL = os.environ["PRIVATE_LANE_URL"]
LANE_TOKEN = os.environ["PRIVATE_LANE_TOKEN"]
REVIEW_URL = os.environ["REVIEW_LANE_URL"]
MODEL_TIER = os.getenv("MODEL_TIER", "dev").lower()

# Claude model ids for the cloud lane
HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-4-6"


def _modal(url: str, prompt: str, max_new_tokens: int) -> str:
    resp = requests.post(
        url,
        json={"prompt": prompt, "token": LANE_TOKEN, "max_new_tokens": max_new_tokens},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["text"]


def _claude(model: str, prompt: str, max_new_tokens: int) -> str:
    from anthropic import Anthropic

    client = Anthropic(timeout=60, max_retries=1)  # reads ANTHROPIC_API_KEY; hard timeout so a stalled call fails fast instead of hanging the batch/demo
    msg = client.messages.create(
        model=model,
        max_tokens=max_new_tokens,
        temperature=0,  # greedy, to match the already-greedy private lane so runs are reproducible
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# dispatch: model_id -> the right backend
def call_model(model_id: str, prompt: str, max_new_tokens: int = 512) -> str:
    if model_id == "3b":
        return _modal(LANE_URL, prompt, max_new_tokens)
    elif model_id == "14b":
        return _modal(REVIEW_URL, prompt, max_new_tokens)
    elif model_id == "haiku":
        return _claude(HAIKU, prompt, max_new_tokens)
    elif model_id == "sonnet":
        return _claude(SONNET, prompt, max_new_tokens)

    raise ValueError(f"unknown model_id: {model_id}")


def intended_model(lane: str, level: str) -> str:
    # the ideal full- 2x2 pick, ALWAYS returned for display, regardless of the toggle
    grid = {
        ("private", "simple"): "3b",
        ("private", "complex"): "14b",
        ("cloud", "simple"): "haiku",
        ("cloud", "complex"): "sonnet",
    }
    return grid[(lane, level)]


def reply_model(lane: str, level: str) -> str:
    # what ACTUALLY runs for the customer reply, capped by the toggle
    if MODEL_TIER == "dev":
        return "3b"
    elif MODEL_TIER == "local":
        return "14b" if level == "complex" else "3b"
    return intended_model(lane, level)  # full


def think_model(lane: str = None, level: str = None) -> str:
    # which model does the agent's reasoning capped by the MODEL_TIER in .env
    # dev/local pin reasoning to private line; only 'full' unlocks cloud lane with Claude
    if MODEL_TIER == "dev":
        return "3b"
    if MODEL_TIER == "local":
        return "14b"
    if lane != "cloud":
        return "14b"
    return intended_model("cloud", level or "complex")


def think(prompt: str, max_new_tokens: int = 256, lane: str = None, level: str = None) -> str:
    # every internal reasoning check goes through here
    return call_model(think_model(lane, level), prompt, max_new_tokens)


def generate_reply(prompt: str, lane: str, level: str, max_new_tokens: int = 512) -> str:
    # the customer facing reply, model chosen by the 2x2 matrix +toggle
    return call_model(reply_model(lane, level), prompt, max_new_tokens)
