import datetime
from datetime import datetime as dt 
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Union
from uuid import UUID


class UserOut(BaseModel):
    id: UUID
    username: str
    email: str
    phone: str
    mushaf_id: int

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    phone: str
    password: str
    mushaf_id: int

class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None



# === Chapter (Surah) ===
class ChapterOut(BaseModel):
    id: int
    chapter_number: Optional[int] = None
    name_simple: Optional[str] = None
    name_arabic: Optional[str] = None
    pages: Optional[str] = None # This seems to be a string representing a range e.g. "1-7"
    verses_count: Optional[int] = None

    class Config:
        from_attributes = True


# === Hizb ===
class HizbOut(BaseModel):
    id: int
    hizb_number: Optional[int] = None
    first_verse_id: Optional[int] = None
    last_verse_id: Optional[int] = None
    verses_count: Optional[int] = None

    class Config:
        from_attributes = True


# === Juz ===
class JuzOut(BaseModel):
    id: int
    juz_number: Optional[int] = None
    first_verse_id: Optional[int] = None
    last_verse_id: Optional[int] = None
    verses_count: Optional[int] = None

    class Config:
        from_attributes = True


# === Verse (Original schemas - can be reused or adapted) ===
class VerseOut(BaseModel):
    id: int
    verse_key: str
    text: str
    text_simple: Optional[str] = None
    surah: Optional[int] = None

    class Config:
        from_attributes = True


# === Warsh Verse (Original schemas - can be reused or adapted) ===
class WarshVerseOut(BaseModel):
    id: int
    jozz: Optional[int] = None
    page: Optional[str] = None
    sura_no: Optional[int] = None
    sura_name_ar: Optional[str] = None
    aya_no: Optional[int] = None
    aya_text: Optional[str] = None
    text_simple: Optional[str] = None
    verse_count: Optional[int] = None


    class Config:
        from_attributes = True

# === SEARCH RELATED SCHEMAS ===

class AyahResult(BaseModel): # Specifically for search results
    verse_id: int
    text: str 

    class Config:
        from_attributes = True

class PageInfoResponse(BaseModel):
    page_number: int

# //CHANGE TO THE OLD (If this was different in your absolute first version and you need that specific old structure)
# This MushafPageOut is standard. If your "first ever" version was different and needed for non-search reasons,
# you'd need to compare. For search-related functionalities, this is fine.
# === Mushaf Page ===
class MushafPageOut(BaseModel):
    id: int
    page_number: Optional[int] = None
    first_verse_id: Optional[int] = None
    last_verse_id: Optional[int] = None

    class Config:
        from_attributes = True


# === Tafsir ===
class TafsirOut(BaseModel):
    id: int
    verse_id: Optional[int] = None
    language_id: Optional[int] = None
    text_: Optional[str] = Field(None, alias="text") # Alias if your DB field is 'text'

    class Config:
        from_attributes = True
        populate_by_name = True


# === Translation ===
class TranslationOut(BaseModel):
    id: Optional[int] = None
    sura: int
    ayah: int
    ayah_key: Optional[str] = None
    text: str

    class Config:
        from_attributes = True



# === Verse Page mapping ===
class VersePageOut(BaseModel):
    id: int
    verse_id: Optional[int] = None
    page_id: Optional[int] = None
    page_number: Optional[int] = None

    class Config:
        from_attributes = True


# === Recitation Interval Input ===
class RecitationIntervalIn(BaseModel):
    surah_id: int
    from_verse: int
    to_verse: int
    mushaf_id: int


# === Frequent Errors Input ===
class FrequentErrorIn(BaseModel):
    user_id: UUID
    mushaf_id: int
    ayah_ids: List[int]


# === Frequent Errors Output ===
class FrequentErrorOut(BaseModel):
    ayah_id: int
    text: str
    error_count: int
    created_at: Optional[dt] = None
    updated_at: Optional[dt] = None

    class Config:
        from_attributes = True
        json_encoders = {
            dt: lambda v: v.isoformat() if v else None
        }



# === Surah Progress Input ===
class SurahProgressIn(BaseModel):
    user_id: UUID
    mushaf_id: int
    surah_id: int
    ayah_ids: List[int]
    # created_at and updated_at are usually handled by the DB or server, not input
    # created_at: Optional[str] = None
    # updated_at: Optional[str] = None


# === Surah Progress Output ===
class SurahProgressOut(BaseModel):
    surah_id: int
    surah_name: str # You'll need to fetch this in your route/crud
    percentage: float
    created_at: Optional[dt] = None
    updated_at: Optional[dt] = None

    class Config:
        from_attributes = True
        json_encoders = {
            dt: lambda v: v.isoformat() if v else None
        }



# === Quran Memorization Output ===
class QuranMemorizationOut(BaseModel):
    user_id: UUID # Should probably be str if that's how you query it elsewhere
    percentage: float

    class Config:
        from_attributes = True


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class SurahNameResponse(BaseModel):
    surah_name: str

class RandomAyahResponse(BaseModel):
    id: int
    text: str

    class Config:
        from_attributes = True
