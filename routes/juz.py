from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import crud
import schemas

router = APIRouter(
    prefix="/juzs",
    tags=["Juzs"]
)

# Liste de tous les Juzs
@router.get("/", response_model=list[schemas.JuzOut])
def get_all_juzs(db: Session = Depends(get_db)):
    return crud.get_all_juzs(db)


# Obtenir la page de début d'un Juz via son first_verse_id
@router.get("/{juz_id}/page", response_model=schemas.VersePageOut)
def get_juz_start_page(juz_id: int, db: Session = Depends(get_db)):
    page = crud.get_juz_start_page(db, juz_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page
