from fastapi import FastAPI
from routes import surah, juz, mushaf, hizb, search, tafsir, recitation, auth, progress
from dotenv import load_dotenv

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
