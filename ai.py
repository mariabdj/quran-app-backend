# ai.py
import torch
import torchaudio
import librosa
from transformers import WhisperProcessor, WhisperForConditionalGeneration
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
import unicodedata
import re
from typing import List, Tuple

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
SUKUN = '\u0652'
TANWEEN_FATH = '\u064B'  # Fathatan
TANWEEN_DAMM = '\u064C'  # Dammatan
TANWEEN_KASR = '\u064D'  # Kasratan

RELEVANT_HARAKAT = [FATHA, DAMMA, KASRA, SUKUN, TANWEEN_FATH, TANWEEN_DAMM, TANWEEN_KASR]

BASMALA_EXACT_TEXT = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"
# For robust token matching, we'll normalize Basmala tokens once
# The normalization used for basmala check must be consistent with how text is split into words.
# We will define normalized Basmala tokens later based on the normalize_arabic_text_for_comparison function.

# --- Helper Functions for Text Processing and Comparison ---

def normalize_arabic_text_for_comparison(text: str) -> str:
    """
    Normalizes Arabic text for comparison.
    - Removes Quranic symbols, verse numbers, etc.
    - Removes dagger alif (ٰ).
    - KEEPS Alef variants, Ta Marbuta, Alif Maqsura distinct.
    """
    # text = unicodedata.normalize('NFD', text) # Decompose AFTER initial cleaning for some symbols
    
    # Remove Quranic symbols like ۝, verse numbers, etc.
    text = re.sub(r"[\u0600-\u0605\u0610-\u061A\u06D6-\u06ED\u08F0-\u08FF]+", "", text) # Quranic marks etc.
    text = re.sub(r"۝\s*\d*\s*", " ", text) # Ayah markers and numbers
    text = re.sub(r"[0-9]+", "", text) # Remove all numbers

    # Specific character normalizations (USER REQUESTED TO KEEP MOST DISTINCT)
    # text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ٱ', 'ا') # REMOVED
    # text = text.replace('ى', 'ي') # REMOVED
    # text = text.replace('ة', 'ه') # REMOVED
    
    text = text.replace('ٰ', '') # Dagger alif is usually stylistic for 'ا'

    # Normalize whitespace (replace multiple spaces/tabs/newlines with a single space)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

BASMALA_NORMALIZED_TOKENS = [
    normalize_arabic_text_for_comparison(token).strip()
    for token in BASMALA_EXACT_TEXT.split()
]
BASMALA_NORMALIZED_TEXT_FOR_EXACT_MATCH = " ".join(BASMALA_NORMALIZED_TOKENS)


def get_letters_and_harakat(word: str) -> Tuple[str, List[Tuple[int, str]]]:
    """
    Extracts base letters and specific harakat from a word.
    Returns a tuple: (letters_string, list_of_harakat_with_index).
    Harakat are associated with the index of the NFD letter they are on.
    """
    # For letter string, we want a "clean" sequence of letters.
    # NFKC combines and composes, then we strip non-letters.
    clean_word_for_letters = unicodedata.normalize('NFKC', word)
    letter_only_string = "".join(c for c in unicodedata.normalize('NFD', clean_word_for_letters) if unicodedata.category(c).startswith('L'))
    
    harakat_tuples_simple = []
    current_letter_idx_simple = -1
    temp_letters_for_indices = [] # Keep track of letters to correctly index harakat

    # Iterate through NFD form of the original word to accurately map harakat
    for char in unicodedata.normalize('NFD', word):
        if unicodedata.category(char).startswith('L'):
            temp_letters_for_indices.append(char)
            current_letter_idx_simple = len(temp_letters_for_indices) - 1
        elif char in RELEVANT_HARAKAT and current_letter_idx_simple != -1:
            # Associate haraka with the last encountered letter's index in the NFD letter stream
            harakat_tuples_simple.append((current_letter_idx_simple, char))
            
    return letter_only_string, harakat_tuples_simple


def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def check_word_match(ayah_word_processed: str, user_word_processed: str,
                     letter_threshold: float = 0.8, tashkeel_threshold: float = 0.5) -> bool:
    ayah_letters, ayah_harakat = get_letters_and_harakat(ayah_word_processed)
    user_letters, user_harakat = get_letters_and_harakat(user_word_processed)

    if not ayah_letters and not user_letters: return True
    if not ayah_letters or not user_letters: return False

    dist = levenshtein_distance(ayah_letters, user_letters)
    max_len = max(len(ayah_letters), len(user_letters))
    letter_sim = (max_len - dist) / max_len if max_len > 0 else (1.0 if dist == 0 else 0.0)
    
    if letter_sim < letter_threshold:
        return False

    if not ayah_harakat:
        tashkeel_sim = 1.0
    else:
        correct_tashkeel_count = 0
        set_user_harakat = set(user_harakat)
        for h_a in ayah_harakat:
            if h_a in set_user_harakat:
                correct_tashkeel_count += 1
        tashkeel_sim = correct_tashkeel_count / len(ayah_harakat)

    return tashkeel_sim >= tashkeel_threshold

# --- FastAPI Lifespan Events for Model Loading ---
@router.on_event("startup")
async def load_model_on_startup():
    global processor, model
    if model is None or processor is None:
        print(f"Loading ASR model: {MODEL_NAME} on device: {device}")
        try:
            processor = WhisperProcessor.from_pretrained(MODEL_NAME)
            model = WhisperForConditionalGeneration.from_pretrained(MODEL_NAME)
            model.to(device)
            model.eval()
            print("ASR Model loaded successfully.")
        except Exception as e:
            print(f"Error loading ASR model: {e}")
            processor, model = None, None

