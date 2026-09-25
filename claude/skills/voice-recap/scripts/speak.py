#!/usr/bin/env python3
"""標準入力のテキストを Gemini TTS で音声化し、afplay で再生する。

環境変数:
  GEMINI_API_KEY   必須
  VOICE_RECAP_MODEL  既定 gemini-3.8-flash-tts
  VOICE_RECAP_VOICE  既定 voice_q5fi42vgyamm（カスタムボイス "Japanese Female 1"）
  VOICE_RECAP_STYLE  読み上げスタイル指示（speech_metadata.style）
  VOICE_RECAP_DIR    WAV の保存先。既定 ~/Music/voice-recap
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import time

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_STYLE = (
    "明るくてノリのいい日本のギャル。テンポよく、フレンドリーに、"
    "でも技術用語や数字ははっきり発音する"
)


def main() -> int:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY が未設定です", file=sys.stderr)
        return 2
    text = sys.stdin.read().strip()
    if not text:
        print("読み上げるテキストが空です", file=sys.stderr)
        return 2

    body = {
        "model": os.environ.get("VOICE_RECAP_MODEL", "gemini-3.8-flash-tts"),
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": text,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": os.environ.get("VOICE_RECAP_STYLE", DEFAULT_STYLE),
                }],
            }],
        }],
        "response_format": {"type": "audio", "mime_type": "audio/wav"},
        "generation_config": {
            "speech_config": [{"voice": os.environ.get("VOICE_RECAP_VOICE", "voice_q5fi42vgyamm")}],
        },
    }
    # python.org 版 Python は CA 証明書が未導入のことがあるため、TLS は curl に任せる。
    # API キーは argv に載せず、ヘッダを標準入力から渡す。
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(body, f)
        body_path = f.name
    try:
        res = subprocess.run(
            ["curl", "-sS", "--max-time", "120", "-w", "\n%{http_code}", "-X", "POST", ENDPOINT,
             "-H", "@-", "-H", "Content-Type: application/json", "--data-binary", f"@{body_path}"],
            input=f"x-goog-api-key: {key}\n", capture_output=True, text=True,
        )
    finally:
        os.unlink(body_path)
    if res.returncode != 0:
        print(f"curl エラー: {res.stderr.strip()}", file=sys.stderr)
        return 1
    payload, _, status = res.stdout.rpartition("\n")
    if status != "200":
        print(f"Gemini API エラー {status}: {payload[:1000]}", file=sys.stderr)
        return 1
    data = json.loads(payload)

    audios = [
        c for s in data.get("steps", []) if s.get("type") == "model_output"
        for c in s.get("content", []) if c.get("type") == "audio"
    ]
    if not audios:
        print(f"音声がレスポンスに含まれていません: {json.dumps(data)[:500]}", file=sys.stderr)
        return 1

    # 一時フォルダは macOS に掃除されるため、消えない場所に残す
    out_dir = os.path.expanduser(os.environ.get("VOICE_RECAP_DIR", "~/Music/voice-recap"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"recap-{time.strftime('%Y%m%d-%H%M%S')}.wav")
    with open(path, "wb") as f:
        f.write(base64.b64decode(audios[-1]["data"]))

    # 再生は切り離して、Claude のターンをブロックしない
    subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
