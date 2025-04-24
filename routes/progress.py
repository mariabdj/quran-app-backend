from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

import schemas
import crud
from database import get_db
from models import Chapters

router = APIRouter(
    prefix="/progress",
    tags=["Progress"]
)

# === 1. Ajouter / Mettre à jour les erreurs fréquentes ===
@router.post("/errors/update")
def add_frequent_errors(data: schemas.FrequentErrorIn, db: Session = Depends(get_db)):
    crud.update_frequent_errors(db, data.user_id, data.mushaf_id, data.ayah_ids)
    return {"message": "Errors updated successfully."}

# === 2. Affichage des erreurs fréquentes avec texte + nombre d’erreurs ===
@router.get("/errors/{user_id}/{mushaf_id}", response_model=List[schemas.FrequentErrorOut])
def get_frequent_errors(user_id: str, mushaf_id: int, db: Session = Depends(get_db)):
    return crud.get_user_frequent_errors(db, user_id, mushaf_id)

# === 3. Ajouter / Mettre à jour la progression sur une sourate ===
@router.post("/surah/update")
def update_surah_progress(data: schemas.SurahProgressIn, db: Session = Depends(get_db)):
    crud.update_surah_progress(db, data.user_id, data.mushaf_id, data.surah_id, data.ayah_ids)
    return {"message": "Surah progress and global memorization updated."}

# === 4. Affichage de la progression sur toutes les sourates (avec noms et pourcentages) ===
@router.get("/surah/{user_id}/{mushaf_id}/{language_id}", response_model=List[schemas.SurahProgressOut])
def get_surah_progress(user_id: str, mushaf_id: int, language_id: int, db: Session = Depends(get_db)):
    model = crud.HafsSurahProgress if mushaf_id == 1 else crud.WarshSurahProgress
    progress_list = db.query(model).filter_by(user_id=user_id).all()

    result = []
    for p in progress_list:
        chapter = db.query(Chapters).filter_by(id=p.surah_id).first()
        if not chapter:
            continue
        surah_name = chapter.name_arabic if language_id == 9 else chapter.name_simple
        result.append(schemas.SurahProgressOut(
            surah_id=p.surah_id,
            surah_name=surah_name,
            percentage=p.percentage,
            created_at=p.created_at,
            updated_at=p.updated_at,
        ))
    return result


# === 5. Affichage du pourcentage global de mémorisation du Coran ===
@router.get("/quran/{user_id}", response_model=schemas.QuranMemorizationOut)
def get_quran_progress(user_id: str, db: Session = Depends(get_db)):
    result = crud.get_memorization_percentage(db, user_id)
    if result:
        return result
    return {"user_id": user_id, "percentage": 0}
