# ai.py
import torch
import librosa
from transformers import WhisperProcessor, WhisperForConditionalGeneration
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
import unicodedata
import re
from typing import List, Tuple, Dict, Any
import tempfile
import os
import traceback

# --- Global Variables for AI Model ---
MODEL_NAME = "tarteel-ai/whisper-base-ar-quran" # or your specific model
processor = None
model = None
device = "cuda" if torch.cuda.is_available() else "cpu"

router = APIRouter()

# --- Constants ---
FATHA = '\u064E'
DAMMA = '\u064F'
KASRA = '\u0650'
RELEVANT_HARAKAT = [FATHA, DAMMA, KASRA] # For check_word_match

BASMALA_EXACT_TEXT = "بسم الله الرحمن الرحيم"
SURAH_WORD_AR_RAW = "سورة" # Raw form for initial check

# --- Normalization Functions ---

def normalize_text_for_detection(text: str) -> str:
    """
    Aggressive normalization for detecting sequences like Basmala or Surah headers.
    Removes all diacritics, normalizes Alef forms, Ta Marbuta, Alif Maqsura,
    and standardizes all whitespace to single spaces.
    """
    if not text:
        return ""
    # Remove all diacritics (Mn category)
    text_no_diacritics = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    # Normalize common letter variations
    text_normalized_letters = text_no_diacritics.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ٱ', 'ا')
    text_normalized_letters = text_normalized_letters.replace('ة', 'ه')
    text_normalized_letters = text_normalized_letters.replace('ى', 'ي')
    # Standardize whitespace (newline, non-breaking space, multiple spaces) to a single space
    text_standard_space = re.sub(r'[\s\u00A0]+', ' ', text_normalized_letters)
    return text_standard_space.strip()

BASMALA_NORMALIZED_FOR_DETECTION = normalize_text_for_detection(BASMALA_EXACT_TEXT)
BASMALA_TOKENS_NORMALIZED_FOR_DETECTION = [token for token in BASMALA_NORMALIZED_FOR_DETECTION.split(' ') if token] # Ensure no empty tokens
SURAH_WORD_NORMALIZED_FOR_DETECTION = normalize_text_for_detection(SURAH_WORD_AR_RAW)


def normalize_arabic_text_for_comparison_content(text: str) -> str:
    """
    Normalizes Arabic text for actual content comparison (used by check_word_match).
    Removes specific Quranic symbols, verse numbers.
    Converts dagger alif to regular alif.
    Keeps most diacritics relevant for pronunciation if not stripped elsewhere.
    """
    if not text:
        return ""
    # Remove specific Quranic symbols, page markers, sajda signs etc.
    normalized_text = re.sub(r"[\u0600-\u0605\u0610-\u061A\u06D6-\u06ED\u08F0-\u08FF]+", "", text)
    # Remove Ayah markers (e.g., ۝١)
    normalized_text = re.sub(r"۝\s*[\u0660-\u06690-9]*\s*", "", normalized_text)
    # Remove any standalone digits (Arabic or Western) that might be verse numbers missed by above
    normalized_text = re.sub(r"\b[0-9\u0660-\u0669]+\b", "", normalized_text) # Word boundary to avoid removing from words like الله
    normalized_text = re.sub(r"[0-9\u0660-\u0669]+", "", normalized_text) # More aggressive digit removal if needed

    normalized_text = normalized_text.replace('ٰ', 'ا') # Dagger Alif to regular Alif
    
    # Consolidate multiple spaces into one and strip leading/trailing
    return re.sub(r'\s+', ' ', normalized_text).strip()


def get_letters_and_harakat(word_normalized_for_content: str, apply_phonetic_normalization: bool = False) -> Tuple[str, List[Tuple[int, str]]]:
    # This function remains as is, used by check_word_match
    clean_word_for_letters = unicodedata.normalize('NFKC', word_normalized_for_content)
    letter_only_string = "".join(c for c in unicodedata.normalize('NFD', clean_word_for_letters) if unicodedata.category(c).startswith('L'))

    if apply_phonetic_normalization:
        letter_only_string = letter_only_string.replace('ٱ', 'ا').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        letter_only_string = letter_only_string.replace('ص', 'س') 
        letter_only_string = letter_only_string.replace('ى', 'ي') 
        letter_only_string = letter_only_string.replace('ة', 'ه') # Often phonetically similar to ه in some contexts

    harakat_tuples = []
    current_letter_idx = -1
    temp_letters_for_indices = []
    for char in unicodedata.normalize('NFD', word_normalized_for_content):
        if unicodedata.category(char).startswith('L'):
            temp_letters_for_indices.append(char)
            current_letter_idx = len(temp_letters_for_indices) - 1
        elif char in RELEVANT_HARAKAT and current_letter_idx != -1:
            harakat_tuples.append((current_letter_idx, char))
            
    return letter_only_string, harakat_tuples

