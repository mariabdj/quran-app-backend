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
    if not user: return None
    for key, value in new_data.items(): setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

# --- Chapters, Juzs, Hizbs (Assumed to be as per your latest version) ---
def get_all_chapters(db: Session):
    return db.query(Chapters).order_by(Chapters.chapter_number).all()

def get_chapter_by_id(db: Session, chapter_id: int):
    return db.query(Chapters).filter(Chapters.id == chapter_id).first()

def get_all_juzs(db: Session):
    return db.query(Juzs).order_by(Juzs.juz_number).all()

def get_juz_start_page(db: Session, juz_id: int):
    juz = db.query(Juzs).filter(Juzs.id == juz_id).first()
    if juz is None or juz.first_verse_id is None: return None
    verse_page_info = db.query(Ayah).filter(Ayah.ayah_index == juz.first_verse_id).first()
    return verse_page_info.page_num if verse_page_info else None

def get_all_hizbs(db: Session):
    return db.query(Hizbs).order_by(Hizbs.hizb_number).all()

def get_hizb_start_page(db: Session, first_verse_id: int): # first_verse_id here is likely Hizbs.first_verse_id
    verse_page_info = db.query(Ayah).filter(Ayah.ayah_index == first_verse_id).first()
    return verse_page_info.page_num if verse_page_info else None

# //CHANGE TO THE OLD (If this was different in your absolute first version and you need that specific old structure for non-search reasons)
# This function seems standard for fetching Mushaf page details.
def get_mushaf_page(db: Session, page_number: int, mushaf_id_filter: Optional[int] = 1):
    return db.query(MushafPages).filter(
        MushafPages.page_number == page_number,
        MushafPages.mushaf_id == mushaf_id_filter
    ).first()

# --- Verses (Display Logic - Bismillah etc. Assumed to be as per your latest version) ---
def get_verses_in_page(db: Session, first_verse_id: int, last_verse_id: int):
    verses_query = db.query(Verse).filter(
        Verse.id >= first_verse_id,
        Verse.id <= last_verse_id
    ).order_by(Verse.id)
    
    verses_on_page = verses_query.all()
    results = []
    for verse_obj in verses_on_page: 
        display_verse = Verse(
            id=verse_obj.id, 
            verse_key=verse_obj.verse_key, 
            text=verse_obj.text, 
            text_simple=verse_obj.text_simple, 
            surah=verse_obj.surah
        )
        if display_verse.verse_key and ":" in display_verse.verse_key:
            try:
                surah_id_val, verse_number_val = map(int, display_verse.verse_key.split(":"))
                if verse_number_val == 1:
                    surah_info = db.query(Chapters).filter(Chapters.id == surah_id_val).first() 
                    if surah_info and surah_info.name_arabic:
                        current_text = display_verse.text if display_verse.text else ""
                        bismillah_text_val = "بسم الله الرحمن الرحيم\n" if surah_id_val != 9 and (surah_info.bismillah_pre is True) else ""
                        display_verse.text = f"سورة {surah_info.name_arabic.strip()}\n{bismillah_text_val}{current_text}"
            except ValueError: 
                pass 
        results.append(display_verse)
    return results

def get_warsh_verses_in_page(db: Session, page: str):
    verses_query = db.query(Warsh).filter(Warsh.page == str(page)).order_by(Warsh.id)
    verses_on_page = verses_query.all()
    results = []
    for verse_obj in verses_on_page:
        display_verse = Warsh( 
            id=verse_obj.id, jozz=verse_obj.jozz, page=verse_obj.page, sura_no=verse_obj.sura_no,
            sura_name_en=verse_obj.sura_name_en, sura_name_ar=verse_obj.sura_name_ar,
            line_start=verse_obj.line_start, line_end=verse_obj.line_end, aya_no=verse_obj.aya_no,
            aya_text=verse_obj.aya_text, 
            text_simple=verse_obj.text_simple, verse_count=verse_obj.verse_count
        )
        if display_verse.aya_no == 1 and display_verse.sura_no is not None:
            chapter_info = db.query(Chapters).filter(Chapters.chapter_number == display_verse.sura_no).first()
            bismillah_text_val = "بسم الله الرحمن الرحيم\n"
            if chapter_info:
                if chapter_info.id == 9: 
                    bismillah_text_val = ""
                elif chapter_info.bismillah_pre is False:
                    bismillah_text_val = ""
            
            current_text = display_verse.aya_text if display_verse.aya_text else ""
            surah_title_str = f"سورة {display_verse.sura_name_ar.strip()}" if display_verse.sura_name_ar else (f"سورة {chapter_info.name_arabic.strip()}" if chapter_info and chapter_info.name_arabic else "سورة")
            display_verse.aya_text = f"{surah_title_str}\n{bismillah_text_val}{current_text}"
        results.append(display_verse)
    return results

