from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import crud
import schemas

router = APIRouter(
    prefix="/mushaf",
    tags=["Mushaf"]
)

# Afficher une page du Mushaf en Hafs
@router.get("/hafs/{page_number}", response_model=list[schemas.VerseOut])
def get_hafs_mushaf_page(page_number: int, db: Session = Depends(get_db)):
    page = crud.get_mushaf_page(db, page_number)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    verses = crud.get_verses_in_page(db, page.first_verse_id, page.last_verse_id)

    return [schemas.VerseOut(
    id=verse.id,
    verse_key=verse.verse_key,
    text=verse.text,
    text_simple=verse.text_simple,
    surah=verse.surah
) for verse in verses]


# Afficher une page du Mushaf en Warsh
@router.get("/warsh/{page_number}", response_model=list[schemas.WarshVerseOut])
def get_warsh_mushaf_page(page_number: int, db: Session = Depends(get_db)):
    verses = crud.get_warsh_verses_in_page(db, str(page_number))
    if not verses:
        raise HTTPException(status_code=404, detail="No verses found for this page")

    return [
        schemas.WarshVerseOut(
            id=verse.id,
            jozz=verse.jozz,
            page=verse.page,
            sura_no=verse.sura_no,
            sura_name_ar=verse.sura_name_ar,
            aya_no=verse.aya_no,
            aya_text=verse.aya_text,
            text_simple=verse.text_simple,
            verse_count=verse.verse_count
        )
        for verse in verses
    ]
