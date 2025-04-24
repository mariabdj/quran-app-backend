from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
import crud
import schemas

router = APIRouter(
    prefix="/tafsir",
    tags=["Tafsir"]
)


@router.get("/", response_model=schemas.TafsirOut)
def get_tafsir(
    verse_id: int = Query(..., description="ID du verset"),
    language_id: int = Query(..., description="9 = arabe, 38 = anglais"),
    mushaf_id: int = Query(..., description="1 = Hafs, 2 = Warsh"),
    db: Session = Depends(get_db)
):
    tafsir = crud.get_tafsir_logic(db, verse_id, language_id, mushaf_id)

    if tafsir == "warsh":
        # Message personnalisé pour Warsh
        if language_id == 9:
            raise HTTPException(status_code=400, detail="❌ الرجاء التبديل إلى مصحف حفص لعرض التفسير")
        else:
            raise HTTPException(status_code=400, detail="❌ Please switch to Hafs mushaf to view tafsir")

    if not tafsir:
        raise HTTPException(status_code=404, detail="❌ Tafsir not found")

    return tafsir


@router.get("/translation", response_model=schemas.TranslationOut)
def get_translation(
    verse_id: int = Query(..., description="ID du verset"),
    language_id: int = Query(..., description="9 = arabe, 38 = anglais"),
    mushaf_id: int = Query(..., description="1 = Hafs, 2 = Warsh"),
    db: Session = Depends(get_db)
):
    translation = crud.get_translation_logic(db, verse_id, language_id, mushaf_id)

    if translation == "warsh":
        # Message personnalisé pour Warsh
        if language_id == 9:
            raise HTTPException(status_code=400, detail="❌ الرجاء التبديل إلى مصحف حفص لعرض الترجمة")
        else:
            raise HTTPException(status_code=400, detail="❌ Please switch to Hafs mushaf to view translation")

    if translation == "no_arabic":
        raise HTTPException(status_code=400, detail="❌ لا تتوفر ترجمة باللغة العربية")

    if not translation:
        raise HTTPException(status_code=404, detail="❌ Translation not found")

    return translation