class TranscriptionComparisonResponse(BaseModel):
    transcribed_text: str
    incorrect_ayah_words: List[str]

# --- API Endpoint ---
@router.post("/transcribe_and_compare", response_model=TranscriptionComparisonResponse)
async def transcribe_and_compare_audio(
    audio_file: UploadFile = File(...),
    ayah_text_input: str = Form(..., alias="ayah_text") # Use alias for clarity if needed
):
    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="ASR Model is not available.")

    try:
        audio_bytes = await audio_file.read()
        waveform, sample_rate = torchaudio.load(audio_file.file, format=audio_file.filename.split(".")[-1] if audio_file.filename else None)
        if sample_rate != 16000:
            waveform = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)(waveform)
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        input_features = processor(waveform.squeeze().numpy(), sampling_rate=16000, return_tensors="pt").input_features.to(device)
        with torch.no_grad():
            predicted_ids = model.generate(input_features)
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
    except Exception as e:
        print(f"Error during audio processing or transcription: {e}")
        raise HTTPException(status_code=500, detail=f"Error during audio processing or transcription: {str(e)}")
    finally:
        await audio_file.close()

    # --- Basmala Handling & Text Preparation ---
    # 1. Check if the entire ayah_text_input is Basmala
    processed_ayah_input_for_basmala_check = normalize_arabic_text_for_comparison(ayah_text_input).strip()
    if processed_ayah_input_for_basmala_check == BASMALA_NORMALIZED_TEXT_FOR_EXACT_MATCH:
        return TranscriptionComparisonResponse(
            transcribed_text=transcription,
            incorrect_ayah_words=[]
        )

    # 2. Prepare Ayah text and Transcription for comparison, potentially stripping leading Basmala
    original_ayah_words_full = [w for w in normalize_arabic_text_for_comparison(ayah_text_input).split() if w]
    transcribed_words_full = [w for w in normalize_arabic_text_for_comparison(transcription).split() if w]

    # Store the full original Ayah words (after initial normalization for splitting) to return in errors
    ayah_words_to_compare_original_form = original_ayah_words_full[:]
    
    # These lists will be used for the actual comparison logic
    ayah_words_for_comparison_loop = original_ayah_words_full[:]
    transcribed_words_for_comparison_loop = transcribed_words_full[:]

    # Check and strip leading Basmala from transcription
    if len(transcribed_words_for_comparison_loop) >= len(BASMALA_NORMALIZED_TOKENS) and \
       transcribed_words_for_comparison_loop[:len(BASMALA_NORMALIZED_TOKENS)] == BASMALA_NORMALIZED_TOKENS:
        transcribed_words_for_comparison_loop = transcribed_words_for_comparison_loop[len(BASMALA_NORMALIZED_TOKENS):]
        
        # If user said Basmala, and Ayah also starts with Basmala (and Ayah is not *only* Basmala), strip from Ayah too
        if len(ayah_words_for_comparison_loop) >= len(BASMALA_NORMALIZED_TOKENS) and \
           ayah_words_for_comparison_loop[:len(BASMALA_NORMALIZED_TOKENS)] == BASMALA_NORMALIZED_TOKENS:
            ayah_words_for_comparison_loop = ayah_words_for_comparison_loop[len(BASMALA_NORMALIZED_TOKENS):]
            # Also adjust the list used for reporting errors if Ayah's Basmala is skipped for comparison
            ayah_words_to_compare_original_form = ayah_words_to_compare_original_form[len(BASMALA_NORMALIZED_TOKENS):]


    # --- Comparison Loop ---
    incorrect_ayah_word_originals_final = []
    user_word_idx = 0
    
    # Ensure we use the correct list of original words for error reporting if Basmala was stripped from Ayah
    # The `ayah_words_for_comparison_loop` contains the words (post-Basmala stripping if any) to iterate over for matching.
    # The `ayah_words_to_compare_original_form` contains their original forms.
    
    # We need to map the words in `ayah_words_for_comparison_loop` (which are processed)
    # back to their actual original forms from the input `ayah_text_input` for error reporting.
    # The current `ayah_words_to_compare_original_form` *is* already the list of words
    # (normalized by normalize_arabic_text_for_comparison) that correspond to the words
    # we are iterating through in `ayah_words_for_comparison_loop`.

    for i, p_ayah_word in enumerate(ayah_words_for_comparison_loop):
        # The word to report if incorrect is from `ayah_words_to_compare_original_form` at the same index `i`
        original_form_of_current_ayah_word = ayah_words_to_compare_original_form[i]
        
        found_match = False
        search_start_user_idx = user_word_idx

        temp_user_idx = search_start_user_idx
        while temp_user_idx < len(transcribed_words_for_comparison_loop):
            p_user_word = transcribed_words_for_comparison_loop[temp_user_idx]
            
            # The words p_ayah_word and p_user_word are already normalized by normalize_arabic_text_for_comparison
            if check_word_match(p_ayah_word, p_user_word):
                found_match = True
                user_word_idx = temp_user_idx + 1
                
                current_matched_user_word_letters, _ = get_letters_and_harakat(p_user_word)
                while user_word_idx < len(transcribed_words_for_comparison_loop):
                    next_user_word_letters, _ = get_letters_and_harakat(transcribed_words_for_comparison_loop[user_word_idx])
                    if next_user_word_letters == current_matched_user_word_letters:
                        user_word_idx += 1
                    else:
                        break
                break 
            temp_user_idx += 1

        if not found_match:
            incorrect_ayah_word_originals_final.append(original_form_of_current_ayah_word)

    return TranscriptionComparisonResponse(
        transcribed_text=transcription,
        incorrect_ayah_words=incorrect_ayah_word_originals_final
    )