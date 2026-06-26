import os
import logging
import sys
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from routers import upload, routing
from routers import claims as claims_api
from routers import pathway as pathway_api
from routers import chat as chat_api

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Claims Agent API", version="1.0.0")

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(routing.router)
app.include_router(claims_api.router)
app.include_router(pathway_api.router)
app.include_router(chat_api.router)


@app.on_event("startup")
def on_startup():
    logger.info("Initializing database tables and routing configurations...")
    try:
        from services.db import engine, Base
        from services.models import DBRule, DBClaim, DBFile
        
        # Create all tables if they do not exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
        
        # Initialize default routing rules and sync with Pathway
        from services.routing_service import init_routing_service
        init_routing_service()
        logger.info("Routing rules and Pathway pipeline synchronized.")
    except Exception as e:
        logger.error(f"Error during startup database initialization: {e}", exc_info=True)


@app.get("/files/{filename}")
async def get_uploaded_file(filename: str):
    """
    Serve uploaded files. 
    1. Checks the local 'uploads' directory cache first.
    2. If not found locally, queries the database, writes it to the local cache, and serves it.
    3. Returns 404 if not found in either location.
    """
    local_path = os.path.join("uploads", filename)
    
    # 1. Try to serve from local filesystem cache
    if os.path.exists(local_path):
        try:
            with open(local_path, "rb") as f:
                content = f.read()
            content_type = "application/pdf"
            if filename.lower().endswith((".jpg", ".jpeg")):
                content_type = "image/jpeg"
            elif filename.lower().endswith(".png"):
                content_type = "image/png"
            return Response(content=content, media_type=content_type)
        except Exception as e:
            logger.warning(f"Failed to read local cached file {filename}: {e}")
            
    # 2. Try to fetch from database
    from services.db import get_db_session
    from services.models import DBFile
    
    session = get_db_session()
    try:
        db_file = session.query(DBFile).filter(DBFile.filename == filename).first()
        if db_file:
            # Cache locally so subsequent requests and ML processors don't need database calls
            try:
                os.makedirs("uploads", exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(db_file.content)
            except Exception as e:
                logger.warning(f"Failed to cache retrieved database file {filename} locally: {e}")
                
            return Response(content=db_file.content, media_type=db_file.mime_type)
    except Exception as e:
        logger.error(f"Database query error for file {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error retrieving file")
    finally:
        session.close()
        
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/")
def root():
    logger.info("Root endpoint accessed")
    return {"message": "Claims Agent API running ✅"}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Claims Agent API"}
