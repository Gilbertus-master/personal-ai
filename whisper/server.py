"""
Faster-Whisper REST API server for Gilbertus.
Accepts audio files, returns JSON transcription with timestamps and speaker segments.
"""
import os
import tempfile
from flask import Flask, request, jsonify

app = Flask(__name__)

MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
MODEL_DIR = "/models"

model = None


def get_model():
    global model
    if model is None:
        from faster_whisper import WhisperModel
        print(f"Loading model: {MODEL_SIZE} (device={DEVICE}, compute={COMPUTE_TYPE})")
        model = WhisperModel(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            download_root=MODEL_DIR,
        )
        print("Model loaded")
    return model


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": MODEL_SIZE})


@app.route("/transcribe", methods=["POST"])
def transcribe():
    """Transcribe an audio file.

    POST with multipart form:
      - file: audio file (wav, mp3, m4a, opus, flac, ogg)
      - language: optional language code (default: auto-detect)

    Returns JSON with segments (speaker, start, end, text).
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    audio_file = request.files["file"]
    language = request.form.get("language", None)
    if language == "auto":
        language = None

    # Save to temp file
    suffix = os.path.splitext(audio_file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        m = get_model()
        segments_gen, info = m.transcribe(
            tmp_path,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        segments = []
        full_text_parts = []
        for seg in segments_gen:
            segments.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })
            full_text_parts.append(seg.text.strip())

        return jsonify({
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 2),
            "segments": segments,
            "text": " ".join(full_text_parts),
        })

    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    # Preload model at startup
    get_model()
    app.run(host="0.0.0.0", port=9090)
