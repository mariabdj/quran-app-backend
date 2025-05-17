from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from database import get_db
import crud
import schemas # Ensure this imports your schemas.py
from typing import List, Union, Optional

router = APIRouter(
    prefix="/search",
    tags=["Search"]
)

@router.get("/", response_model=Union[List[schemas.AyahResult], schemas.PageInfoResponse])
def new_complex_search(
    mushaf_id: int = Query(..., description="Mushaf ID (1 for Hafs, 2 for Warsh). Example: 1"),
    text: Optional[str] = Query(None, min_length=1, description="Text to search (keyword). Example: 'Allah'"),
    surah: Optional[int] = Query(None, ge=1, le=114, description="Surah number (1-114). Example: 1"),
    page: Optional[int] = Query(None, ge=1, le=604, description="Page number. Example: 2"), # Max page can vary
    verse_number: Optional[int] = Query(None, ge=1, description="Verse number within a surah. Example: 1"), # Max verse varies
    db: Session = Depends(get_db)
):
    """
    Advanced search for Quranic verses.

    **Input Rules:**
    - `mushaf_id` is **required**.
    - At least one of `text`, `surah`, `page`, or `verse_number` must be provided.
    - If `verse_number` is specified, `surah` is also **required**.
    - Cannot search by (`verse_number` AND `surah`) AND `page` simultaneously.
    - Cannot search by `surah` (alone) AND `page` (alone) simultaneously. Provide `text` if combining `surah` and `page` as filters.

    **Output Scenarios:**
    1.  **List of Ayahs (`List[AyahResult]`):**
        - If `text` is provided (alone or with `surah` filter).
        - If `text` and `page` are provided (searches text within that page).
        - If `surah` and `verse_number` are provided (returns the specific ayah).
        - If `text`, `surah`, and `verse_number` are provided (returns the specific ayah if text matches).
    2.  **Page Number (`PageInfoResponse`):**
        - If `surah` is provided alone (returns the starting page of the surah).
        - If `page` is provided alone (validates and returns the page number).
    3.  **Error (HTTPException):**
        - For invalid input combinations or if no results are found.
    """

    # --- Input Validation ---
    if not (text or surah or page or verse_number):
        raise HTTPException(
            status_code=400,
            detail="At least one search parameter (text, surah, page, verse_number) must be provided."
        )

    if verse_number is not None and surah is None:
        raise HTTPException(
            status_code=400,
            detail="Surah (surah number) must be provided if verse_number is specified."
        )

    # Error: verse_number/surah combined with page
    if verse_number is not None and page is not None: # (surah is implied to be with verse_number here)
        raise HTTPException(
            status_code=400,
            detail="Cannot search by a specific verse (surah and verse_number) and a page number simultaneously. Choose one."
        )

    # Error: surah (alone) combined with page (alone)
    # This means text is None, verse_number is None, but both surah and page are given.
    if text is None and verse_number is None and surah is not None and page is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both Surah and Page as primary search criteria simultaneously. "
                   "To search within a surah on a specific page, provide 'text'. "
                   "Otherwise, search by 'surah' alone for its starting page, or 'page' alone."
        )

    # --- Logic for "Surah alone" or "Page alone" to return PageInfoResponse ---

    # Case 1: Surah alone (to get its starting page number)
    if surah is not None and text is None and page is None and verse_number is None:
        page_num_from_surah = crud.get_page_for_surah(db, mushaf_id=mushaf_id, surah_number=surah)
        if page_num_from_surah is None:
            raise HTTPException(
                status_code=404,
                detail=f"Could not determine starting page for Surah {surah} in Mushaf {mushaf_id}. Surah may be invalid or data missing."
            )
        return schemas.PageInfoResponse(page_number=page_num_from_surah)

    # Case 2: Page alone (to validate/return the page number)
    if page is not None and text is None and surah is None and verse_number is None:
        if not crud.check_page_exists(db, mushaf_id=mushaf_id, page_number=page):
            raise HTTPException(
                status_code=404,
                detail=f"Page {page} not found or is invalid for Mushaf {mushaf_id}."
            )
        return schemas.PageInfoResponse(page_number=page)

    # --- Logic for searching Ayahs (returns List[AyahResult]) ---
    # This covers all other valid combinations involving text, or specific verse, or text on page.
    
    # Call the comprehensive search function in crud.py
    ayat_data = crud.search_verses_complex(
        db=db,
        mushaf_id=mushaf_id,
        text=text,
        surah_id=surah,
        page_number=page,
        verse_num=verse_number
    )

    if not ayat_data:
        detail_message = "No matching verses found for the given criteria."
        if text and surah and verse_number:
            detail_message = f"No matching text '{text}' found in Surah {surah}, Verse {verse_number} for Mushaf {mushaf_id}."
        elif text and page:
             detail_message = f"No matching text '{text}' found on Page {page} for Mushaf {mushaf_id}."
        raise HTTPException(status_code=404, detail=detail_message)

    # Format results into List[schemas.AyahResult]
    response_list = []
    for verse in ayat_data:
        ayah_text_content = ""
        if mushaf_id == 1: # Hafs (models.Verse)
            ayah_text_content = verse.text if verse.text is not None else ""
        elif mushaf_id == 2: # Warsh (models.Warsh)
            ayah_text_content = verse.aya_text if verse.aya_text is not None else ""
        
        response_list.append(schemas.AyahResult(verse_id=verse.id, text=ayah_text_content))
        
    return response_list


@router.get("/page/{verse_id}", response_model=schemas.PageInfoResponse,
            summary="Get page number for a specific verse ID",
            description="Retrieves the page number for a given verse ID and Mushaf ID.")
def get_page_number_for_verse(
    verse_id: int = Path(..., description="The ID of the verse (specific to the Mushaf type). Example: 1 (for Hafs), 7 (for Warsh)"),
    mushaf_id: int = Query(..., description="Mushaf ID (1 for Hafs, 2 for Warsh). Example: 1"),
    db: Session = Depends(get_db)
):
    """
    Retrieves the page number where a specific verse (by its ID) is located.
    - **verse_id**: The unique identifier of the verse. This ID is specific to the Mushaf type.
                   For Hafs (mushaf_id=1), this corresponds to `Verse.id` (which is also `Ayah.ayah_index`).
                   For Warsh (mushaf_id=2), this corresponds to `Warsh.id`.
    - **mushaf_id**: Specifies the Quran edition (1 for Hafs, 2 for Warsh).
    """
    page_num = crud.get_page_from_verse_id(db, mushaf_id=mushaf_id, verse_id=verse_id)
    if page_num is None:
        raise HTTPException(
            status_code=404,
            detail=f"Verse with ID {verse_id} not found in Mushaf {mushaf_id}, or page information is not available."
        )
    return schemas.PageInfoResponse(page_number=page_num)

# The original search endpoint, if you had one named "/original/" or similar,
# can be kept or removed based on your needs.
# Example:
# @router.get("/original_search/", response_model=list[schemas.AyahResult], deprecated=True)
# def original_search_function(
#     # parameters...
# ):
#     # logic...
#     pass
