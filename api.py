from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title = "Support Ticket Triage API")

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["http://localhost:5173","http://localhost:3000",],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health():
    return {"status": "ok"}

