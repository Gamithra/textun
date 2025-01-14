import azure.cognitiveservices.speech as speechsdk
from openai import OpenAI
from obswebsocket import obsws, requests
from secrets import SPEECH_KEY, SERVICE_REGION, OPENAI_KEY

# === Configuration ===
OBS_HOST = "localhost"  # OBS WebSocket Host
OBS_PORT = 4455         # OBS WebSocket Port (Updated)
OBS_SOURCE = "Subtitles"  # Name of the text source in OBS
MAX_SUBTITLE_LENGTH = 60  # Maximum characters per subtitle chunk

# Initialize Azure Speech Service
speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SERVICE_REGION)
speech_config.speech_recognition_language = "is-IS"
audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

# Initialize OpenAI API
client = OpenAI(api_key=OPENAI_KEY)

# Connect to OBS WebSocket
obs_client = obsws(OBS_HOST, OBS_PORT, None)
try:
    obs_client.connect()
    print("Connected to OBS WebSocket!")
    # Test connection by updating OBS with a test subtitle
    obs_client.call(requests.SetTextGDIPlusProperties(
        source=OBS_SOURCE,
        text="Testing connection to OBS..."
    ))
    print("Test subtitle sent to OBS!")
except Exception as e:
    print(f"Failed to connect to OBS WebSocket: {e}")
    exit(1)

# === Functions ===

def update_obs_subtitles(text):
    """Update the OBS text source (FreeType 2) with new subtitles."""
    try:
        # Use SetSourceSettings for FreeType 2 sources
        response = obs_client.call(requests.SetInputSettings(
            inputName=OBS_SOURCE,
            inputSettings={"text": text}  # Update the 'text' field
        ))
        print(f"OBS Response: {response}")  # Print response from OBS
        print(f"Successfully updated OBS subtitles to: {text}")
    except Exception as e:
        print(f"Error updating OBS: {e}")


def translate_text(text):
    """Translate Icelandic text to English using OpenAI."""
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a live translator. Translate Icelandic text to English for real-time subtitles."},
                {"role": "user", "content": f"Translate the following Icelandic text to English:\n\n{text}"}
            ]
        )
        if "error" not in completion:
            return completion.choices[0].message.content.strip()
        else:
            print(f"Translation error: {completion.text}")
            return "[Translation Error]"
    except Exception as e:
        print(f"Error during translation: {e}")
        return "[Translation Error]"

def display_subtitles(text):
    """Display subtitles in chunks suitable for OBS."""
    words = text.split()
    current_chunk = []
    subtitle_chunks = []

    update_obs_subtitles(text)

    for word in words:
        if len(" ".join(current_chunk) + len(word) + 1) <= MAX_SUBTITLE_LENGTH:
            current_chunk.append(word)
            print(current_chunk)
        else:
            subtitle_chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            print(current_chunk)

    subtitle_chunks.append(" ".join(current_chunk))  # Add the last chunk

    print(f"Subtitle chunks: {subtitle_chunks}")

    for chunk in subtitle_chunks:
        update_obs_subtitles(chunk)

def on_recognized(event):
    """Callback for recognized speech."""
    if event.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f"Recognized (Icelandic): {event.result.text}")
        translated_text = translate_text(event.result.text)
        print(f"Translated (English): {translated_text}")
        display_subtitles(translated_text)
    elif event.result.reason == speechsdk.ResultReason.NoMatch:
        print("No speech could be recognized.")
    elif event.result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = event.result.cancellation_details
        print(f"Recognition canceled: {cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print(f"Error details: {cancellation_details.error_details}")

# === Main Program ===
def main():
    """Start speech recognition and translation."""
    recognizer.recognized.connect(on_recognized)
    recognizer.start_continuous_recognition()
    
    print("Listening for speech. Press Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(1)  # Keep the program running
    except KeyboardInterrupt:
        print("Stopping...")
        recognizer.stop_continuous_recognition()
        obs_client.disconnect()

if __name__ == "__main__":
    main()