def levenshtein_distance(s1: str, s2: str) -> int:
    # This function remains as is
    if len(s1) < len(s2): return levenshtein_distance(s2, s1)
    if len(s2) == 0: return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1; deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def check_word_match(ayah_word_normalized_for_content: str, user_word_normalized_for_content: str,
                     letter_threshold: float = 0.85, tashkeel_threshold: float = 0.7) -> bool:
    # This function remains as is
    ayah_letters_compare, ayah_harakat = get_letters_and_harakat(ayah_word_normalized_for_content, apply_phonetic_normalization=True)
    user_letters_compare, user_harakat = get_letters_and_harakat(user_word_normalized_for_content, apply_phonetic_normalization=True)

    if not ayah_letters_compare and not user_letters_compare: return True
    if not ayah_letters_compare or not user_letters_compare: return False

    dist = levenshtein_distance(ayah_letters_compare, user_letters_compare)
    max_len = max(len(ayah_letters_compare), len(user_letters_compare))
    letter_sim = (max_len - dist) / max_len if max_len > 0 else (1.0 if dist == 0 else 0.0)
    
    if letter_sim < letter_threshold:
        return False

    if not ayah_harakat:
        tashkeel_sim = 1.0
    else:
        correct_tashkeel_count = 0
        set_user_harakat = set(user_harakat)
        for h_a in ayah_harakat:
            if h_a in set_user_harakat: correct_tashkeel_count += 1
        tashkeel_sim = correct_tashkeel_count / len(ayah_harakat) if ayah_harakat else 1.0
    
    return tashkeel_sim >= tashkeel_threshold

@router.on_event("startup")
async def load_model_on_startup():
    global processor, model
    if model is None or processor is None:
        print(f"AI_LOG: Loading ASR model: {MODEL_NAME} on device: {device}")
        try:
            processor = WhisperProcessor.from_pretrained(MODEL_NAME)
            model = WhisperForConditionalGeneration.from_pretrained(MODEL_NAME)
            model.to(device); model.eval()
            print("AI_LOG: ASR Model loaded successfully.")
        except Exception as e:
            print(f"AI_LOG: Error loading ASR model: {e}"); processor, model = None, None

class IncorrectWordDetail(BaseModel):
    word: str
    position: int

class TranscriptionComparisonResponse(BaseModel):
    transcribed_text: str
    incorrect_ayah_words: List[IncorrectWordDetail]

def _strip_prefix_from_raw_text(raw_text: str, prefix_tokens_normalized_for_detection: List[str], num_prefix_raw_words_expected: int) -> str:
    """
    Helper to strip a prefix from raw text if its normalized version matches.
    Returns the stripped raw text or original raw text if no match.
    """
    if not raw_text or not prefix_tokens_normalized_for_detection:
        return raw_text

    # Split raw text by any whitespace, keeping original tokens
    raw_text_tokens = [token for token in re.split(r'[\s\u00A0]+', raw_text) if token]
    
    if len(raw_text_tokens) < num_prefix_raw_words_expected:
        return raw_text # Not enough raw tokens to possibly match the prefix

    # Normalize the first N raw tokens for comparison
    first_n_raw_tokens_normalized = [
        normalize_text_for_detection(token) for token in raw_text_tokens[:num_prefix_raw_words_expected]
    ]

    if first_n_raw_tokens_normalized == prefix_tokens_normalized_for_detection:
        return " ".join(raw_text_tokens[num_prefix_raw_words_expected:]).strip()
    return raw_text


