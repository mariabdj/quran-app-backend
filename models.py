from typing import List, Optional

from sqlalchemy import ARRAY, TIMESTAMP, BigInteger, Boolean, Column, ForeignKeyConstraint, Index, Integer, JSON, PrimaryKeyConstraint, String, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID  # at the top


class Base(DeclarativeBase):
    pass

class AppUser(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String)
    phone = Column(String)
    created_at = Column(Text, default=func.now())
    mushaf_id = Column(Integer, nullable=False)

class Chapters(Base):
    __tablename__ = 'chapters'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='chapters_pkey'),
        Index('index_chapters_on_chapter_number', 'chapter_number'),
        {'schema': 'quran'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bismillah_pre: Mapped[Optional[bool]] = mapped_column(Boolean)
    name_arabic: Mapped[Optional[str]] = mapped_column(String)
    name_simple: Mapped[Optional[str]] = mapped_column(String)
    pages: Mapped[Optional[str]] = mapped_column(String)
    verses_count: Mapped[Optional[int]] = mapped_column(Integer)
    chapter_number: Mapped[Optional[int]] = mapped_column(Integer)
    hizbs_count: Mapped[Optional[int]] = mapped_column(Integer)
    ayah_id_range_hafs: Mapped[Optional[str]] = mapped_column(Text)
    ayah_id_range_warsh: Mapped[Optional[str]] = mapped_column(Text)


class Hizbs(Base):
    __tablename__ = 'hizbs'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='hizbs_pkey'),
        Index('index_hizbs_on_first_verse_id_and_last_verse_id', 'first_verse_id', 'last_verse_id'),
        Index('index_hizbs_on_hizb_number', 'hizb_number'),
        {'schema': 'quran'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    hizb_number: Mapped[Optional[int]] = mapped_column(Integer)
    verses_count: Mapped[Optional[int]] = mapped_column(Integer)
    verse_mapping: Mapped[Optional[dict]] = mapped_column(JSONB)
    first_verse_id: Mapped[Optional[int]] = mapped_column(Integer)
    last_verse_id: Mapped[Optional[int]] = mapped_column(Integer)



class Juzs(Base):
    __tablename__ = 'juzs'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='juzs_pkey'),
        Index('index_juzs_on_first_verse_id', 'first_verse_id'),
        Index('index_juzs_on_juz_number', 'juz_number'),
        Index('index_juzs_on_last_verse_id', 'last_verse_id'),
        {'schema': 'quran'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    juz_number: Mapped[Optional[int]] = mapped_column(Integer)
    verse_mapping: Mapped[Optional[dict]] = mapped_column(JSON)
    first_verse_id: Mapped[Optional[int]] = mapped_column(Integer)
    last_verse_id: Mapped[Optional[int]] = mapped_column(Integer)
    verses_count: Mapped[Optional[int]] = mapped_column(Integer)


class MushafPages(Base):
    __tablename__ = 'mushaf_pages'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='mushaf_pages_pkey'),
        Index('index_mushaf_pages_on_mushaf_id', 'mushaf_id'),
        Index('index_mushaf_pages_on_page_number', 'page_number'),
        {'schema': 'quran'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    verse_mapping: Mapped[Optional[dict]] = mapped_column(JSON)
    first_verse_id: Mapped[Optional[int]] = mapped_column(Integer)
    last_verse_id: Mapped[Optional[int]] = mapped_column(Integer)
    verses_count: Mapped[Optional[int]] = mapped_column(Integer)
    mushaf_id: Mapped[Optional[int]] = mapped_column(Integer)
    first_word_id: Mapped[Optional[int]] = mapped_column(Integer)
    last_word_id: Mapped[Optional[int]] = mapped_column(Integer)


class Mushafs(Base):
    __tablename__ = 'mushafs'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='mushafs_pkey'),
        Index('index_mushafs_on_enabled', 'enabled'),
        Index('index_mushafs_on_is_default', 'is_default'),
        Index('index_mushafs_on_qirat_type_id', 'qirat_type_id'),
        {'schema': 'quran'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    lines_per_page: Mapped[Optional[int]] = mapped_column(Integer)
    is_default: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    default_font_name: Mapped[Optional[str]] = mapped_column(String)
    pages_count: Mapped[Optional[int]] = mapped_column(Integer)
    qirat_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    enabled: Mapped[Optional[bool]] = mapped_column(Boolean)
    resource_content_id: Mapped[Optional[int]] = mapped_column(Integer)


class QiratTypes(Base):
    __tablename__ = 'qirat_types'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='qirat_types_pkey'),
        {'schema': 'quran'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    recitations_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))


