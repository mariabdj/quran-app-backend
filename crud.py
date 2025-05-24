from sqlalchemy.orm import Session
from sqlalchemy import func # For random in get_random_ayah_from_verse_table
import re # For normalization
from models import * # Ensure all your models are imported
from schemas import * # Ensure all your schemas are imported
from typing import List, Optional, Union, Any
from uuid import UUID

# +++ ARABIC TEXT NORMALIZATION FOR QURANIC SCRIPT COMPARISON +++
def normalize_arabic_quranic_text_for_comparison(text: str) -> str:
    if not text:
        return ""
    
    # --- For Debugging Normalization ---
    # print(f"Original DB Text Slice: '{text[:50]}'")

    # Step 1: Remove common diacritics.
    diacritics_pattern = r'[\u064B-\u065F\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED]' 
    text_no_diacritics = re.sub(diacritics_pattern, '', text)
    # print(f"After Diacritic Removal: '{text_no_diacritics[:50]}'")
    
    # Step 2: Specifically replace Dagger Alif (U+0670) with standard Alif (U+0627)
    text_processed_dagger_alif = text_no_diacritics.replace('\u0670', '\u0627') 
    # print(f"After Dagger Alif Norm: '{text_processed_dagger_alif[:50]}'")
    
    # Step 3: Normalize Alif Wasla (ٱ - U+0671) to standard Alif (ا - U+0627)
    text_processed_alefs = text_processed_dagger_alif.replace('\u0671', '\u0627')
    # print(f"After Alif Wasla Norm: '{text_processed_alefs[:50]}'")
    
    # Step 4: Remove Tatweel (ـ - U+0640)
    final_text_no_tatweel = text_processed_alefs.replace('\u0640', '')
    # print(f"After Tatweel Removal: '{final_text_no_tatweel[:50]}'")
    
    # Step 5: Normalize spaces - crucial for consistent word splitting
    # This replaces multiple whitespace characters (including non-breaking spaces if any) with a single space.
    normalized_spaces_text = ' '.join(final_text_no_tatweel.split())
    stripped_text = normalized_spaces_text.strip()
    # print(f"After Space Normalization & Strip: '{stripped_text[:50]}'")
    
    return stripped_text
# +++ END OF NORMALIZATION FUNCTION +++

# Helper function for word sequence matching
def _is_word_subsequence(query_words: List[str], text_words: List[str]) -> bool:
    n = len(query_words)
    m = len(text_words)
    
    # print(f"Comparing query_words: {query_words} (len {n}) with text_words: {text_words} (len {m})")

    if n == 0: return False 
    if n > m: return False

    for i in range(m - n + 1):
        match = True
        for j in range(n):
            if text_words[i+j] != query_words[j]:
                match = False
                break
        if match:
            # print(f"Subsequence found at index {i}")
            return True
    # print("Subsequence not found")
    return False

# --- Authentication (Assumed to be as per your latest version) ---
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
    if not user:
        return None
    for key, value in new_data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


# === CHAPTERS ===
def get_all_chapters(db: Session):
    return db.query(Chapters).order_by(Chapters.chapter_number).all()


def get_chapter_by_id(db: Session, chapter_id: int):
    return db.query(Chapters).filter(Chapters.id == chapter_id).first()


# === JUZS ===
def get_all_juzs(db: Session):
    return db.query(Juzs).order_by(Juzs.juz_number).all()


def get_juz_start_page(db: Session, juz_id: int):
    juz = db.query(Juzs).filter(Juzs.id == juz_id).first()
    if juz is None or juz.first_verse_id is None:
        return None
    # This was returning VersePages, but likely you need the page number.
    # Assuming Hafs context for VersePages. This needs to be mushaf-aware if used generally.
    # For now, let's assume it's for Hafs and we need Ayah table.
    verse_page_info = db.query(Ayah).filter(Ayah.ayah_index == juz.first_verse_id).first()
    return verse_page_info.page_num if verse_page_info else None


# === HIZBS ===
def get_all_hizbs(db: Session):
    return db.query(Hizbs).order_by(Hizbs.hizb_number).all()


def get_hizb_start_page(db: Session, first_verse_id: int):
    # Similar to get_juz_start_page, this needs context or refinement.
    verse_page_info = db.query(Ayah).filter(Ayah.ayah_index == first_verse_id).first()
    return verse_page_info.page_num if verse_page_info else None


