from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import crud
import schemas

router = APIRouter(
    prefix="/chapters",
    tags=["Chapters"]
)

# Obtenir la liste de toutes les sourates
@router.get("/", response_model=list[schemas.ChapterOut])
def get_all_chapters(db: Session = Depends(get_db)):
    return crud.get_all_chapters(db)


# Obtenir les détails d'une sourate par ID
@router.get("/{chapter_id}", response_model=schemas.ChapterOut)
def get_chapter_by_id(chapter_id: int, db: Session = Depends(get_db)):
    chapter = crud.get_chapter_by_id(db, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter
