from fastapi import  FastAPI
from app.api.v1.router import router_v1
from app.api.ws.endpoint import router as ws_router
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="Loupe", version="1.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"ok": True}

app.include_router(router_v1)
app.include_router(ws_router)