# === MUSHAF PAGES ===
def get_mushaf_page(db: Session, page_number: int, mushaf_id_filter: Optional[int] = 20):
    """
    Gets page details from quran.mushaf_pages.
    Note: The original MushafPages table has a mushaf_id column.
    We should filter by it if applicable. Defaulting to 1 (Hafs) for now.
    """
    return db.query(MushafPages).filter(
        MushafPages.page_number == page_number,
        MushafPages.mushaf_id == mushaf_id_filter # Adjust if your table structure differs
    ).first()


# === VERSES ===
def get_verses_in_page(db: Session, first_verse_id: int, last_verse_id: int):
    """ Original function for Hafs, fetches verses for a given range of verse IDs """
    verses = db.query(Verse).filter(
        Verse.id >= first_verse_id,
        Verse.id <= last_verse_id
    ).order_by(Verse.id).all() # Added order_by for consistency

    results = []
    for verse in verses:
        if verse.verse_key and ":" in verse.verse_key:
            try:
                surah_id, verse_number = map(int, verse.verse_key.split(":"))
                if verse_number == 1: # Add Bismillah and Surah name for first verse of Surah
                    surah_info = db.query(Chapters).filter(Chapters.id == surah_id).first() # Use Chapters.id
                    if surah_info and surah_info.name_arabic:
                        # Ensure text is not None before prepending
                        current_text = verse.text if verse.text else ""
                        # For Surah At-Tawbah (ID 9), Bismillah is not recited.
                        bismillah_text = "بسم الله الرحمن الرحيم\n" if surah_id != 9 and surah_info.bismillah_pre else ""
                        verse.text = f"سورة {surah_info.name_arabic.strip()}\n{bismillah_text}{current_text}"
            except ValueError:
                # Skip malformed keys or log an error
                pass
        results.append(verse)
    return results


def get_warsh_verses_in_page(db: Session, page: str):
    """ Original function for Warsh, fetches verses for a given page string """
    # Ensure page is treated as a string for Warsh
    verses = db.query(Warsh).filter(Warsh.page == str(page)).order_by(Warsh.id).all() # Added order_by

    for verse in verses:
        if verse.aya_no == 1 and verse.sura_no is not None: # Add Bismillah and Surah name
            # Surah At-Tawbah (ID 9) does not have Bismillah
            # Warsh table has sura_name_ar, check if Chapters.bismillah_pre applies or if sura_no 9 is universal
            chapter_info = db.query(Chapters).filter(Chapters.chapter_number == verse.sura_no).first()
            bismillah_text = "بسم الله الرحمن الرحيم\n"
            if chapter_info and chapter_info.id == 9: # Assuming chapter_info.id is the surah number for comparison
                 bismillah_text = ""
            elif chapter_info and not chapter_info.bismillah_pre: # If bismillah_pre is explicitly false
                 bismillah_text = ""


            current_text = verse.aya_text if verse.aya_text else ""
            # Use sura_name_ar from Warsh table itself if available and preferred
            surah_title = f"سورة {verse.sura_name_ar.strip()}" if verse.sura_name_ar else f"سورة {chapter_info.name_arabic.strip() if chapter_info else ''}"
            verse.aya_text = f"{surah_title}\n{bismillah_text}{current_text}"
    return verses


# === UPDATED SEARCH LOGIC ===

def get_page_for_surah(db: Session, mushaf_id: int, surah_number: int) -> Optional[int]:
    """
    Gets the page number where a given Surah starts.
    """
    if mushaf_id == 1:  # Hafs
        # Find the first verse of the surah (e.g., verse_key = "surah_number:1")
        first_verse_in_surah = db.query(Verse).filter(Verse.verse_key == f"{surah_number}:1").first()
        if not first_verse_in_surah:
            return None
        # Get its page_num from Ayah table using Verse.id as Ayah.ayah_index
        ayah_entry = db.query(Ayah).filter(Ayah.ayah_index == first_verse_in_surah.id).first()
        return ayah_entry.page_num if ayah_entry else None
    elif mushaf_id == 2:  # Warsh
        # Find the first verse (aya_no = 1) of the surah (sura_no)
        first_verse_in_surah = db.query(Warsh).filter(
            Warsh.sura_no == surah_number,
            Warsh.aya_no == 1
        ).order_by(Warsh.id).first() # Ensure we get the very first one if multiple due to data issues
        if not first_verse_in_surah or first_verse_in_surah.page is None:
            return None
        try:
            return int(first_verse_in_surah.page)
        except ValueError:
            # Handle cases where Warsh.page might not be a simple integer string
            # This might indicate a data issue or a different page numbering scheme
            return None # Or log an error
    return None

