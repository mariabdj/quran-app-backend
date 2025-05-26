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
MODEL_NAME = "tarteel-ai/whisper-base-ar-quran"
processor = None
model = None
device = "cuda" if torch.cuda.is_available() else "cpu"

router = APIRouter()

# --- Constants for Tashkeel and Basmala ---
FATHA = '\u064E'
DAMMA = '\u064F'
KASRA = '\u0650'
RELEVANT_HARAKAT = [FATHA, DAMMA, KASRA] # Only Fatha, Damma, Kasra

BASMALA_EXACT_TEXT = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"

# --- Helper Functions for Text Processing and Comparison ---

def normalize_arabic_text_for_comparison_content(text: str) -> str:
    """
    Normalizes Arabic text for actual content comparison.
    - Removes Quranic symbols, verse numbers, etc.
    - Converts dagger alif (ٰ) to regular alif (ا) for comparison purposes.
    - Keeps Alef variants, Ta Marbuta, Alif Maqsura distinct *in the input to this function*,
      further letter normalization for comparison happens in get_letters_and_harakat.
    """
    normalized_text = re.sub(r"[\u0600-\u0605\u0610-\u061A\u06D6-\u06ED\u08F0-\u08FF]+", "", text)
    normalized_text = re.sub(r"۝\s*[\u0660-\u06690-9]*\s*", "", normalized_text)
    normalized_text = re.sub(r"[0-9\u0660-\u0669]+", "", normalized_text)
    
    normalized_text = normalized_text.replace('ٰ', 'ا') # MODIFIED: Convert dagger alif to regular alif
    
    return re.sub(r'\s+', ' ', normalized_text).strip()

BASMALA_NORMALIZED_FOR_EXACT_MATCH = normalize_arabic_text_for_comparison_content(BASMALA_EXACT_TEXT)


def get_letters_and_harakat(word_normalized_for_content: str, apply_phonetic_normalization: bool = False) -> Tuple[str, List[Tuple[int, str]]]:
    clean_word_for_letters = unicodedata.normalize('NFKC', word_normalized_for_content)
    letter_only_string = "".join(c for c in unicodedata.normalize('NFD', clean_word_for_letters) if unicodedata.category(c).startswith('L'))

    if apply_phonetic_normalization:
        letter_only_string = letter_only_string.replace('ٱ', 'ا').replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        letter_only_string = letter_only_string.replace('ص', 'س')

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
                     letter_threshold: float = 0.7, tashkeel_threshold: float = 0.5) -> bool:
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
        tashkeel_sim = correct_tashkeel_count / len(ayah_harakat) if ayah_harakat else 1.0 # Avoid division by zero if ayah_harakat somehow became empty after check
    
    return tashkeel_sim >= tashkeel_threshold

@router.on_event("startup")
async def load_model_on_startup():
    global processor, model
    if model is None or processor is None:
        print(f"Loading ASR model: {MODEL_NAME} on device: {device}")
        try:
            processor = WhisperProcessor.from_pretrained(MODEL_NAME)
            model = WhisperForConditionalGeneration.from_pretrained(MODEL_NAME)
            model.to(device); model.eval()
            print("ASR Model loaded successfully.")
        except Exception as e:
            print(f"Error loading ASR model: {e}"); processor, model = None, None

class IncorrectWordDetail(BaseModel):
    word: str
    position: int

class TranscriptionComparisonResponse(BaseModel):
    transcribed_text: str
    incorrect_ayah_words: List[IncorrectWordDetail]

