from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.prompt_routes import route as prompt_router

app = FastAPI(title="🧠 MCP Prompt API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prompt_router)

# Run with: uvicorn main:app --reload