def check_page_exists(db: Session, mushaf_id: int, page_number: int) -> bool:
    if mushaf_id == 1: 
        return db.query(Ayah).filter(Ayah.page_num == page_number).first() is not None
    elif mushaf_id == 2: 
        return db.query(Warsh).filter(Warsh.page == str(page_number)).first() is not None
    return False

# //////////////CHANGE MARIA (crud.py - Search logic refinement for single words like "في")
def search_verses_complex(db: Session, mushaf_id: int, user_query_text: Optional[str] = None,
                          surah_id: Optional[int] = None, page_number: Optional[int] = None,
                          verse_num: Optional[int] = None) -> List[Any]:
    
    candidate_verses_query = None
    if mushaf_id == 1: 
        candidate_verses_query = db.query(Verse)
        if verse_num is not None and surah_id is not None:
            verse_key_to_find = f"{surah_id}:{verse_num}"
            candidate_verses_query = candidate_verses_query.filter(Verse.verse_key == verse_key_to_find)
        elif page_number is not None:
            verse_ids_on_page_query = db.query(Ayah.ayah_index).filter(Ayah.page_num == page_number)
            verse_ids_on_page = [v_id for (v_id,) in verse_ids_on_page_query.all()]
            if not verse_ids_on_page: return []
            candidate_verses_query = candidate_verses_query.filter(Verse.id.in_(verse_ids_on_page))
        elif surah_id is not None: 
             candidate_verses_query = candidate_verses_query.filter(Verse.surah == surah_id)
    elif mushaf_id == 2: 
        candidate_verses_query = db.query(Warsh)
        if verse_num is not None and surah_id is not None:
            candidate_verses_query = candidate_verses_query.filter(Warsh.sura_no == surah_id, Warsh.aya_no == verse_num)
        elif page_number is not None:
            candidate_verses_query = candidate_verses_query.filter(Warsh.page == str(page_number))
        elif surah_id is not None: 
            candidate_verses_query = candidate_verses_query.filter(Warsh.sura_no == surah_id)
    else:
        return [] 

    if candidate_verses_query is None: return [] 
    
    all_candidate_verses = candidate_verses_query.order_by(Verse.id if mushaf_id == 1 else Warsh.id).all()
    
    if not user_query_text:
        if (verse_num is not None and surah_id is not None) or \
           (page_number is not None) or \
           (surah_id is not None and not page_number and not verse_num): 
            return all_candidate_verses 
        else: 
            return []

    stripped_user_query = user_query_text.strip()
    if not stripped_user_query: return [] 
    
    user_query_words = stripped_user_query.split()
    if not user_query_words: return [] 

    # print(f"User query words: {user_query_words}") # For debugging user input

    matched_ayat = []
    for ayah_obj in all_candidate_verses: 
        db_text_raw = ""
        if mushaf_id == 1: 
            db_text_raw = ayah_obj.text if ayah_obj.text else ""
        elif mushaf_id == 2: 
            db_text_raw = ayah_obj.aya_text if ayah_obj.aya_text else ""
        
        if not db_text_raw:
            continue

        db_text_for_comparison = normalize_arabic_quranic_text_for_comparison(db_text_raw)
        db_text_words = db_text_for_comparison.split()

        # ---- Debugging prints for matching logic ----
        # if "في" in user_query_words: # Or any specific word you are testing
        #     print(f"--- Ayah ID {ayah_obj.id} (Mushaf {mushaf_id}) ---")
        #     print(f"Raw DB text: '{db_text_raw[:100]}...'")
        #     print(f"Normalized DB text for comparison: '{db_text_for_comparison[:100]}...'")
        #     print(f"DB text words: {db_text_words[:15]}...") # Print first few words
        #     print(f"User query words: {user_query_words}")
        # ---- End Debugging ----
            
        if not db_text_words: 
            continue
            
        if _is_word_subsequence(user_query_words, db_text_words):
            # print(f"MATCH FOUND for Ayah ID {ayah_obj.id}")
            matched_ayat.append(ayah_obj) 
        # else:
            # if "في" in user_query_words:
                # print(f"NO MATCH for Ayah ID {ayah_obj.id}")
            
    return matched_ayat
# //////////////CHANGE MARIA