@router.post("/transcribe_and_compare", response_model=TranscriptionComparisonResponse)
async def transcribe_and_compare_audio(
    audio_file: UploadFile = File(...),
    ayah_text_input: str = Form(...) 
):
    if model is None or processor is None: raise HTTPException(status_code=503, detail="ASR Model is not available.")
    tmp_audio_file_path = None; transcription = ""
    try:
        suffix = os.path.splitext(audio_file.filename)[1] if audio_file.filename and os.path.splitext(audio_file.filename)[1] else ".m4a"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            content = await audio_file.read(); tmp_file.write(content)
            tmp_audio_file_path = tmp_file.name
        waveform_np, _ = librosa.load(tmp_audio_file_path, sr=16000, mono=True)
        input_features = processor(waveform_np, sampling_rate=16000, return_tensors="pt").input_features.to(device)
        with torch.no_grad(): predicted_ids = model.generate(input_features)
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
    except Exception as e:
        print(f"Full traceback of audio processing error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error during audio processing or transcription: {str(e)}")
    finally:
        if audio_file: await audio_file.close()
        if tmp_audio_file_path and os.path.exists(tmp_audio_file_path): os.remove(tmp_audio_file_path)

    raw_ayah_tokens_from_input = ayah_text_input.split()
    ayah_words_info_list_initial: List[Dict[str, Any]] = []
    for raw_token in raw_ayah_tokens_from_input:
        normalized_for_compare = normalize_arabic_text_for_comparison_content(raw_token)
        if normalized_for_compare:
            ayah_words_info_list_initial.append({
                "original_form": raw_token,
                "normalized_form_for_content_comparison": normalized_for_compare
            })
    
    processed_ayah_input_for_basmala_check = normalize_arabic_text_for_comparison_content(ayah_text_input)
    if processed_ayah_input_for_basmala_check == BASMALA_NORMALIZED_FOR_EXACT_MATCH:
        return TranscriptionComparisonResponse(transcribed_text=transcription, incorrect_ayah_words=[])

    transcribed_word_tokens_normalized_for_content_comparison = [
        norm_word for raw_word in transcription.split() 
        if (norm_word := normalize_arabic_text_for_comparison_content(raw_word))
    ]
    
    basmala_normalized_tokens_for_stripping = [
        normalize_arabic_text_for_comparison_content(token).strip() for token in BASMALA_EXACT_TEXT.split()
    ]

    final_ayah_infos_for_loop = ayah_words_info_list_initial[:]
    final_transcribed_tokens_for_loop = transcribed_word_tokens_normalized_for_content_comparison[:]

    if len(final_transcribed_tokens_for_loop) >= len(basmala_normalized_tokens_for_stripping) and \
       final_transcribed_tokens_for_loop[:len(basmala_normalized_tokens_for_stripping)] == basmala_normalized_tokens_for_stripping:
        final_transcribed_tokens_for_loop = final_transcribed_tokens_for_loop[len(basmala_normalized_tokens_for_stripping):]
        temp_ayah_normalized_tokens = [info["normalized_form_for_content_comparison"] for info in final_ayah_infos_for_loop]
        if len(temp_ayah_normalized_tokens) >= len(basmala_normalized_tokens_for_stripping) and \
           temp_ayah_normalized_tokens[:len(basmala_normalized_tokens_for_stripping)] == basmala_normalized_tokens_for_stripping:
            final_ayah_infos_for_loop = final_ayah_infos_for_loop[len(basmala_normalized_tokens_for_stripping):]

    incorrect_ayah_word_details_final: List[IncorrectWordDetail] = []
    user_word_idx = 0
    
    for loop_idx, ayah_info in enumerate(final_ayah_infos_for_loop):
        ayah_word_original_form = ayah_info["original_form"]
        ayah_word_normalized_for_content_compare = ayah_info["normalized_form_for_content_comparison"]
        
        found_match = False; temp_user_idx = user_word_idx
        while temp_user_idx < len(final_transcribed_tokens_for_loop):
            user_word_normalized_for_content_compare = final_transcribed_tokens_for_loop[temp_user_idx]
            
            if check_word_match(ayah_word_normalized_for_content_compare, user_word_normalized_for_content_compare):
                found_match = True; user_word_idx = temp_user_idx + 1
                current_matched_user_word_letters, _ = get_letters_and_harakat(user_word_normalized_for_content_compare, apply_phonetic_normalization=True)
                while user_word_idx < len(final_transcribed_tokens_for_loop):
                    next_user_word_norm_content = final_transcribed_tokens_for_loop[user_word_idx]
                    next_user_word_letters, _ = get_letters_and_harakat(next_user_word_norm_content, apply_phonetic_normalization=True)
                    if next_user_word_letters == current_matched_user_word_letters: user_word_idx += 1
                    else: break
                break 
            temp_user_idx += 1

        if not found_match:
            incorrect_ayah_word_details_final.append(
                IncorrectWordDetail(word=ayah_word_original_form, position=loop_idx)
            )

    return TranscriptionComparisonResponse(
        transcribed_text=transcription,
        incorrect_ayah_words=incorrect_ayah_word_details_final
    )