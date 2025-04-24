from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from database import get_db
import crud
import schemas

router = APIRouter(
    prefix="/search",
    tags=["Search"]
)

@router.get("/", response_model=list[schemas.SearchResult])
def search(
    mushaf_id: int = Query(..., description="1 for Hafs, 2 for Warsh"),
    keyword: str = Query(..., description="Text to search"),
    surah_id: int = Query(None, description="Optional Surah ID"),
    db: Session = Depends(get_db)
):
    results = crud.search_in_mushaf(db, mushaf_id=mushaf_id, keyword=keyword, surah_id=surah_id)

    if not results:
        raise HTTPException(status_code=404, detail="No matching verses found")

    return [
        schemas.SearchResult(
            verse_id=verse.id,
            text=verse.text if mushaf_id == 1 else verse.aya_text
        ) for verse in results
    ]


@router.get("/page/{verse_id}")
def get_page_number(
    mushaf_id: int = Query(..., description="1 for Hafs, 2 for Warsh"),
    verse_id: int = Path(..., description="Verse ID to locate"), 
    db: Session = Depends(get_db)
):
    page = crud.get_page_from_verse_id(db, mushaf_id=mushaf_id, verse_id=verse_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Verse not found or page not set")
    return {"page_number": page}