# --- Search Related Functions ---
def get_page_for_surah(db: Session, mushaf_id: int, surah_number: int) -> Optional[int]:
    if mushaf_id == 1: 
        first_verse_in_surah = db.query(Verse).filter(Verse.verse_key == f"{surah_number}:1").first()
        if not first_verse_in_surah: return None
        ayah_entry = db.query(Ayah).filter(Ayah.ayah_index == first_verse_in_surah.id).first()
        return ayah_entry.page_num if ayah_entry else None
    elif mushaf_id == 2: 
        first_verse_in_surah = db.query(Warsh).filter(Warsh.sura_no == surah_number, Warsh.aya_no == 1).order_by(Warsh.id).first()
        if not first_verse_in_surah or first_verse_in_surah.page is None: return None
        try: return int(first_verse_in_surah.page)
        except ValueError: return None
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
    if mushaf_id == 1: 
        ayah_entry = db.query(Ayah).filter(Ayah.ayah_index == verse_id).first()
        if ayah_entry: return ayah_entry.page_num
    elif mushaf_id == 2: 
        verse_entry = db.query(Warsh).filter(Warsh.id == verse_id).first()
        if verse_entry and verse_entry.page is not None:
            try: return int(verse_entry.page)
            except ValueError: return None
    return None

# --- Tafsir, Translation, Recitation, Mushaf Page Creation (Assumed to be as per your latest version) ---
# //CHANGE TO THE OLD (If any of these were different in your first version and not search-related)
# These functions seem standard and likely evolved with your app's features.
def get_tafsir_logic(db: Session, verse_id: int, language_id: int, mushaf_id: int):
    if mushaf_id == 2: return "warsh" # Placeholder, actual Warsh tafsir logic might differ
    tafsir = db.query(Tafsirs).filter(Tafsirs.verse_id == verse_id, Tafsirs.language_id == language_id).first()
    return tafsir

def get_translation_logic(db: Session, verse_id: int, language_id: int, mushaf_id: int):
    if mushaf_id == 2: return "warsh" # Placeholder
    if language_id == 9: return "no_arabic" 
    verse_obj = db.query(Verse).filter(Verse.id == verse_id).first()
    if not verse_obj or not verse_obj.verse_key or ":" not in verse_obj.verse_key: return None
    try: sura_num, ayah_num = map(int, verse_obj.verse_key.split(":"))
    except ValueError: return None
    translation = db.query(Translation).filter(Translation.sura == sura_num, Translation.ayah == ayah_num).first() # Assuming language_id is handled by table structure or another filter
    return translation

def get_verse_count_in_chapter(db: Session, chapter_id: int): 
    chapter = db.query(Chapters).filter(Chapters.id == chapter_id).first()
    return chapter.verses_count if chapter else None

def get_warsh_verse_count(db: Session, surah_id: int): 
    # This assumes Warsh table has a reliable verse_count per surah_no.
    # It might be better to query Chapters table if it's the source of truth for verse counts for all qira'at.
    verse_info = db.query(Warsh.verse_count).filter(Warsh.sura_no == surah_id).first() # This might give repeated counts
    # A more robust way for Warsh if Warsh table has verse_count per surah:
    # warsh_surah_data = db.query(func.max(Warsh.verse_count)).filter(Warsh.sura_no == surah_id).scalar()
    # return warsh_surah_data if warsh_surah_data is not None else 0
    return verse_info[0] if verse_info else None # Current approach

def get_verses_by_interval(db: Session, chapter_id: int, start: int, end: int): 
    query = db.query(Verse).filter(Verse.surah == chapter_id) 
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

# --- Frequent Errors & Progress Handling (Assumed to be as per your latest version) ---
def update_frequent_errors(db: Session, user_id: UUID, mushaf_id: int, ayah_ids: List[int]):
    model = HafsError if mushaf_id == 1 else WarshError
    for ayah_id_val in ayah_ids: 
        error = db.query(model).filter_by(user_id=user_id, ayah_id=ayah_id_val).first()
        if error: error.error_count += 1
        else: db.add(model(user_id=user_id, ayah_id=ayah_id_val, error_count=1)) # type: ignore
    db.commit()

