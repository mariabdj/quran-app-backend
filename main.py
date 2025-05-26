from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # Add this import
from routes import surah, juz, mushaf, hizb, search, tafsir, recitation, auth, progress
from dotenv import load_dotenv
from fastapi import FastAPI
from ai import router as ai_router # Assuming ai.py is in the same directory or accessible via Python path


app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins or specify only your frontend domain
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)

load_dotenv(dotenv_path=".env")

# Include the updated routers
app.include_router(auth.router)
app.include_router(surah.router)
app.include_router(juz.router)
app.include_router(mushaf.router)
app.include_router(hizb.router)
app.include_router(search.router)
app.include_router(tafsir.router)
app.include_router(recitation.router)
app.include_router(progress.router)
# Include the AI endpoint router
app.include_router(ai_router, prefix="/ai", tags=["AI Recitation Analysis"])

@app.get("/")
async def root():
    return {"message": "Welcome to the Quran Recitation API"}