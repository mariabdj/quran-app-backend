import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional, List
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
    chapter_number: Optional[int]
    name_simple: Optional[str]
    name_arabic: Optional[str]
    pages: Optional[str]
    verses_count: Optional[int]

    class Config:
        orm_mode = True


# === Hizb ===
class HizbOut(BaseModel):
    id: int
    hizb_number: Optional[int]
    first_verse_id: Optional[int]
    last_verse_id: Optional[int]
    verses_count: Optional[int]

    class Config:
        orm_mode = True


# === Juz ===
class JuzOut(BaseModel):
    id: int
    juz_number: Optional[int]
    first_verse_id: Optional[int]
    last_verse_id: Optional[int]
    verses_count: Optional[int]

    class Config:
        orm_mode = True


# === Verse ===
class VerseOut(BaseModel):
    id: int
    verse_key: str
    text: str
    text_simple: Optional[str]
    surah: Optional[int]

    class Config:
        orm_mode = True


# === Warsh Verse ===
class WarshVerseOut(BaseModel):
    id: int
    jozz: Optional[int]
    page: Optional[str]
    sura_no: Optional[int]
    sura_name_ar: Optional[str]
    aya_no: Optional[int]
    aya_text: Optional[str]
    text_simple: Optional[str]
    verse_count: Optional[int]


    class Config:
        orm_mode = True


class SearchResult(BaseModel):
    verse_id: int
    text: str

    class Config:
        orm_mode = True


# === Mushaf Page ===
class MushafPageOut(BaseModel):
    id: int
    page_number: Optional[int]
    first_verse_id: Optional[int]
    last_verse_id: Optional[int]

    class Config:
        orm_mode = True


# === Tafsir ===
class TafsirOut(BaseModel):
    id: int
    verse_id: Optional[int]
    language_id: Optional[int]
    text_: Optional[str]

    class Config:
        orm_mode = True


# === Translation ===
class TranslationOut(BaseModel):
    id: Optional[int]
    sura: int
    ayah: int
    ayah_key: Optional[str]
    text: str

    class Config:
        orm_mode = True



# === Verse Page mapping ===
class VersePageOut(BaseModel):
    id: int
    verse_id: Optional[int]
    page_id: Optional[int]
    page_number: Optional[int]

    class Config:
        orm_mode = True


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
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }



# === Surah Progress Input ===
class SurahProgressIn(BaseModel):
    user_id: UUID
    mushaf_id: int
    surah_id: int
    ayah_ids: List[int]
    created_at: Optional[str]
    updated_at: Optional[str]


# === Surah Progress Output ===
class SurahProgressOut(BaseModel):
    surah_id: int
    surah_name: str
    percentage: float
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }



# === Quran Memorization Output ===
class QuranMemorizationOut(BaseModel):
    user_id: UUID
    percentage: float