def get_user_frequent_errors(db: Session, user_id: UUID, mushaf_id: int) -> List[FrequentErrorOut]:
    model = HafsError if mushaf_id == 1 else WarshError
    error_list = db.query(model).filter_by(user_id=user_id).order_by(model.updated_at.desc()).all() # type: ignore
    results = []
    for error_item in error_list: 
        text_val = ""
        # This logic assumes ayah_id in error tables corresponds to Verse.id or Warsh.id
        if mushaf_id == 1:
            verse_obj = db.query(Verse.text).filter_by(id=error_item.ayah_id).first() 
            text_val = verse_obj[0] if verse_obj else "Ayah text not found"
        else: 
            verse_obj = db.query(Warsh.aya_text).filter_by(id=error_item.ayah_id).first() 
            text_val = verse_obj[0] if verse_obj else "Ayah text not found"
        results.append(FrequentErrorOut(
            ayah_id=error_item.ayah_id, text=text_val, error_count=error_item.error_count, 
            created_at=error_item.created_at, updated_at=error_item.updated_at
        ))
    return results

def update_surah_progress(db: Session, user_id: UUID, mushaf_id: int, surah_id_param: int, ayah_ids: List[int]): 
    ProgressModel = HafsSurahProgress if mushaf_id == 1 else WarshSurahProgress
    ErrorModel = HafsError if mushaf_id == 1 else WarshError
    total_ayahs = 0
    if mushaf_id == 1: # Hafs - surah_id_param is Chapters.id
        chapter_info = db.query(Chapters.verses_count).filter(Chapters.id == surah_id_param).first()
        total_ayahs = chapter_info[0] if chapter_info else 0
    else: # Warsh - surah_id_param is Warsh.sura_no
        # Need to get verse_count for this sura_no from Warsh table or Chapters table
        # Assuming Chapters table is the source of truth for verse counts if Warsh.verse_count is per-ayah
        chapter_info_for_warsh = db.query(Chapters.verses_count).filter(Chapters.chapter_number == surah_id_param).first()
        total_ayahs = chapter_info_for_warsh[0] if chapter_info_for_warsh else 0
        # warsh_surah_info = db.query(Warsh.verse_count).filter(Warsh.sura_no == surah_id_param).first() # This might be per-ayah
        # total_ayahs = warsh_surah_info[0] if warsh_surah_info else 0

    if total_ayahs == 0: return

    progress = db.query(ProgressModel).filter_by(user_id=user_id, surah_id=surah_id_param).first()
    if not progress:
        progress = ProgressModel(user_id=user_id, surah_id=surah_id_param, ayahs_learned=[], total_ayahs=total_ayahs, percentage=0) # type: ignore
        db.add(progress)
    
    current_learned_set = set(progress.ayahs_learned or [])
    for ayah_id_val in ayah_ids: current_learned_set.add(ayah_id_val) 
    
    progress.ayahs_learned = sorted(list(current_learned_set))
    progress.percentage = round((len(progress.ayahs_learned) / total_ayahs) * 100, 2) if total_ayahs > 0 else 0.0 # Ensure float division
    
    for ayah_id_val in ayah_ids: 
        error_to_decrement = db.query(ErrorModel).filter_by(user_id=user_id, ayah_id=ayah_id_val).first()
        if error_to_decrement:
            error_to_decrement.error_count -= 1
            if error_to_decrement.error_count <= 0: db.delete(error_to_decrement)
    db.commit()
    if progress: db.refresh(progress) 
    update_quran_memorization(db, user_id, mushaf_id)

def update_quran_memorization(db: Session, user_id: UUID, mushaf_id: int):
    ProgressModel = HafsSurahProgress if mushaf_id == 1 else WarshSurahProgress
    all_surah_progress_for_user = db.query(ProgressModel).filter_by(user_id=user_id).all()
    total_learned_verses = sum(len(sp.ayahs_learned or []) for sp in all_surah_progress_for_user)
    
    grand_total_verses = 0
    # For Hafs, sum of verses_count from all Chapters
    all_chapters = db.query(Chapters.verses_count).all()
    grand_total_verses = sum(c[0] for c in all_chapters if c[0] is not None)
    # Note: This grand_total_verses is for Hafs (6236). If Warsh has a different total (e.g., 6214),
    # this needs to be adjusted if mushaf_id is Warsh.
    # For simplicity, if your Chapters table accurately reflects verse counts for both, this is fine.
    # Otherwise, you might need:
    # if mushaf_id == 1:
    #     grand_total_verses = sum(c[0] for c in db.query(Chapters.verses_count).all() if c[0] is not None)
    # else: # Warsh
    #     grand_total_verses = 6214 # Or dynamically calculate if possible
    
    overall_percentage = round((total_learned_verses / grand_total_verses) * 100, 2) if grand_total_verses > 0 else 0.0 # Ensure float
    memorization_record = db.query(QuranMemorization).filter_by(user_id=user_id).first()
    if memorization_record:
        memorization_record.percentage = overall_percentage
    else:
        memorization_record = QuranMemorization(user_id=user_id, percentage=overall_percentage) # type: ignore
        db.add(memorization_record)
    db.commit()

def get_memorization_percentage(db: Session, user_id: UUID):
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