t_schema_migrations = Table(
    'schema_migrations', Base.metadata,
    Column('version', String, nullable=False),
    Index('unique_schema_migrations', 'version', unique=True),
    schema='quran'
)

class Ayah(Base):
    __tablename__ = 'ayah'
    __table_args__ = (
        ForeignKeyConstraint(['surah_id'], ['quran.surah.surah_id'], name='ayah_surah_id_fkey'),
        PrimaryKeyConstraint('ayah_key', name='ayah_pkey'),
        UniqueConstraint('ayah_index', name='ayah_index_key'),
        UniqueConstraint('surah_id', 'ayah_num', name='surah_ayah_key'),
        Index('ayah_surah_id_idx', 'surah_id'),
        Index('index_quran.ayah_on_ayah_key', 'ayah_key'),
        {'schema': 'quran'}
    )

    ayah_index: Mapped[int] = mapped_column(Integer)
    ayah_key: Mapped[str] = mapped_column(Text, primary_key=True)
    surah_id: Mapped[Optional[int]] = mapped_column(Integer)
    ayah_num: Mapped[Optional[int]] = mapped_column(Integer)
    page_num: Mapped[Optional[int]] = mapped_column(Integer)
    juz_num: Mapped[Optional[int]] = mapped_column(Integer)
    hizb_num: Mapped[Optional[int]] = mapped_column(Integer)
    text_: Mapped[Optional[str]] = mapped_column('text', Text)
    sajdah: Mapped[Optional[str]] = mapped_column(Text)

    surah: Mapped[Optional['Surah']] = relationship('Surah', back_populates='ayah')


class Surah(Base):
    __tablename__ = 'surah'
    __table_args__ = (
        PrimaryKeyConstraint('surah_id', name='surah_pkey'),
        {'schema': 'quran'}
    )

    surah_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ayat: Mapped[int] = mapped_column(Integer)
    bismillah_pre: Mapped[bool] = mapped_column(Boolean)
    page: Mapped[list] = mapped_column(ARRAY(Integer()))
    name_simple: Mapped[str] = mapped_column(Text)
    name_english: Mapped[str] = mapped_column(Text)
    name_arabic: Mapped[str] = mapped_column(Text)

    ayah: Mapped[List['Ayah']] = relationship('Ayah', back_populates='surah')


class Tafsirs(Base):
    __tablename__ = 'tafsirs'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='tafsirs_pkey'),
        Index('index_tafsirs_on_chapter_id', 'chapter_id'),
        Index('index_tafsirs_on_chapter_id_and_verse_number', 'chapter_id', 'verse_number'),
        Index('index_tafsirs_on_hizb_number', 'hizb_number'),
        Index('index_tafsirs_on_juz_number', 'juz_number'),
        Index('index_tafsirs_on_language_id', 'language_id'),
        Index('index_tafsirs_on_page_number', 'page_number'),
        Index('index_tafsirs_on_resource_content_id', 'resource_content_id'),
        Index('index_tafsirs_on_verse_id', 'verse_id'),
        Index('index_tafsirs_on_verse_key', 'verse_key'),
        {'schema': 'quran'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    verse_id: Mapped[Optional[int]] = mapped_column(Integer)
    language_id: Mapped[Optional[int]] = mapped_column(Integer)
    text_: Mapped[Optional[str]] = mapped_column('text', Text)
    language_name: Mapped[Optional[str]] = mapped_column(String)
    resource_content_id: Mapped[Optional[int]] = mapped_column(Integer)
    resource_name: Mapped[Optional[str]] = mapped_column(String)
    verse_key: Mapped[Optional[str]] = mapped_column(String)
    chapter_id: Mapped[Optional[int]] = mapped_column(Integer)
    verse_number: Mapped[Optional[int]] = mapped_column(Integer)
    juz_number: Mapped[Optional[int]] = mapped_column(Integer)
    hizb_number: Mapped[Optional[int]] = mapped_column(Integer)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)


