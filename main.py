import uvicorn
import uuid
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from dotenv import load_dotenv
import os


load_dotenv()
from smart_home.agent import root_agent
from database import init_db, migrate_from_hardcoded
from scheduler import start_scheduler, stop_scheduler
from notification_service import start_notification_service

APP_NAME = "agents"

session_service = None
runner = None
#------vòng đời-----
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Đang khởi động Smart Home API...")
    global session_service, runner
    
    # Initialize database
    print("Initializing database...")
    init_db()
    migrate_from_hardcoded()
    
    # Start scheduler
    print("Starting scheduler...")
    start_scheduler()
    
    # Start notification service
    print("Starting notification service...")
    # Create background task for notification monitoring
    import asyncio
    from notification_service import check_alerts
    asyncio.create_task(check_alerts())
    
    # Initialize AI agent
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service
    )
    
    yield
    
    # Cleanup
    print("Đang tắt ứng dụng...")
    stop_scheduler()
    print("Services stopped")

app = FastAPI(title="Smart Home AI Agent", lifespan=lifespan)
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
    global session_service, runner

    user_id = request.user_id if request.user_id else str(uuid.uuid4())
    session_id = request.session_id if request.session_id else str(uuid.uuid4())
    
    print(f" Request: '{request.query}' | User: {user_id} | Session: {session_id}")

    try:
        try:
            await session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id
            )
        except Exception:
            pass
        # 3. Chạy Agent
        user_message = types.Content(
            role="user", 
            parts=[types.Part.from_text(text=request.query)]
        )
        final_response_text = "Xin lỗi, tôi không nghe rõ."
        async for event in runner.run_async(
            user_id=user_id, 
            session_id=session_id, 
            new_message=user_message
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text
        print(f"Response: {final_response_text}")
        return ChatResponse(
            response=final_response_text,
            user_id=user_id,     # Trả lại ID để Client lưu cho lần sau
            session_id=session_id
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
# Gắn routers vào app
app.include_router(router, prefix="/api", tags=["SmartHome Chat"])

# Include new API routers
from api import devices, schedules, alerts, rules
app.include_router(devices.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(rules.router, prefix="/api")

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