from fastapi import FastAPI
from routes import surah, juz, mushaf, hizb, search, tafsir, recitation, auth, progress
from dotenv import load_dotenv

app = FastAPI()
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
