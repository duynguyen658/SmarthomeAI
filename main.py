import uvicorn
import uuid
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os


load_dotenv()
from smart_home.agent_ollama import call_agent, check_ollama_status
from database import init_db, migrate_from_hardcoded
from scheduler import start_scheduler, stop_scheduler

#------vòng đời-----
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Đang khởi động Smart Home API...")
    
    # Initialize database
    print("Initializing database...")
    init_db()
    migrate_from_hardcoded()
    
    # Start scheduler
    print("Starting scheduler...")
    start_scheduler()
    
    # Start notification service
    print("Starting notification service...")
    import asyncio
    from notification_service import check_alerts
    asyncio.create_task(check_alerts())
    
    # Check Ollama connection
    print("Checking Ollama connection...")
    status = await check_ollama_status()
    if status["connected"]:
        print(f"✅ Ollama connected: {status['model']}")
        print(f"   Available models: {status['available_models']}")
    else:
        print("⚠️ Ollama not connected. Please ensure Ollama is running.")
        print("   Install Ollama: https://ollama.com/download")
        print("   Then run: ollama pull mistral")
    
    yield
    
    # Cleanup
    print("Đang tắt ứng dụng...")
    stop_scheduler()
    print("Services stopped")

app = FastAPI(title="Smart Home AI (Ollama)", lifespan=lifespan)
router = APIRouter()

# Serve static files from web directory
web_dir = os.path.join(os.path.dirname(__file__), "web")

class ChatRequest(BaseModel):
    query: str
    user_id: str | None = None 
    session_id: str | None = None

class ChatResponse(BaseModel):
    response: str
    user_id: str
    session_id: str

# --- API ENDPOINT ---
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    user_id = request.user_id if request.user_id else str(uuid.uuid4())
    session_id = request.session_id if request.session_id else str(uuid.uuid4())
    
    print(f" Request: '{request.query}' | User: {user_id} | Session: {session_id}")

    try:
        # Gọi Ollama Agent
        response_text = await call_agent(request.query)
        print(f"Response: {response_text}")
        
        return ChatResponse(
            response=response_text,
            user_id=user_id,
            session_id=session_id
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")

# --- Status Endpoint ---
@router.get("/status/ollama")
async def get_ollama_status():
    """Kiểm tra trạng thái Ollama"""
    status = await check_ollama_status()
    return status

# Gắn routers vào app
app.include_router(router, prefix="/api", tags=["SmartHome Chat"])

# Include new API routers
from api import devices, schedules, alerts, rules, sensors
app.include_router(devices.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(sensors.router, prefix="/api")

# Serve static files AFTER API routes (to avoid catching /api/* paths)
if os.path.exists(web_dir):
    # Mount static files (CSS, JS, images)
    app.mount("/assets", StaticFiles(directory=web_dir), name="assets")
    
    @app.get("/")
    async def read_root():
        return FileResponse(os.path.join(web_dir, "index.html"))
    
    @app.get("/{path:path}")
    async def serve_static(path: str):
        # Skip API paths
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        file_path = os.path.join(web_dir, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(web_dir, "index.html"))

if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