def get_page_from_verse_id(db: Session, mushaf_id: int, verse_id: int):
    """ Original function to get page from verse ID. """
    if mushaf_id == 1: # Hafs
        # verse_id is Ayah.ayah_index
        ayah_entry = db.query(Ayah).filter(Ayah.ayah_index == verse_id).first()
        if ayah_entry:
            return ayah_entry.page_num
    elif mushaf_id == 2: # Warsh
        # verse_id is Warsh.id
        verse_entry = db.query(Warsh).filter(Warsh.id == verse_id).first()
        if verse_entry and verse_entry.page is not None:
            try:
                return int(verse_entry.page)
            except ValueError:
                return None # Or handle non-integer page strings
    return None

# --- Tafsir, Translation, Recitation, Mushaf Page Creation (Assumed to be as per your latest version) ---
# //CHANGE TO THE OLD (If any of these were different in your first version and not search-related)
# These functions seem standard and likely evolved with your app's features.
def get_tafsir_logic(db: Session, verse_id: int, language_id: int, mushaf_id: int):
    if mushaf_id == 2: # Warsh
        # Tafsir for Warsh might need specific handling if Warsh verse IDs don't map to Tafsirs.verse_id
        # For now, assuming Tafsirs.verse_id can be a Warsh ID or Hafs ID based on context.
        # Or, it might mean no tafsir for Warsh through this function.
        # The prompt says "return 'warsh'", which implies it's a signal not a Tafsir object.
        return "warsh" # Placeholder, as Tafsir table seems Hafs-centric by verse_id
    
    tafsir = db.query(Tafsirs).filter(
        Tafsirs.verse_id == verse_id, # This verse_id needs to be the one used in Tafsirs table.
                                      # If Tafsirs table uses Hafs verse IDs, this needs adjustment for Warsh.
        Tafsirs.language_id == language_id
    ).first()
    return tafsir

def get_translation_logic(db: Session, verse_id: int, language_id: int, mushaf_id: int):
    # This function seems to primarily work for Hafs due to verse_key parsing.
    if mushaf_id == 2: # Warsh
        # Similar to Tafsir, translation for Warsh might need a different approach
        # if Translation table is keyed by Hafs sura/ayah numbers.
        return "warsh" # Placeholder

    if language_id == 9: # Assuming 9 is Arabic, and no translation needed.
        return "no_arabic"

    # For Hafs: verse_id is Verse.id
    verse_obj = db.query(Verse).filter(Verse.id == verse_id).first()
    if not verse_obj or not verse_obj.verse_key or ":" not in verse_obj.verse_key:
        return None

    try:
        sura, ayah = map(int, verse_obj.verse_key.split(":"))
    except ValueError:
        return None

    # Assuming Translation table uses sura and ayah numbers.
    translation = db.query(Translation).filter(
        Translation.sura == sura,
        Translation.ayah == ayah
        # Add language filter if Translation table has language_id
        # Example: Translation.language_id == language_id (if your Translation table has it)
    ).first() # This might need to be .all() if multiple translations for same ayah/lang

    return translation

# === RECITATION INTERVAL SUPPORT ===
def get_verse_count_in_chapter(db: Session, chapter_id: int): # chapter_id is Chapters.id
    chapter = db.query(Chapters).filter(Chapters.id == chapter_id).first()
    return chapter.verses_count if chapter else None

def get_warsh_verse_count(db: Session, surah_id: int): # surah_id is Warsh.sura_no
    # This needs to get the max aya_no for that sura_no or use a dedicated count from Chapters/Warsh metadata
    # The Warsh table has `verse_count` per row, which seems to be total verses in that surah.
    # Taking the first one should be fine if it's consistent.
    verse_info = db.query(Warsh.verse_count).filter(Warsh.sura_no == surah_id).first()
    return verse_info[0] if verse_info else None

def get_verses_by_interval(db: Session, chapter_id: int, start: int, end: int): # chapter_id is Chapters.id (surah number)
    # Filters Hafs verses by surah number (from verse_key) and verse number (from verse_key)
    
    # This is inefficient as it queries all verses. Better to filter in DB if possible.
    # However, verse_key is text. Splitting and casting in SQL is complex and DB-specific.
    # For now, keeping Python filtering.
    # A more performant way would be to construct verse_key strings if format is fixed.
    # E.g. Verse.verse_key.between(f"{chapter_id}:{start}", f"{chapter_id}:{end}") might work if lexicographical.
    # But numeric comparison is safer.
    
    # Alternative: Filter by Verse.surah == chapter_id first, then Python filter for verse number.
    query = db.query(Verse).filter(Verse.surah == chapter_id)
    
    result = []
    for verse in query.all(): # Iterate only over verses of the target surah
        if verse.verse_key and ":" in verse.verse_key:
            try:
                # verse.surah should already match chapter_id
                _, verse_num_str = verse.verse_key.split(":")
                verse_num = int(verse_num_str)
                if start <= verse_num <= end:
                    result.append(verse)
            except ValueError:
                continue 
    # Sort results by verse number (implicit if verse_key is like "S:V" and S is fixed)
    # Or explicitly sort if needed: result.sort(key=lambda v: int(v.verse_key.split(':')[1]))
    return result


