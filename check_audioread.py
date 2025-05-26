# test_audioread_file.py
import audioread
import traceback

# IMPORTANT: Replace with the ACTUAL path to your audio file
# Using a raw string (r"...") or forward slashes can help with Windows paths
audio_file_path = r"Voix 008.m4a"
# Or, if the file is in the same directory as the script:
# audio_file_path = "Voix 008 (1).m4a"


print(f"Attempting to open: {audio_file_path}")
try:
    with audioread.audio_open(audio_file_path) as f:
        print(f"Audioread SUCCESS: Duration: {f.duration:.2f}s, Channels: {f.channels}, Samplerate: {f.samplerate}")
        # You can try to read a bit of data
        # count = 0
        # for buf in f:
        #     count += 1
        #     if count > 5: # just read a few buffers
        #         break
        # print(f"Read {count} buffers.")
except Exception as e:
    print(f"Audioread FAILED: {e}")
    print("\n--- Full Traceback ---")
    traceback.print_exc()