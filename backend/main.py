import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import upload, tasks, chat

app = FastAPI(
    title="PPT Agent",
    description="上传文档，AI 自动生成 PPT",
    version="1.0.0",
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_detail = f"""
URL: {request.url}
Method: {request.method}
Error: {type(exc).__name__}: {str(exc)}
Traceback:
{traceback.format_exc()}
"""
    with open("error.log", "a") as f:
        import datetime
        f.write(f"\n[{datetime.datetime.now().isoformat()}]\n")
        f.write(error_detail)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "PPT Agent"}