@router.post("/transcribe_and_compare", response_model=TranscriptionComparisonResponse)
async def transcribe_and_compare_audio(
    audio_file: UploadFile = File(...),
    ayah_text_input: str = Form(...) 
):
    if model is None or processor is None: raise HTTPException(status_code=503, detail="ASR Model is not available.")
    
    tmp_audio_file_path = None; original_transcription = ""
    try:
        suffix = os.path.splitext(audio_file.filename)[1] if audio_file.filename and os.path.splitext(audio_file.filename)[1] else ".m4a"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            content = await audio_file.read(); tmp_file.write(content)
            tmp_audio_file_path = tmp_file.name
        waveform_np, _ = librosa.load(tmp_audio_file_path, sr=16000, mono=True)
        input_features = processor(waveform_np, sampling_rate=16000, return_tensors="pt").input_features.to(device)
        with torch.no_grad(): predicted_ids = model.generate(input_features)
        original_transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
        print(f"AI_LOG: Original Transcription from Whisper: >>>{original_transcription}<<<")
    except Exception as e:
        print(f"AI_LOG: Full traceback of audio processing error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error during audio processing or transcription: {str(e)}")
    finally:
        if audio_file: await audio_file.close()
        if tmp_audio_file_path and os.path.exists(tmp_audio_file_path): os.remove(tmp_audio_file_path)

    # --- Text Preprocessing for Comparison ---
    print(f"AI_LOG: Original Ayah Text Input from Frontend: >>>{ayah_text_input}<<<")

    processed_ayah_text_for_comparison = ayah_text_input
    processed_transcription_for_comparison = original_transcription

    # 1. Surah Header Removal (from Ayah text)
    raw_ayah_tokens_before_header_strip = [token for token in re.split(r'[\s\u00A0]+', processed_ayah_text_for_comparison) if token]
    if raw_ayah_tokens_before_header_strip:
        first_raw_token_normalized = normalize_text_for_detection(raw_ayah_tokens_before_header_strip[0])
        if first_raw_token_normalized == SURAH_WORD_NORMALIZED_FOR_DETECTION:
            num_header_words_to_strip = 1 # For "سورة"
            if len(raw_ayah_tokens_before_header_strip) > 1:
                # Check if the Surah name is one or two words (e.g., "الفلق" vs "آل عمران")
                # This is a heuristic. A more robust way would be a list of Surah names.
                num_header_words_to_strip += 1 # Default to removing one word for Surah name
                if len(raw_ayah_tokens_before_header_strip) > 2 and \
                   normalize_text_for_detection(raw_ayah_tokens_before_header_strip[1]) == normalize_text_for_detection("ال"):
                    num_header_words_to_strip += 1 # For "ال" + "عمران"
            
            if len(raw_ayah_tokens_before_header_strip) >= num_header_words_to_strip:
                processed_ayah_text_for_comparison = " ".join(raw_ayah_tokens_before_header_strip[num_header_words_to_strip:]).strip()
            else: # Not enough words to strip header, implies malformed input or very short
                processed_ayah_text_for_comparison = "" 
            print(f"AI_LOG: Ayah Text after Surah Header Removal: >>>{processed_ayah_text_for_comparison}<<<")

    # 2. Al-Fatiha Basmala Case Check
    is_al_fatiha_basmala_case = False
    normalized_ayah_after_header_strip_for_fatiha_check = normalize_text_for_detection(processed_ayah_text_for_comparison)
    
    if normalized_ayah_after_header_strip_for_fatiha_check == BASMALA_NORMALIZED_FOR_DETECTION:
        is_al_fatiha_basmala_case = True
        print(f"AI_LOG: Al-Fatiha case detected. Basmala will NOT be stripped for comparison.")
    
    # 3. If NOT Al-Fatiha case, attempt to strip Basmala from both Ayah and Transcription texts
    if not is_al_fatiha_basmala_case:
        print(f"AI_LOG: Not Al-Fatiha case. Proceeding with Basmala stripping.")
        num_basmala_raw_words_expected = len(BASMALA_TOKENS_NORMALIZED_FOR_DETECTION)

        # Strip from Ayah text
        stripped_ayah = _strip_prefix_from_raw_text(processed_ayah_text_for_comparison, BASMALA_TOKENS_NORMALIZED_FOR_DETECTION, num_basmala_raw_words_expected)
        if stripped_ayah != processed_ayah_text_for_comparison:
            processed_ayah_text_for_comparison = stripped_ayah
            print(f"AI_LOG: Basmala stripped from Ayah text. Now: >>>{processed_ayah_text_for_comparison}<<<")
        else:
            print(f"AI_LOG: Basmala not detected or not stripped from Ayah text. Using: >>>{processed_ayah_text_for_comparison}<<<")

        # Strip from Transcription text
        stripped_transcription = _strip_prefix_from_raw_text(processed_transcription_for_comparison, BASMALA_TOKENS_NORMALIZED_FOR_DETECTION, num_basmala_raw_words_expected)
        if stripped_transcription != processed_transcription_for_comparison:
            processed_transcription_for_comparison = stripped_transcription
            print(f"AI_LOG: Basmala stripped from Transcription. Now: >>>{processed_transcription_for_comparison}<<<")
        else:
            print(f"AI_LOG: Basmala not detected or not stripped from Transcription. Using: >>>{processed_transcription_for_comparison}<<<")
            
    # 4. Prepare tokens for the main comparison loop
    final_ayah_tokens_raw_for_loop = [token for token in re.split(r'[\s\u00A0]+', processed_ayah_text_for_comparison) if token]
    
    ayah_words_for_comparison_info_list: List[Dict[str, Any]] = []
    for idx, raw_token in enumerate(final_ayah_tokens_raw_for_loop):
        normalized_token_for_content = normalize_arabic_text_for_comparison_content(raw_token)
        if normalized_token_for_content: 
            ayah_words_for_comparison_info_list.append({
                "original_form": raw_token, 
                "normalized_form_for_content_comparison": normalized_token_for_content,
                "original_position_in_processed_ayah": idx 
            })

    transcribed_tokens_for_comparison_normalized = [
        norm_word for raw_word in re.split(r'[\s\u00A0]+', processed_transcription_for_comparison) if raw_word
        if (norm_word := normalize_arabic_text_for_comparison_content(raw_word))
    ]
    
    print(f"AI_LOG: Final Ayah words for comparison loop ({len(ayah_words_for_comparison_info_list)} tokens): {[info['original_form'] for info in ayah_words_for_comparison_info_list]}")
    print(f"AI_LOG: Final Transcribed tokens for comparison loop ({len(transcribed_tokens_for_comparison_normalized)} tokens): {transcribed_tokens_for_comparison_normalized}")

    # 5. Perform Word-by-Word Comparison
    incorrect_ayah_word_details: List[IncorrectWordDetail] = []
    user_word_idx = 0 

    for ayah_info in ayah_words_for_comparison_info_list:
        ayah_word_original_form = ayah_info["original_form"]
        ayah_word_normalized_for_content = ayah_info["normalized_form_for_content_comparison"]
        ayah_word_position_in_processed_list = ayah_info["original_position_in_processed_ayah"]

        found_match_for_current_ayah_word = False
        temp_user_idx_search = user_word_idx
        while temp_user_idx_search < len(transcribed_tokens_for_comparison_normalized):
            user_word_normalized_for_content = transcribed_tokens_for_comparison_normalized[temp_user_idx_search]
            
            if check_word_match(ayah_word_normalized_for_content, user_word_normalized_for_content):
                found_match_for_current_ayah_word = True
                user_word_idx = temp_user_idx_search + 1 
                current_matched_user_word_letters, _ = get_letters_and_harakat(user_word_normalized_for_content, apply_phonetic_normalization=True)
                while user_word_idx < len(transcribed_tokens_for_comparison_normalized):
                    next_user_word_norm_content = transcribed_tokens_for_comparison_normalized[user_word_idx]
                    next_user_word_letters, _ = get_letters_and_harakat(next_user_word_norm_content, apply_phonetic_normalization=True)
                    if next_user_word_letters == current_matched_user_word_letters:
                        user_word_idx += 1
                    else:
                        break
                break 
            temp_user_idx_search += 1

        if not found_match_for_current_ayah_word:
            incorrect_ayah_word_details.append(
                IncorrectWordDetail(word=ayah_word_original_form, position=ayah_word_position_in_processed_list)
            )
    
    print(f"AI_LOG: Comparison complete. Incorrect words found: {len(incorrect_ayah_word_details)}")
    for detail in incorrect_ayah_word_details:
        print(f"AI_LOG: Incorrect - Word: '{detail.word}', Position in processed Ayah: {detail.position}")

    return TranscriptionComparisonResponse(
        transcribed_text=original_transcription, 
        incorrect_ayah_words=incorrect_ayah_word_details
    )

