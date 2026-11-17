#!/usr/bin/env python3
"""Real-time Russian speech recognition from a 4-channel LC-AC108 array.

Audio path: ALSA S32_LE/4ch/16kHz -> SoX mono S16_LE -> Vosk.
"""

import json
import subprocess
import sys
from pathlib import Path

from vosk import Model, KaldiRecognizer

BASE_DIR = Path.home() / "voice-assistant"
MODEL_DIR = BASE_DIR / "models" / "vosk-model-small-ru-0.22"
ALSA_DEVICE = "hw:CARD=lcac1084mic,DEV=0"
SAMPLE_RATE = 16000


def main() -> int:
    if not MODEL_DIR.is_dir():
        print(f"Не найдена модель Vosk: {MODEL_DIR}", file=sys.stderr)
        return 1

    print("Загружаю русскую модель Vosk...", flush=True)
    model = Model(str(MODEL_DIR))
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)

    arecord_cmd = [
        "arecord", "-q", "-D", ALSA_DEVICE,
        "-f", "S32_LE", "-r", str(SAMPLE_RATE),
        "-c", "4", "-t", "raw",
    ]
    sox_cmd = [
        "sox", "-q",
        "-t", "raw", "-r", str(SAMPLE_RATE),
        "-e", "signed-integer", "-b", "32", "-c", "4", "-",
        "-t", "raw", "-r", str(SAMPLE_RATE),
        "-e", "signed-integer", "-b", "16", "-c", "1", "-",
        "remix", "-",
    ]

    recorder = None
    converter = None
    try:
        recorder = subprocess.Popen(
            arecord_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        assert recorder.stdout is not None
        converter = subprocess.Popen(
            sox_cmd,
            stdin=recorder.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        recorder.stdout.close()

        assert converter.stdout is not None
        print("Микрофоны запущены.")
        print("Говори по-русски. Для выхода нажми Ctrl+C.\n", flush=True)

        while True:
            data = converter.stdout.read(3200)
            if not data:
                print("Поток звука завершился.", file=sys.stderr)
                return 2
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                if text:
                    print("Распознано:", text, flush=True)

    except KeyboardInterrupt:
        print("\nОстановка.")
        return 0
    except FileNotFoundError as exc:
        print(f"Не найдена необходимая программа: {exc}", file=sys.stderr)
        return 1
    finally:
        for proc in (converter, recorder):
            if proc is not None and proc.poll() is None:
                proc.terminate()
        for proc in (converter, recorder):
            if proc is not None:
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
