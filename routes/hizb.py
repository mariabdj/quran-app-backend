from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import crud
import schemas

router = APIRouter(
    prefix="/hizbs",
    tags=["Hizbs"]
)

# Liste de tous les Hizbs
@router.get("/", response_model=list[schemas.HizbOut])
def get_all_hizbs(db: Session = Depends(get_db)):
    return crud.get_all_hizbs(db)


# Obtenir la page de début d'un Hizb via son first_verse_id
@router.get("/{hizb_id}/page", response_model=schemas.VersePageOut)
def get_hizb_start_page(hizb_id: int, db: Session = Depends(get_db)):
    hizb = crud.get_hizb_start_page(db, hizb_id)
    if not hizb:
        raise HTTPException(status_code=404, detail="Hizb or page not found")
    return hizb
