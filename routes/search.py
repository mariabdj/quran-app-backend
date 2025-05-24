from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from database import get_db
import crud # crud.py now contains normalize_arabic_quranic_text_for_comparison
import schemas
from typing import List, Union, Optional

router = APIRouter(
    prefix="/search",
    tags=["Search"]
)

@router.get("/", response_model=Union[List[schemas.AyahResult], schemas.PageInfoResponse])
def new_complex_search(
    mushaf_id: int = Query(..., description="Mushaf ID (1 for Hafs, 2 for Warsh). Example: 1"),
    text: Optional[str] = Query(None, min_length=1, description="Text to search (keyword). Example: 'الرحمان' or 'بسم الله'"),
    surah: Optional[int] = Query(None, ge=1, le=114, description="Surah number (1-114). Example: 1"),
    page: Optional[int] = Query(None, ge=1, le=604, description="Page number. Example: 2"), # Max page can vary
    verse_number: Optional[int] = Query(None, ge=1, description="Verse number within a surah. Example: 1"), # Max verse varies
    db: Session = Depends(get_db)
):
    """
    Advanced search for Quranic verses with precise word matching.
    User's input 'text' is used as-is for word tokenization.
    Database text is normalized on-the-fly for comparison.

    **Input Rules & Output Scenarios are the same as before.**
    """

    # --- Input Validation (same as before) ---
    if not (text or surah or page or verse_number):
        raise HTTPException(status_code=400, detail="At least one search parameter (text, surah, page, verse_number) must be provided.")
    if verse_number is not None and surah is None:
        raise HTTPException(status_code=400, detail="Surah (surah number) must be provided if verse_number is specified.")
    if verse_number is not None and page is not None:
        raise HTTPException(status_code=400, detail="Cannot search by a specific verse (surah and verse_number) and a page number simultaneously.")
    if text is None and verse_number is None and surah is not None and page is not None:
        raise HTTPException(status_code=400, detail="Cannot specify both Surah and Page as primary search criteria without text.")

    # --- Logic for "Surah alone" or "Page alone" (same as before) ---
    if surah is not None and text is None and page is None and verse_number is None:
        page_num_from_surah = crud.get_page_for_surah(db, mushaf_id=mushaf_id, surah_number=surah)
        if page_num_from_surah is None:
            raise HTTPException(status_code=404, detail=f"Could not determine starting page for Surah {surah} in Mushaf {mushaf_id}.")
        return schemas.PageInfoResponse(page_number=page_num_from_surah)

    if page is not None and text is None and surah is None and verse_number is None:
        if not crud.check_page_exists(db, mushaf_id=mushaf_id, page_number=page):
            raise HTTPException(status_code=404, detail=f"Page {page} not found or is invalid for Mushaf {mushaf_id}.")
        return schemas.PageInfoResponse(page_number=page)

    # --- Logic for searching Ayahs ---
    # User's 'text' is passed directly to crud.search_verses_complex
    # The crud function will handle its tokenization and comparison against processed DB text.
    
    ayat_data = crud.search_verses_complex(
        db=db,
        mushaf_id=mushaf_id,
        user_query_text=text, # Pass raw user text
        surah_id=surah,
        page_number=page,
        verse_num=verse_number
    )

    if not ayat_data:
        detail_message = "No matching verses found for the given criteria."
        # (Error messages can be refined based on which specific combination led to no results)
        raise HTTPException(status_code=404, detail=detail_message)

    response_list = []
    for verse_obj in ayat_data:
        ayah_text_content = ""
        verse_id_val = 0
        if mushaf_id == 1: # Hafs (models.Verse)
            ayah_text_content = verse_obj.text if verse_obj.text is not None else "" # Original text
            verse_id_val = verse_obj.id
        elif mushaf_id == 2: # Warsh (models.Warsh)
            ayah_text_content = verse_obj.aya_text if verse_obj.aya_text is not None else "" # Original text
            verse_id_val = verse_obj.id
        
        response_list.append(schemas.AyahResult(verse_id=verse_id_val, text=ayah_text_content))
        
    return response_list


@router.get("/page/{verse_id}", response_model=schemas.PageInfoResponse,
            summary="Get page number for a specific verse ID",
            description="Retrieves the page number for a given verse ID and Mushaf ID.")
def get_page_number_for_verse(
    verse_id: int = Path(..., description="The ID of the verse. For Hafs: Verse.id, For Warsh: Warsh.id"),
    mushaf_id: int = Query(..., description="Mushaf ID (1 for Hafs, 2 for Warsh)."),
    db: Session = Depends(get_db)
):
    page_num = crud.get_page_from_verse_id(db, mushaf_id=mushaf_id, verse_id=verse_id)
    if page_num is None:
        raise HTTPException(status_code=404, detail=f"Verse with ID {verse_id} not found in Mushaf {mushaf_id}, or page info unavailable.")
    return schemas.PageInfoResponse(page_number=page_num)

# +++ NEW ENDPOINT: AYAH ID TO SURAH NAME (same as before) +++
# //////////////CHANGE MARIA (search.py - Added mushaf_id to endpoint)
# +++ UPDATED ENDPOINT: AYAH ID TO SURAH NAME (with mushaf_id) +++
@router.get("/surah-name-by-ayah/{ayah_id}", response_model=schemas.SurahNameResponse,
            summary="Get Surah name for a specific Ayah ID and Mushaf",
            description="Retrieves the Surah name for a given Ayah ID, Mushaf ID, and language ID.")
def get_surah_name_for_ayah(
    ayah_id: int = Path(..., description="The Ayah ID (Verse.id for Hafs, Warsh.id for Warsh). Example: 1"),
    mushaf_id: int = Query(..., description="Mushaf ID (1 for Hafs, 2 for Warsh). Example: 1"),
    language_id: int = Query(..., description="Language ID (9 for Arabic, 38 for English). Example: 9"),
    db: Session = Depends(get_db)
):
    if language_id not in [9, 38]:
        raise HTTPException(status_code=400, detail="Invalid language_id. Supported: 9 (Arabic) and 38 (English).")
    if mushaf_id not in [1, 2]:
        raise HTTPException(status_code=400, detail="Invalid mushaf_id. Supported: 1 (Hafs) and 2 (Warsh).")

    surah_name = crud.get_surah_name_by_ayah_id(db, ayah_id=ayah_id, mushaf_id=mushaf_id, language_id=language_id)

    if surah_name is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Could not find Surah name for Ayah ID {ayah_id} in Mushaf {mushaf_id} with language ID {language_id}."
        )
    return schemas.SurahNameResponse(surah_name=surah_name)

# +++ NEW ENDPOINT: RANDOM AYAH (same as before) +++
@router.get("/random-ayah/", response_model=schemas.RandomAyahResponse,
            summary="Get a random Ayah",
            description="Retrieves a random Ayah (ID and text) from the quran.verse table (Hafs).")
def get_random_ayah(db: Session = Depends(get_db)):
    random_ayah_obj = crud.get_random_ayah_from_verse_table(db)
    if not random_ayah_obj:
        raise HTTPException(status_code=404, detail="Could not retrieve a random Ayah.")
    return schemas.RandomAyahResponse(id=random_ayah_obj.id, text=random_ayah_obj.text or "")
