# scripts/preload_model.py
from transformers import WhisperProcessor, WhisperForConditionalGeneration

model_name = "tarteel-ai/whisper-base-ar-quran"

print(f"Attempting to download/cache model: {model_name}")
try:
    processor = WhisperProcessor.from_pretrained(model_name)
    model = WhisperForConditionalGeneration.from_pretrained(model_name)
    print(f"Successfully pre-loaded model and processor for {model_name}")
except Exception as e:
    print(f"Error pre-loading model: {e}")
    # Depending on your Docker build setup, you might want to exit(1) here
    # to fail the build if the model can't be downloaded.

# If you chose the other model:
# model_name_diacritics = "moatazlumin/Arabic_ASR_whisper_small_with_diacritics"
# print(f"Attempting to download/cache model: {model_name_diacritics}")
# try:
#     WhisperProcessor.from_pretrained(model_name_diacritics)
#     WhisperForConditionalGeneration.from_pretrained(model_name_diacritics)
#     print(f"Successfully pre-loaded model and processor for {model_name_diacritics}")
# except Exception as e:
#     print(f"Error pre-loading model {model_name_diacritics}: {e}")