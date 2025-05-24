from sqlalchemy.orm import Session
from sqlalchemy import func # For random in get_random_ayah_from_verse_table
import re # For normalization
from models import * # Ensure all your models are imported
from schemas import * # Ensure all your schemas are imported
from typing import List, Optional, Union, Any
from uuid import UUID

# +++ ARABIC TEXT NORMALIZATION FOR QURANIC SCRIPT COMPARISON (Corrected for Dagger Alif) +++
def normalize_arabic_quranic_text_for_comparison(text: str) -> str:
    """
    Normalizes Quranic Arabic text from the database for comparison purposes.
    - Removes common diacritics (tashkeel).
    - Converts Dagger Alif (ٰ - U+0670) to a standard Alif (ا - U+0627). This is key.
    - Converts Alif Wasla (ٱ - U+0671) to a standard Alif (ا - U+0627).
    - Does NOT convert ة to ه or ى to ي.
    - Removes Tatweel (ـ - U+0640).
    """
    if not text:
        return ""

    # Step 1: Remove common diacritics.
    # The range U+064B to U+065F covers Fathatan to Sukun.
    # Quranic annotation marks (like small high seen, etc.) are in U+06D6 to U+06ED.
    # CRITICAL: Ensure Dagger Alif (U+0670) is NOT in this removal pattern.
    diacritics_pattern = r'[\u064B-\u065F\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED]' # Excludes U+0670
    text_no_diacritics = re.sub(diacritics_pattern, '', text)
    
    # Step 2: Specifically replace Dagger Alif (U+0670) with standard Alif (U+0627)
    # This ensures 'الرحمان' matching.
    text_processed_dagger_alif = text_no_diacritics.replace('\u0670', '\u0627') 
    
    # Step 3: Normalize Alif Wasla (ٱ - U+0671) to standard Alif (ا - U+0627)
    text_processed_alefs = text_processed_dagger_alif.replace('\u0671', '\u0627')
    
    # Step 4: Remove Tatweel (ـ - U+0640)
    final_text = text_processed_alefs.replace('\u0640', '')
    
    # Step 5: Normalize spaces
    final_text = ' '.join(final_text.split())
    return final_text.strip()
# +++ END OF NORMALIZATION FUNCTION +++

# Helper function for word sequence matching (remains the same)
def _is_word_subsequence(query_words: List[str], text_words: List[str]) -> bool:
    n = len(query_words)
    m = len(text_words)
    if n == 0: return False # An empty query should not match anything
    if n > m: return False
    for i in range(m - n + 1):
        match = True
        for j in range(n):
            if text_words[i+j] != query_words[j]:
                match = False
                break
        if match: return True
    return False

# --- Authentication ---
def get_user_by_username(db: Session, username: str):
    return db.query(AppUser).filter(AppUser.username == username).first()

