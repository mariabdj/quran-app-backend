from sqlalchemy.orm import Session
from models import *
from schemas import *
from schemas import FrequentErrorOut  # make sure this import is present

#Authentification
def get_user_by_username(db: Session, username: str):
    return db.query(AppUser).filter(AppUser.username == username).first()

def create_app_user(db: Session, user_id: UUID, username: str, email: str, phone: str, mushaf_id: int):
    user = AppUser(id=user_id, username=username, email=email, phone=phone, mushaf_id=mushaf_id)  # 🔥 Ajouté
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
    if juz is None:
        return None
    return db.query(VersePages).filter(VersePages.verse_id == juz.first_verse_id).first()


# === HIZBS ===
def get_all_hizbs(db: Session):
    return db.query(Hizbs).order_by(Hizbs.hizb_number).all()


def get_hizb_start_page(db: Session, first_verse_id: int):
    return db.query(VersePages).filter(VersePages.verse_id == first_verse_id).first()


# === MUSHAF PAGES ===
def get_mushaf_page(db: Session, page_number: int):
    return db.query(MushafPages).filter(MushafPages.page_number == page_number).first()


# === VERSES ===
def get_verses_in_page(db: Session, first_verse_id: int, last_verse_id: int):
    verses = db.query(Verse).filter(
        Verse.id >= first_verse_id,
        Verse.id <= last_verse_id
    ).all()

    results = []

    for verse in verses:
        try:
            surah_id, verse_number = map(int, verse.verse_key.split(":"))
        except:
            continue  # skip malformed keys

        if verse_number == 1:
            surah = db.query(Chapters).filter(Chapters.id == surah_id).first()
            if surah:
                verse.text = f"سورة {surah.name_arabic.strip()}\nبسم الله الرحمن الرحيم\n{verse.text}"

        # Keep the full Verse object (with updated text)
        results.append(verse)

    return results


def get_warsh_verses_in_page(db: Session, page: str):
    verses = db.query(Warsh).filter(Warsh.page == page).order_by(Warsh.id).all()

    for verse in verses:
        if verse.aya_no == 1:
            surah_title = f"سورة {verse.sura_name_ar.strip()}"
            bismillah = "بسم الله الرحمن الرحيم"
            verse.aya_text = f"{surah_title}\n{bismillah}\n{verse.aya_text}"

    return verses



# === SEARCH ===
def search_in_mushaf(db: Session, mushaf_id: int, keyword: str, surah_id: Optional[int] = None):
    keyword = keyword.strip()

    if mushaf_id == 1:
        # HAFSS: search in verse
        query = db.query(Verse)
        if surah_id:
            query = query.filter(Verse.surah == surah_id)
        query = query.filter(Verse.text_simple.ilike(f"%{keyword}%"))
        return query.all()

    elif mushaf_id == 2:
        # WARSH: search in warsh
        query = db.query(Warsh)
        if surah_id:
            query = query.filter(Warsh.sura_no == surah_id)
        query = query.filter(Warsh.text_simple.ilike(f"%{keyword}%"))
        return query.all()

    else:
        return []


def get_page_from_verse_id(db: Session, mushaf_id: int, verse_id: int):
    if mushaf_id == 1:
        verse = db.query(Ayah).filter(Ayah.ayah_index == verse_id).first()
        if verse:
            return verse.page_num
    elif mushaf_id == 2:
        verse = db.query(Warsh).filter(Warsh.id == verse_id).first()
        if verse:
            return verse.page
    return None


# === TAFSIR ===
def get_tafsir_logic(db: Session, verse_id: int, language_id: int, mushaf_id: int):
    if mushaf_id == 2:
        return "warsh"
    tafsir = db.query(Tafsirs).filter(
        Tafsirs.verse_id == verse_id,
        Tafsirs.language_id == language_id
    ).first()
    return tafsir

# === TRANSLATION ===
def get_translation_logic(db: Session, verse_id: int, language_id: int, mushaf_id: int):
    if mushaf_id == 2:
        return "warsh"

    if language_id == 9:
        return "no_arabic"

    # 🔥 Étape 1 : récupérer le verse depuis table verse
    verse = db.query(Verse).filter(Verse.id == verse_id).first()
    if not verse:
        return None

    # 🔥 Étape 2 : parser surah et ayah depuis verse_key
    if not verse.verse_key or ":" not in verse.verse_key:
        return None

    try:
        sura, ayah = map(int, verse.verse_key.split(":"))
    except ValueError:
        return None

    # 🔥 Étape 3 : chercher dans translation
    translation = db.query(Translation).filter(
        Translation.sura == sura,
        Translation.ayah == ayah
    ).first()

    return translation





# === RECITATION INTERVAL SUPPORT ===
def get_verse_count_in_chapter(db: Session, chapter_id: int):
    chapter = db.query(Chapters).filter(Chapters.id == chapter_id).first()
    return chapter.verses_count if chapter else None