def get_warsh_by_interval(db: Session, surah_no: int, start: int, end: int):
    return db.query(Warsh).filter(
        Warsh.sura_no == surah_no,
        Warsh.aya_no >= start,
        Warsh.aya_no <= end
    ).order_by(Warsh.aya_no).all()


# === MUSHAF PAGE CREATION ===
def create_mushaf_page(db: Session, page_number: int, first_verse_id: int, last_verse_id: int, mushaf_id_val: int = 1):
    # Added mushaf_id_val as MushafPages has mushaf_id
    page = MushafPages(
        page_number=page_number,
        first_verse_id=first_verse_id,
        last_verse_id=last_verse_id,
        mushaf_id=mushaf_id_val # Ensure this is passed or defaulted correctly
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return page

# === Frequent Errors Handling ===
def update_frequent_errors(db: Session, user_id: UUID, mushaf_id: int, ayah_ids: List[int]):
    model = HafsError if mushaf_id == 1 else WarshError
    for ayah_id in ayah_ids:
        error = db.query(model).filter_by(user_id=user_id, ayah_id=ayah_id).first()
        if error:
            error.error_count += 1
        else:
            new_error = model(user_id=user_id, ayah_id=ayah_id, error_count=1) # type: ignore
            db.add(new_error)
    db.commit()


def get_user_frequent_errors(db: Session, user_id: UUID, mushaf_id: int) -> List[FrequentErrorOut]:
    model = HafsError if mushaf_id == 1 else WarshError
    error_list = db.query(model).filter_by(user_id=user_id).order_by(model.updated_at.desc()).all() # type: ignore

    results = []
    for error in error_list:
        text_val = ""
        if mushaf_id == 1:
            verse = db.query(Verse.text).filter_by(id=error.ayah_id).first() # Query only text
            text_val = verse[0] if verse else "Ayah text not found"
        else: # mushaf_id == 2 (Warsh)
            verse = db.query(Warsh.aya_text).filter_by(id=error.ayah_id).first() # Query only aya_text
            text_val = verse[0] if verse else "Ayah text not found"
        
        results.append(FrequentErrorOut(
            ayah_id=error.ayah_id,
            text=text_val,
            error_count=error.error_count,
            created_at=error.created_at,
            updated_at=error.updated_at,
        ))
    return results


# === Surah Progress Handling ===
def update_surah_progress(db: Session, user_id: UUID, mushaf_id: int, surah_id: int, ayah_ids: List[int]):
    ProgressModel = HafsSurahProgress if mushaf_id == 1 else WarshSurahProgress
    ErrorModel = HafsError if mushaf_id == 1 else WarshError
    
    # Get total ayahs in the surah
    if mushaf_id == 1: # Hafs
        chapter_info = db.query(Chapters.verses_count).filter(Chapters.id == surah_id).first() # Assuming Chapters.id is surah number
        total_ayahs = chapter_info[0] if chapter_info else 0
    else: # Warsh
        # Get verse_count for this surah_id (sura_no) from Warsh table (it's repeated, take one)
        warsh_surah_info = db.query(Warsh.verse_count).filter(Warsh.sura_no == surah_id).first()
        total_ayahs = warsh_surah_info[0] if warsh_surah_info else 0

    if total_ayahs == 0: # Avoid division by zero if surah info not found
        # Optionally log this situation
        return

    progress = db.query(ProgressModel).filter_by(user_id=user_id, surah_id=surah_id).first()

    if not progress:
        progress = ProgressModel(
            user_id=user_id, # type: ignore
            surah_id=surah_id, # type: ignore
            ayahs_learned=[],
            total_ayahs=total_ayahs, # type: ignore
            percentage=0 
        )
        db.add(progress)
        # db.commit() # Commit later after all updates
        # db.refresh(progress) # Refresh after commit

    current_learned_set = set(progress.ayahs_learned or [])
    for ayah_id in ayah_ids:
        current_learned_set.add(ayah_id)
    
    progress.ayahs_learned = sorted(list(current_learned_set)) # Store as sorted list
    progress.percentage = round((len(progress.ayahs_learned) / total_ayahs) * 100, 2) if total_ayahs > 0 else 0
    
    # Decrement frequent errors for ayahs learned
    for ayah_id in ayah_ids: # Iterate through newly confirmed learned ayahs
        error_to_decrement = db.query(ErrorModel).filter_by(user_id=user_id, ayah_id=ayah_id).first()
        if error_to_decrement:
            error_to_decrement.error_count -= 1
            if error_to_decrement.error_count <= 0:
                db.delete(error_to_decrement)
    
    db.commit() # Commit all changes (progress and error decrements)
    db.refresh(progress) # Refresh progress object if needed later in the same session

    # Update overall Quran memorization percentage
    update_quran_memorization(db, user_id, mushaf_id)


# === Global Memorization ===
def update_quran_memorization(db: Session, user_id: UUID, mushaf_id: int):
    ProgressModel = HafsSurahProgress if mushaf_id == 1 else WarshSurahProgress
    
    all_surah_progress_for_user = db.query(ProgressModel).filter_by(user_id=user_id).all()
    
    total_learned_verses = sum(len(sp.ayahs_learned or []) for sp in all_surah_progress_for_user)
    
    # Total verses in Quran for the mushaf
    # Hafs: 6236 (standard, excluding Bismillahs except Al-Fatiha)
    # Warsh: Varies slightly by counting method, e.g., 6214.
    # It's better to sum total_ayahs from all surahs in Chapters table for Hafs,
    # or derive for Warsh if not readily available as a single number.
    
    grand_total_verses = 0
    if mushaf_id == 1: # Hafs
        # Sum of verses_count from all Chapters
        all_chapters_hafs = db.query(Chapters.verses_count).all()
        grand_total_verses = sum(c[0] for c in all_chapters_hafs if c[0] is not None) # Should be 114 chapters
    else: # Warsh
        # Sum of unique verse_count for each sura_no in Warsh table
        # This is tricky because verse_count is repeated. Need distinct surah verse counts.
        # A simpler approach might be to use a known total or sum from Chapters if applicable to Warsh counts.
        # For now, using the provided fixed numbers.
        grand_total_verses = 6236 if mushaf_id == 1 else 6214 # Using provided totals

    overall_percentage = round((total_learned_verses / grand_total_verses) * 100, 2) if grand_total_verses > 0 else 0

    memorization_record = db.query(QuranMemorization).filter_by(user_id=user_id).first()
    if memorization_record:
        memorization_record.percentage = overall_percentage
    else:
        memorization_record = QuranMemorization(user_id=user_id, percentage=overall_percentage) # type: ignore
        db.add(memorization_record)
    
    db.commit()


def get_memorization_percentage(db: Session, user_id: UUID): # Changed user_id to UUID
    return db.query(QuranMemorization).filter_by(user_id=user_id).first()

# //////////////CHANGE MARIA (Backend CRUD function parameter fix)
# //////////////CHANGE MARIA (crud.py - Added mushaf_id handling for Surah name)
def get_surah_name_by_ayah_id(db: Session, ayah_id: int, mushaf_id: int, language_id: int) -> Optional[str]:
    if mushaf_id == 1: # Hafs
        ayah_model_info = db.query(Ayah.surah_id).filter(Ayah.ayah_index == ayah_id).first()
        if not ayah_model_info or ayah_model_info.surah_id is None:
            return None 
        chapter_info = db.query(Chapters).filter(Chapters.chapter_number == ayah_model_info.surah_id).first()
        if not chapter_info:
            chapter_info = db.query(Chapters).filter(Chapters.id == ayah_model_info.surah_id).first()
            if not chapter_info:
                return None
        if language_id == 9: return chapter_info.name_arabic
        elif language_id == 38: return chapter_info.name_simple
        else: return None
    elif mushaf_id == 2: # Warsh
        warsh_verse_info = db.query(Warsh.sura_name_ar, Warsh.sura_name_en).filter(Warsh.id == ayah_id).first()
        if not warsh_verse_info: return None
        if language_id == 9: return warsh_verse_info.sura_name_ar
        elif language_id == 38: return warsh_verse_info.sura_name_en
        else: return None
    else:
        return None 

def get_random_ayah_from_verse_table(db: Session) -> Optional[Verse]:
    random_ayah = db.query(Verse).order_by(func.random()).first()
    return random_ayah