def create_app_user(db: Session, user_id: UUID, username: str, email: str, phone: str, mushaf_id: int):
    user = AppUser(id=user_id, username=username, email=email, phone=phone, mushaf_id=mushaf_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user_info(db: Session, user_id: UUID, new_data: dict):
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user: return None
    for key, value in new_data.items(): setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

# --- Chapters, Juzs, Hizbs, Mushaf Pages (Structure remains the same) ---
def get_all_chapters(db: Session):
    return db.query(Chapters).order_by(Chapters.chapter_number).all()

def get_chapter_by_id(db: Session, chapter_id: int):
    return db.query(Chapters).filter(Chapters.id == chapter_id).first()

def get_all_juzs(db: Session):
    return db.query(Juzs).order_by(Juzs.juz_number).all()

def get_juz_start_page(db: Session, juz_id: int):
    juz = db.query(Juzs).filter(Juzs.id == juz_id).first()
    if juz is None or juz.first_verse_id is None: return None
    # Assuming Ayah.ayah_index maps to Verse.id for Hafs
    verse_page_info = db.query(Ayah).filter(Ayah.ayah_index == juz.first_verse_id).first()
    return verse_page_info.page_num if verse_page_info else None

def get_all_hizbs(db: Session):
    return db.query(Hizbs).order_by(Hizbs.hizb_number).all()

def get_hizb_start_page(db: Session, first_verse_id: int):
    verse_page_info = db.query(Ayah).filter(Ayah.ayah_index == first_verse_id).first()
    return verse_page_info.page_num if verse_page_info else None

def get_mushaf_page(db: Session, page_number: int, mushaf_id_filter: Optional[int] = 1):
    return db.query(MushafPages).filter(
        MushafPages.page_number == page_number,
        MushafPages.mushaf_id == mushaf_id_filter
    ).first()

# --- Verses (Display Logic - for fetching pages, Bismillah etc. remains the same) ---
def get_verses_in_page(db: Session, first_verse_id: int, last_verse_id: int):
    verses_query = db.query(Verse).filter(
        Verse.id >= first_verse_id,
        Verse.id <= last_verse_id
    ).order_by(Verse.id)
    
    verses_on_page = verses_query.all()
    results = []
    for verse_obj in verses_on_page: # Use verse_obj to avoid conflict
        # Create a mutable copy for display modification if needed
        display_verse = Verse(
            id=verse_obj.id, 
            verse_key=verse_obj.verse_key, 
            text=verse_obj.text, # Start with original text
            text_simple=verse_obj.text_simple, 
            surah=verse_obj.surah
        )
        if display_verse.verse_key and ":" in display_verse.verse_key:
            try:
                surah_id_val, verse_number_val = map(int, display_verse.verse_key.split(":"))
                if verse_number_val == 1:
                    surah_info = db.query(Chapters).filter(Chapters.id == surah_id_val).first() # Assuming Chapters.id is the surah number linkage
                    if surah_info and surah_info.name_arabic:
                        current_text = display_verse.text if display_verse.text else ""
                        bismillah_text_val = "بسم الله الرحمن الرحيم\n" if surah_id_val != 9 and (surah_info.bismillah_pre is True) else ""
                        display_verse.text = f"سورة {surah_info.name_arabic.strip()}\n{bismillah_text_val}{current_text}"
            except ValueError: 
                pass # Malformed verse_key
        results.append(display_verse)
    return results

def get_warsh_verses_in_page(db: Session, page: str):
    verses_query = db.query(Warsh).filter(Warsh.page == str(page)).order_by(Warsh.id)
    verses_on_page = verses_query.all()
    results = []
    for verse_obj in verses_on_page:
        display_verse = Warsh( # Create a mutable copy
            id=verse_obj.id, jozz=verse_obj.jozz, page=verse_obj.page, sura_no=verse_obj.sura_no,
            sura_name_en=verse_obj.sura_name_en, sura_name_ar=verse_obj.sura_name_ar,
            line_start=verse_obj.line_start, line_end=verse_obj.line_end, aya_no=verse_obj.aya_no,
            aya_text=verse_obj.aya_text, # Start with original text
            text_simple=verse_obj.text_simple, verse_count=verse_obj.verse_count
        )
        if display_verse.aya_no == 1 and display_verse.sura_no is not None:
            chapter_info = db.query(Chapters).filter(Chapters.chapter_number == display_verse.sura_no).first()
            bismillah_text_val = "بسم الله الرحمن الرحيم\n"
            if chapter_info:
                if chapter_info.id == 9: # Surah At-Tawbah
                    bismillah_text_val = ""
                elif chapter_info.bismillah_pre is False:
                    bismillah_text_val = ""
            
            current_text = display_verse.aya_text if display_verse.aya_text else ""
            surah_title = f"سورة {display_verse.sura_name_ar.strip()}" if display_verse.sura_name_ar else (f"سورة {chapter_info.name_arabic.strip()}" if chapter_info and chapter_info.name_arabic else "سورة")
            display_verse.aya_text = f"{surah_title}\n{bismillah_text_val}{current_text}"
        results.append(display_verse)
    return results

# --- Search Logic ---
def get_page_for_surah(db: Session, mushaf_id: int, surah_number: int) -> Optional[int]:
    if mushaf_id == 1: # Hafs
        first_verse_in_surah = db.query(Verse).filter(Verse.verse_key == f"{surah_number}:1").first()
        if not first_verse_in_surah: return None
        ayah_entry = db.query(Ayah).filter(Ayah.ayah_index == first_verse_in_surah.id).first()
        return ayah_entry.page_num if ayah_entry else None
    elif mushaf_id == 2: # Warsh
        first_verse_in_surah = db.query(Warsh).filter(Warsh.sura_no == surah_number, Warsh.aya_no == 1).order_by(Warsh.id).first()
        if not first_verse_in_surah or first_verse_in_surah.page is None: return None
        try: return int(first_verse_in_surah.page)
        except ValueError: return None
    return None

def check_page_exists(db: Session, mushaf_id: int, page_number: int) -> bool:
    if mushaf_id == 1: # Hafs
        return db.query(Ayah).filter(Ayah.page_num == page_number).first() is not None
    elif mushaf_id == 2: # Warsh
        return db.query(Warsh).filter(Warsh.page == str(page_number)).first() is not None
    return False

def search_verses_complex(db: Session, mushaf_id: int, user_query_text: Optional[str] = None,
                          surah_id: Optional[int] = None, page_number: Optional[int] = None,
                          verse_num: Optional[int] = None) -> List[Any]:
    
    candidate_verses_query = None
    # Initial DB query to narrow down candidates if possible
    if mushaf_id == 1: # Hafs
        candidate_verses_query = db.query(Verse)
        if verse_num is not None and surah_id is not None:
            verse_key_to_find = f"{surah_id}:{verse_num}"
            candidate_verses_query = candidate_verses_query.filter(Verse.verse_key == verse_key_to_find)
        elif page_number is not None:
            # Get verse IDs for the page from Ayah table (assuming Ayah.ayah_index maps to Verse.id)
            verse_ids_on_page_query = db.query(Ayah.ayah_index).filter(Ayah.page_num == page_number)
            verse_ids_on_page = [v_id for (v_id,) in verse_ids_on_page_query.all()]
            if not verse_ids_on_page: return []
            candidate_verses_query = candidate_verses_query.filter(Verse.id.in_(verse_ids_on_page))
        elif surah_id is not None: # If surah_id is provided, filter by it
             candidate_verses_query = candidate_verses_query.filter(Verse.surah == surah_id)
        # If only user_query_text, query remains broad for now.

    elif mushaf_id == 2: # Warsh
        candidate_verses_query = db.query(Warsh)
        if verse_num is not None and surah_id is not None:
            candidate_verses_query = candidate_verses_query.filter(Warsh.sura_no == surah_id, Warsh.aya_no == verse_num)
        elif page_number is not None:
            candidate_verses_query = candidate_verses_query.filter(Warsh.page == str(page_number))
        elif surah_id is not None: # If surah_id is provided, filter by it
            candidate_verses_query = candidate_verses_query.filter(Warsh.sura_no == surah_id)
    else:
        return [] # Invalid mushaf_id

    if candidate_verses_query is None: return [] # Should be caught by mushaf_id check
    
    # Fetch all candidate verses based on preliminary filters
    # Ordering helps in consistent testing/debugging if needed
    all_candidate_verses = candidate_verses_query.order_by(Verse.id if mushaf_id == 1 else Warsh.id).all()
    
    # If no text query, and we had specific verse/page, results are ready
    if not user_query_text:
        if (verse_num is not None and surah_id is not None) or \
           (page_number is not None) or \
           (surah_id is not None and not page_number and not verse_num): # Case: list all verses of a surah
            return all_candidate_verses # Return all verses from the surah/page/specific verse
        else: # No text query and no other specific filters that would list multiple ayahs.
              # This path is less likely given endpoint logic which handles page_for_surah etc.
            return []


    # Process text query: Python-based word sequence matching
    stripped_user_query = user_query_text.strip()
    if not stripped_user_query: return [] # Empty text query after strip
    
    user_query_words = stripped_user_query.split()
    if not user_query_words: return [] # Should not happen if stripped_user_query is not empty

    matched_ayat = []
    for ayah_obj in all_candidate_verses: # Iterate over already filtered candidates
        db_text_raw = ""
        if mushaf_id == 1: # Hafs
            db_text_raw = ayah_obj.text if ayah_obj.text else ""
        elif mushaf_id == 2: # Warsh
            db_text_raw = ayah_obj.aya_text if ayah_obj.aya_text else ""
        
        if not db_text_raw:
            continue

        # Normalize the database text for comparison using the corrected function
        db_text_for_comparison = normalize_arabic_quranic_text_for_comparison(db_text_raw)
        db_text_words = db_text_for_comparison.split()

        if not db_text_words: # Skip if DB text becomes empty after normalization
            continue
            
        # Perform word sequence matching
        if _is_word_subsequence(user_query_words, db_text_words):
            matched_ayat.append(ayah_obj) # Add the original ayah object
            
    return matched_ayat


def get_page_from_verse_id(db: Session, mushaf_id: int, verse_id: int):
    if mushaf_id == 1: # Hafs
        ayah_entry = db.query(Ayah).filter(Ayah.ayah_index == verse_id).first()
        if ayah_entry: return ayah_entry.page_num
    elif mushaf_id == 2: # Warsh
        verse_entry = db.query(Warsh).filter(Warsh.id == verse_id).first()
        if verse_entry and verse_entry.page is not None:
            try: return int(verse_entry.page)
            except ValueError: return None
    return None

# --- Tafsir, Translation, Recitation, Mushaf Page Creation (Structure remains the same) ---
def get_tafsir_logic(db: Session, verse_id: int, language_id: int, mushaf_id: int):
    if mushaf_id == 2: return "warsh" 
    tafsir = db.query(Tafsirs).filter(Tafsirs.verse_id == verse_id, Tafsirs.language_id == language_id).first()
    return tafsir

def get_translation_logic(db: Session, verse_id: int, language_id: int, mushaf_id: int):
    if mushaf_id == 2: return "warsh"
    if language_id == 9: return "no_arabic" # Assuming 9 is Arabic
    verse_obj = db.query(Verse).filter(Verse.id == verse_id).first()
    if not verse_obj or not verse_obj.verse_key or ":" not in verse_obj.verse_key: return None
    try: sura, ayah_num = map(int, verse_obj.verse_key.split(":"))
    except ValueError: return None
    # Assuming Translation table has sura, ayah, and a language filter if needed
    translation = db.query(Translation).filter(Translation.sura == sura, Translation.ayah == ayah_num).first()
    return translation

def get_verse_count_in_chapter(db: Session, chapter_id: int): # chapter_id is Chapters.id
    chapter = db.query(Chapters).filter(Chapters.id == chapter_id).first()
    return chapter.verses_count if chapter else None

def get_warsh_verse_count(db: Session, surah_id: int): # surah_id is Warsh.sura_no
    verse_info = db.query(Warsh.verse_count).filter(Warsh.sura_no == surah_id).first()
    return verse_info[0] if verse_info else None

def get_verses_by_interval(db: Session, chapter_id: int, start: int, end: int): # chapter_id is Chapters.id (surah number)
    query = db.query(Verse).filter(Verse.surah == chapter_id) # Assuming Verse.surah holds surah number
    result = []
    for verse_obj in query.all():
        if verse_obj.verse_key and ":" in verse_obj.verse_key:
            try:
                _, verse_num_str = verse_obj.verse_key.split(":")
                verse_num_val = int(verse_num_str)
                if start <= verse_num_val <= end: result.append(verse_obj)
            except ValueError: continue 
    return result

def get_warsh_by_interval(db: Session, surah_no: int, start: int, end: int):
    return db.query(Warsh).filter(
        Warsh.sura_no == surah_no,
        Warsh.aya_no >= start,
        Warsh.aya_no <= end
    ).order_by(Warsh.aya_no).all()

def create_mushaf_page(db: Session, page_number: int, first_verse_id: int, last_verse_id: int, mushaf_id_val: int = 1):
    page = MushafPages(
        page_number=page_number,
        first_verse_id=first_verse_id,
        last_verse_id=last_verse_id,
        mushaf_id=mushaf_id_val
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return page

# --- Frequent Errors & Progress Handling (Structure remains the same) ---
def update_frequent_errors(db: Session, user_id: UUID, mushaf_id: int, ayah_ids: List[int]):
    model = HafsError if mushaf_id == 1 else WarshError
    for ayah_id_val in ayah_ids: # Renamed to avoid conflict
        error = db.query(model).filter_by(user_id=user_id, ayah_id=ayah_id_val).first()
        if error: error.error_count += 1
        else: db.add(model(user_id=user_id, ayah_id=ayah_id_val, error_count=1)) # type: ignore
    db.commit()

def get_user_frequent_errors(db: Session, user_id: UUID, mushaf_id: int) -> List[FrequentErrorOut]:
    model = HafsError if mushaf_id == 1 else WarshError
    error_list = db.query(model).filter_by(user_id=user_id).order_by(model.updated_at.desc()).all() # type: ignore
    results = []
    for error_item in error_list: # Renamed to avoid conflict
        text_val = ""
        if mushaf_id == 1:
            verse_obj = db.query(Verse.text).filter_by(id=error_item.ayah_id).first() # Renamed
            text_val = verse_obj[0] if verse_obj else "Ayah text not found"
        else: 
            verse_obj = db.query(Warsh.aya_text).filter_by(id=error_item.ayah_id).first() # Renamed
            text_val = verse_obj[0] if verse_obj else "Ayah text not found"
        results.append(FrequentErrorOut(
            ayah_id=error_item.ayah_id, text=text_val, error_count=error_item.error_count, 
            created_at=error_item.created_at, updated_at=error_item.updated_at
        ))
    return results

def update_surah_progress(db: Session, user_id: UUID, mushaf_id: int, surah_id_param: int, ayah_ids: List[int]): # Renamed surah_id
    ProgressModel = HafsSurahProgress if mushaf_id == 1 else WarshSurahProgress
    ErrorModel = HafsError if mushaf_id == 1 else WarshError
    total_ayahs = 0
    if mushaf_id == 1:
        chapter_info = db.query(Chapters.verses_count).filter(Chapters.id == surah_id_param).first()
        total_ayahs = chapter_info[0] if chapter_info else 0
    else: 
        warsh_surah_info = db.query(Warsh.verse_count).filter(Warsh.sura_no == surah_id_param).first()
        total_ayahs = warsh_surah_info[0] if warsh_surah_info else 0
    if total_ayahs == 0: return

    progress = db.query(ProgressModel).filter_by(user_id=user_id, surah_id=surah_id_param).first()
    if not progress:
        progress = ProgressModel(user_id=user_id, surah_id=surah_id_param, ayahs_learned=[], total_ayahs=total_ayahs, percentage=0) # type: ignore
        db.add(progress)
    
    current_learned_set = set(progress.ayahs_learned or [])
    for ayah_id_val in ayah_ids: current_learned_set.add(ayah_id_val) # Renamed
    
    progress.ayahs_learned = sorted(list(current_learned_set))
    progress.percentage = round((len(progress.ayahs_learned) / total_ayahs) * 100, 2) if total_ayahs > 0 else 0
    
    for ayah_id_val in ayah_ids: # Renamed
        error_to_decrement = db.query(ErrorModel).filter_by(user_id=user_id, ayah_id=ayah_id_val).first()
        if error_to_decrement:
            error_to_decrement.error_count -= 1
            if error_to_decrement.error_count <= 0: db.delete(error_to_decrement)
    db.commit()
    if progress: db.refresh(progress) # Ensure progress is not None
    update_quran_memorization(db, user_id, mushaf_id)

def update_quran_memorization(db: Session, user_id: UUID, mushaf_id: int):
    ProgressModel = HafsSurahProgress if mushaf_id == 1 else WarshSurahProgress
    all_surah_progress_for_user = db.query(ProgressModel).filter_by(user_id=user_id).all()
    total_learned_verses = sum(len(sp.ayahs_learned or []) for sp in all_surah_progress_for_user)
    grand_total_verses = 0
    if mushaf_id == 1:
        all_chapters_hafs = db.query(Chapters.verses_count).all()
        grand_total_verses = sum(c[0] for c in all_chapters_hafs if c[0] is not None)
    else: grand_total_verses = 6214 # Placeholder for Warsh total
    
    overall_percentage = round((total_learned_verses / grand_total_verses) * 100, 2) if grand_total_verses > 0 else 0
    memorization_record = db.query(QuranMemorization).filter_by(user_id=user_id).first()
    if memorization_record:
        memorization_record.percentage = overall_percentage
    else:
        memorization_record = QuranMemorization(user_id=user_id, percentage=overall_percentage) # type: ignore
        db.add(memorization_record)
    db.commit()

def get_memorization_percentage(db: Session, user_id: UUID):
    return db.query(QuranMemorization).filter_by(user_id=user_id).first()

# --- New CRUD Functions for Additional Endpoints (Structure remains the same) ---
# //////////////CHANGE MARIA (Backend CRUD function parameter fix)
# //////////////CHANGE MARIA (crud.py - Added mushaf_id handling for Surah name)
def get_surah_name_by_ayah_id(db: Session, ayah_id: int, mushaf_id: int, language_id: int) -> Optional[str]:
    """
    Retrieves the Surah name for a given Ayah ID, Mushaf ID, and language.
    - For Hafs (mushaf_id=1), ayah_id is Ayah.ayah_index (which maps to Verse.id).
    - For Warsh (mushaf_id=2), ayah_id is Warsh.id.
    """
    if mushaf_id == 1: # Hafs
        # Ayah.ayah_index is used to find the surah_id (chapter number)
        # Then Chapters table is used for the name.
        # The input 'ayah_id' for Hafs is expected to be the Verse.id / Ayah.ayah_index.
        ayah_model_info = db.query(Ayah.surah_id).filter(Ayah.ayah_index == ayah_id).first()
        if not ayah_model_info or ayah_model_info.surah_id is None:
            return None 

        # ayah_model_info.surah_id is the chapter_number
        chapter_info = db.query(Chapters).filter(Chapters.chapter_number == ayah_model_info.surah_id).first()

        if not chapter_info:
            # Fallback if Ayah.surah_id was meant to be Chapters.id (less common but good to check)
            chapter_info = db.query(Chapters).filter(Chapters.id == ayah_model_info.surah_id).first()
            if not chapter_info:
                return None

        if language_id == 9: # Arabic
            return chapter_info.name_arabic
        elif language_id == 38: # English
            return chapter_info.name_simple
        else:
            return None

    elif mushaf_id == 2: # Warsh
        # The input 'ayah_id' for Warsh is Warsh.id (the primary key of the Warsh table).
        warsh_verse_info = db.query(Warsh.sura_name_ar, Warsh.sura_name_en).filter(Warsh.id == ayah_id).first()
        if not warsh_verse_info:
            return None

        if language_id == 9: # Arabic
            return warsh_verse_info.sura_name_ar
        elif language_id == 38: # English
            return warsh_verse_info.sura_name_en
        else:
            return None
    else:
        return None # Unsupported mushaf_id

def get_random_ayah_from_verse_table(db: Session) -> Optional[Verse]:
    # func.random() is for PostgreSQL. For other DBs, it might be rand() or similar.
    random_ayah = db.query(Verse).order_by(func.random()).first()
    return random_ayah
