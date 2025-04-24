from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import crud
import schemas
from typing import List, Union

router = APIRouter(
    prefix="/recitation",
    tags=["Recitation"]
)

# Vérifie si l'intervalle de versets est valide pour une sourate donnée
@router.post("/validate_interval")
def validate_interval(data: schemas.RecitationIntervalIn, db: Session = Depends(get_db)):
    if data.mushaf_id == 1:
        verse_count = crud.get_verse_count_in_chapter(db, data.surah_id)
    elif data.mushaf_id == 2:
        verse_count = crud.get_warsh_verse_count(db, data.surah_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid mushaf_id. Use 1 for Hafs or 2 for Warsh.")

    if verse_count is None:
        raise HTTPException(status_code=404, detail="Surah not found")

    if data.from_verse < 1 or data.to_verse > verse_count or data.from_verse > data.to_verse:
        raise HTTPException(status_code=400, detail=f"Invalid interval. Surah has {verse_count} verses.")

    return {"valid": True, "message": "Interval is valid."}


# Récupère les versets à réciter dans l'intervalle Hafs ou warsh
@router.post("/interval", response_model=List[Union[schemas.VerseOut, schemas.WarshVerseOut]])
def get_recitation_verses(data: schemas.RecitationIntervalIn, db: Session = Depends(get_db)):
    if data.mushaf_id == 1:
        return crud.get_verses_by_interval(db, data.surah_id, data.from_verse, data.to_verse)
    elif data.mushaf_id == 2:
        return crud.get_warsh_by_interval(db, data.surah_id, data.from_verse, data.to_verse)
    else:
        raise HTTPException(status_code=400, detail="Invalid mushaf_id. Use 1 for Hafs or 2 for Warsh.")