Base = declarative_base()

from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Translation(Base):
    __tablename__ = 'translation'
    __table_args__ = {'schema': 'quran'}

    id = Column(Integer, primary_key=True)  # ✅ nouvelle colonne
    sura = Column(Integer)
    ayah = Column(Integer)
    ayah_key = Column(Text)
    text = Column(Text, nullable=True)



class Verse(Base):
    __tablename__ = 'verse'
    __table_args__ = {'schema': 'quran'}

    id = Column(Integer, primary_key=True)
    verse_key = Column(Text)
    text = Column(Text)
    text_simple = Column(Text)
    surah = Column(Integer)


class VersePages(Base):
    __tablename__ = 'verse_pages'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='verse_pages_pkey'),
        Index('index_verse_pages_on_page_number_and_mushaf_id', 'page_number', 'mushaf_id'),
        Index('index_verse_pages_on_verse_id', 'verse_id'),
        {'schema': 'quran'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    verse_id: Mapped[Optional[int]] = mapped_column(Integer)
    page_id: Mapped[Optional[int]] = mapped_column(Integer)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    mushaf_id: Mapped[Optional[int]] = mapped_column(Integer)


class Warsh(Base):
    __tablename__ = 'warsh'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='warsh_pkey'),
        {'schema': 'quran'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jozz: Mapped[Optional[int]] = mapped_column(Integer)
    page: Mapped[Optional[str]] = mapped_column(String(10))
    sura_no: Mapped[Optional[int]] = mapped_column(Integer)
    sura_name_en: Mapped[Optional[str]] = mapped_column(String(255))
    sura_name_ar: Mapped[Optional[str]] = mapped_column(Text)
    line_start: Mapped[Optional[int]] = mapped_column(Integer)
    line_end: Mapped[Optional[int]] = mapped_column(Integer)
    aya_no: Mapped[Optional[int]] = mapped_column(Integer)
    aya_text: Mapped[Optional[str]] = mapped_column(Text)
    text_simple: Mapped[Optional[str]] = mapped_column(Text)
    verse_count: Mapped[Optional[int]] = mapped_column(Integer)

# === Frequent Errors Tables ===
class HafsError(Base):
    __tablename__ = "hafs_errors"
    __table_args__ = {"schema": "public"}

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    ayah_id = Column(Integer, primary_key=True)
    error_count = Column(Integer, default=1)
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())


class WarshError(Base):
    __tablename__ = "warsh_errors"
    __table_args__ = {"schema": "public"}

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    ayah_id = Column(Integer, primary_key=True)
    error_count = Column(Integer, default=1)
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())


class HafsSurahProgress(Base):
    __tablename__ = "hafs_surah_progress"
    __table_args__ = {"schema": "public"}

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    surah_id = Column(Integer, primary_key=True)
    ayahs_learned = Column(ARRAY(Integer), default=[])
    total_ayahs = Column(Integer, nullable=False)
    percentage = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())


class WarshSurahProgress(Base):
    __tablename__ = "warsh_surah_progress"
    __table_args__ = {"schema": "public"}

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    surah_id = Column(Integer, primary_key=True)
    ayahs_learned = Column(ARRAY(Integer), default=[])
    total_ayahs = Column(Integer, nullable=False)
    percentage = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())



# === Global Quran Memorization ===
class QuranMemorization(Base):
    __tablename__ = "quran_memorization"
    __table_args__ = {"schema": "public"}

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    percentage = Column(Integer, default=0)