def get_warsh_verse_count(db: Session, surah_id: int):
    verse = db.query(Warsh).filter(Warsh.sura_no == surah_id).first()
    return verse.verse_count if verse else None

def get_verses_by_interval(db: Session, chapter_id: int, start: int, end: int):
    verses = db.query(Verse).all()

    # Filter in Python since we can't filter verse_key directly in DB
    result = []
    for verse in verses:
        if verse.verse_key and ":" in verse.verse_key:
            try:
                surah_id, verse_num = map(int, verse.verse_key.split(":"))
                if surah_id == chapter_id and start <= verse_num <= end:
                    result.append(verse)
            except ValueError:
                continue  # skip malformed keys

    return result



def get_warsh_by_interval(db: Session, surah_no: int, start: int, end: int):
    return db.query(Warsh).filter(
        Warsh.sura_no == surah_no,
        Warsh.aya_no >= start,
        Warsh.aya_no <= end
    ).order_by(Warsh.aya_no).all()


# === MUSHAF PAGE CREATION ===
def create_mushaf_page(db: Session, page_number: int, first_verse_id: int, last_verse_id: int):
    page = MushafPages(
        page_number=page_number,
        first_verse_id=first_verse_id,
        last_verse_id=last_verse_id
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
            new_error = model(user_id=user_id, ayah_id=ayah_id, error_count=1)
            db.add(new_error)
    db.commit()


def get_user_frequent_errors(db: Session, user_id: UUID, mushaf_id: int):
    model = HafsError if mushaf_id == 1 else WarshError
    error_list = db.query(model).filter_by(user_id=user_id).all()

    results = []
    for error in error_list:
        if mushaf_id == 1:
            verse = db.query(Verse).filter_by(id=error.ayah_id).first()
            text = verse.text if verse else ""
        else:
            verse = db.query(Warsh).filter_by(id=error.ayah_id).first()
            text = verse.aya_text if verse else ""

        # ✅ Build a real FrequentErrorOut Pydantic model
        results.append(FrequentErrorOut(
            ayah_id=error.ayah_id,
            text=text,
            error_count=error.error_count,
            created_at=error.created_at,
            updated_at=error.updated_at,
        ))

    return results


# === Surah Progress Handling ===
def update_surah_progress(db: Session, user_id: UUID, mushaf_id: int, surah_id: int, ayah_ids: List[int]):
    model = HafsSurahProgress if mushaf_id == 1 else WarshSurahProgress
    get_total = get_verse_count_in_chapter if mushaf_id == 1 else get_warsh_verse_count

    progress = db.query(model).filter_by(user_id=user_id, surah_id=surah_id).first()
    total_ayahs = get_total(db, surah_id)

    if not progress:
        progress = model(
            user_id=user_id,
            surah_id=surah_id,
            ayahs_learned=[],
            total_ayahs=total_ayahs,
            percentage=0
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)

    # Ajouter les ayahs qui ne sont pas déjà appris
    ayah_set = set(progress.ayahs_learned or [])
    for ayah in ayah_ids:
        if ayah not in ayah_set:
            ayah_set.add(ayah)

    progress.ayahs_learned = list(ayah_set)
    progress.percentage = round(len(progress.ayahs_learned) / total_ayahs * 100, 2)
    db.commit()

    # Mise à jour du pourcentage global
    update_quran_memorization(db, user_id, mushaf_id)

    # Nouveau bloc: décrémenter les erreurs fréquentes si l'utilisateur les a bien récitées maintenant
    ErrorModel = HafsError if mushaf_id == 1 else WarshError
    for ayah_id in ayah_ids:
        error = db.query(ErrorModel).filter_by(user_id=user_id, ayah_id=ayah_id).first()
        if error:
            error.error_count -= 1
            if error.error_count <= 0:
                db.delete(error)
            db.commit()


# === Global Memorization ===
def update_quran_memorization(db: Session, user_id: UUID, mushaf_id: int):
    model = HafsSurahProgress if mushaf_id == 1 else WarshSurahProgress
    all_surahs = db.query(model).filter_by(user_id=user_id).all()
    total_verses = sum([s.total_ayahs for s in all_surahs])
    learned_verses = sum([len(s.ayahs_learned or []) for s in all_surahs])
    total = 6236 if mushaf_id == 1 else 6214

    percentage = round(learned_verses / total * 100, 2) if total else 0

    memorization = db.query(QuranMemorization).filter_by(user_id=user_id).first()
    if memorization:
        memorization.percentage = percentage
    else:
        memorization = QuranMemorization(user_id=user_id, percentage=percentage)
        db.add(memorization)
    db.commit()


def get_memorization_percentage(db: Session, user_id: str):
    return db.query(QuranMemorization).filter_by(user_id=user_id).first()
