#!/usr/bin/env python3
"""標準入力のテキストを TTS で音声化し、アバター（DesktopAvatar）に喋らせる。

TTS はローカルの Irodori-TTS（既定）か Gemini TTS を選べる。Irodori-TTS は常駐サーバ
（irodori_server.py）に依頼し、サーバが居なければ起動する。
台本中の `[表情: ジト目]` のようなタグは TTS に渡さず、表情タイムラインに変換してアバターに送る。
アバターに繋がらなければ afplay で再生する。

環境変数:
  VOICE_RECAP_ENGINE irodori（既定）か gemini
  VOICE_RECAP_IRODORI_DIR  Irodori-TTS の clone 先。既定 ~/Desktop/codes/Irodori-TTS
  GEMINI_API_KEY   gemini のとき必須
  VOICE_RECAP_MODEL  既定 gemini-3.8-flash-tts
  VOICE_RECAP_VOICE  既定 voice_q5fi42vgyamm（カスタムボイス "Japanese Female 1"）
  VOICE_RECAP_STYLE  読み上げスタイル指示（speech_metadata.style）
  VOICE_RECAP_DIR    WAV の保存先。既定 ~/Music/voice-recap
  VOICE_RECAP_AVATAR 0 にするとアバターを使わず afplay で再生する。既定 1
"""
import array
import base64
import json
import math
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import wave

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_STYLE = (
    "明るくてノリのいい日本のギャル。テンポよく、フレンドリーに、"
    "でも技術用語や数字ははっきり発音する"
)
AVATAR_SOCK = os.path.expanduser("~/Library/Application Support/desktop-avatar/avatar.sock")
AVATAR_APP = os.path.expanduser("~/Applications/DesktopAvatar.app")
IRODORI_SOCK = os.path.expanduser("~/Library/Application Support/voice-recap/irodori.sock")
IRODORI_LOG = os.path.expanduser("~/Library/Logs/voice-recap/irodori.log")
SCRIPTS = os.path.dirname(os.path.abspath(__file__))

EXPRESSIONS = {
    "通常": "normal", "笑顔": "smile", "ドヤ": "smug", "驚き": "surprised",
    "ジト目": "jitome", "困り": "troubled", "考え中": "thinking", "照れ": "shy",
}
TAG = re.compile(r"\[表情[:：]\s*([^\]]+?)\s*\]")


def parse_script(script: str) -> tuple[str, list[tuple[int, str]]]:
    """タグを除いた本文と、(本文中の文字オフセット, 表情キー) の列を返す。"""
    text, marks, pos = [], [], 0
    for m in TAG.finditer(script):
        text.append(script[pos:m.start()])
        name = m.group(1)
        key = EXPRESSIONS.get(name, name if name in EXPRESSIONS.values() else "normal")
        marks.append((len("".join(text)), key))
        pos = m.end()
    text.append(script[pos:])
    body = "".join(text)
    # 先頭の空白を削ったぶんオフセットをずらす
    lead = len(body) - len(body.lstrip())
    body = body.strip()
    marks = [(max(0, o - lead), k) for o, k in marks]
    return body, marks


def analyze(path: str) -> tuple[float, list[float]]:
    """WAV の長さ（秒）と、無音区間の終わりの時刻の一覧を返す。"""
    with wave.open(path) as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if width != 2:
        return len(frames) / (sr * ch * width), []
    a = array.array("h", frames)
    duration = len(a) / (sr * ch)
    win = int(sr * 0.01) * ch
    silent_run, ends = 0, []
    for i in range(0, len(a) - win, win):
        chunk = a[i:i + win]
        rms = math.sqrt(sum(x * x for x in chunk) / win) / 32768
        if 20 * math.log10(rms + 1e-9) < -40:
            silent_run += 1
        else:
            if silent_run >= 15:  # 150ms 以上の無音のあとで声が始まった位置
                ends.append(i / (sr * ch))
            silent_run = 0
    return duration, ends


def timeline(body: str, marks: list[tuple[int, str]], duration: float, pause_ends: list[float]) -> list[dict]:
    """タグの位置を時刻に直す。文字数の比率で見積もり、近くの息継ぎに寄せる。"""
    if not marks or marks[0][0] > 0:
        marks = [(0, "normal")] + marks
    # 空白は読み上げ時間にほぼ効かないので数えない
    counted = [0]
    for c in body:
        counted.append(counted[-1] + (0 if c.isspace() else 1))
    total = max(1, counted[-1])
    out = []
    for offset, key in marks:
        if offset == 0:
            t = 0.0
        else:
            t = counted[min(offset, len(body))] / total * duration
            near = [e for e in pause_ends if abs(e - t) <= 0.6]
            if near:
                t = min(near, key=lambda e: abs(e - t))
        out.append({"t": round(t, 3), "expr": key})
    return out


def send_avatar(msg: dict, timeout: float = 3.0) -> dict | None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(AVATAR_SOCK)
            s.sendall((json.dumps(msg) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
        return json.loads(buf.decode() or "{}")
    except (OSError, ValueError):
        return None


def play_on_avatar(path: str, tl: list[dict]) -> str | None:
    """アバターに喋らせる。失敗したら理由を返す。"""
    msg = {"type": "speak", "wav": path, "timeline": tl}
    r = send_avatar(msg)
    if r is None:
        if not os.path.isdir(AVATAR_APP):
            return "DesktopAvatar.app が入っていない"
        subprocess.run(["open", "-g", AVATAR_APP], check=False)
        deadline = time.time() + 3
        while r is None and time.time() < deadline:
            time.sleep(0.1)
            r = send_avatar(msg)
        if r is None:
            return "アバターが起動しない"
    if not r.get("ok"):
        return f"アバターがエラーを返した: {r.get('error')}"
    return None


def synth_gemini(text: str, path: str) -> str | None:
    """Gemini TTS で path に WAV を書く。失敗したら理由を返す。"""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return "GEMINI_API_KEY が未設定です"
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
        return f"curl エラー: {res.stderr.strip()}"
    payload, _, status = res.stdout.rpartition("\n")
    if status != "200":
        return f"Gemini API エラー {status}: {payload[:1000]}"
    data = json.loads(payload)

    audios = [
        c for s in data.get("steps", []) if s.get("type") == "model_output"
        for c in s.get("content", []) if c.get("type") == "audio"
    ]
    if not audios:
        return f"音声がレスポンスに含まれていません: {json.dumps(data)[:500]}"

    with open(path, "wb") as f:
        f.write(base64.b64decode(audios[-1]["data"]))
    return None


def irodori_request(msg: dict, timeout: float) -> dict | None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(IRODORI_SOCK)
            s.sendall((json.dumps(msg, ensure_ascii=False) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
        return json.loads(buf.decode() or "{}")
    except (OSError, ValueError):
        return None


def start_irodori() -> str | None:
    """常駐サーバを起動し、ソケットが開くまで待つ。失敗したら理由を返す。"""
    irodori_dir = os.path.expanduser(os.environ.get("VOICE_RECAP_IRODORI_DIR", "~/Desktop/codes/Irodori-TTS"))
    python = os.path.join(irodori_dir, ".venv", "bin", "python")
    if not os.path.isfile(python):
        return f"Irodori-TTS の環境が見つからない（{python}）"
    os.makedirs(os.path.dirname(IRODORI_LOG), exist_ok=True)
    with open(IRODORI_LOG, "ab") as log:
        proc = subprocess.Popen([python, os.path.join(SCRIPTS, "irodori_server.py")], cwd=irodori_dir,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    # 初回はモデルのダウンロードが入るので長めに待つ
    deadline = time.time() + 600
    while time.time() < deadline:
        if proc.poll() is not None:
            with open(IRODORI_LOG, errors="replace") as f:
                tail = f.read().strip().splitlines()[-1:]
            return f"Irodori-TTS サーバが終了した: {tail[0] if tail else '?'}（ログ {IRODORI_LOG}）"
        if os.path.exists(IRODORI_SOCK):
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.connect(IRODORI_SOCK)
                return None
            except OSError:
                pass
        time.sleep(0.5)
    return f"Irodori-TTS サーバが起動しない（ログ {IRODORI_LOG}）"


def synth_irodori(text: str, path: str) -> str | None:
    """Irodori-TTS の常駐サーバで path に WAV を書く。失敗したら理由を返す。"""
    msg = {"text": text, "out": path}
    r = irodori_request(msg, timeout=300)
    if r is None:
        reason = start_irodori()
        if reason:
            return reason
        r = irodori_request(msg, timeout=300)
    if r is None:
        return "Irodori-TTS サーバが応答しない"
    if not r.get("ok"):
        return f"Irodori-TTS エラー: {r.get('error', r)}"
    return None


def main() -> int:
    engine = os.environ.get("VOICE_RECAP_ENGINE", "irodori")
    if engine not in ("irodori", "gemini"):
        print(f"VOICE_RECAP_ENGINE は irodori か gemini: {engine}", file=sys.stderr)
        return 2
    text, marks = parse_script(sys.stdin.read())
    if not text:
        print("読み上げるテキストが空です", file=sys.stderr)
        return 2

    # 一時フォルダは macOS に掃除されるため、消えない場所に残す
    out_dir = os.path.expanduser(os.environ.get("VOICE_RECAP_DIR", "~/Music/voice-recap"))
    os.makedirs(out_dir, exist_ok=True)
    # Irodori の出力を参照ボイスの作り直しに混ぜないよう、名前で見分けられるようにする
    suffix = "-irodori" if engine == "irodori" else ""
    path = os.path.join(out_dir, f"recap-{time.strftime('%Y%m%d-%H%M%S')}{suffix}.wav")
    err = (synth_irodori if engine == "irodori" else synth_gemini)(text, path)
    if err:
        print(err, file=sys.stderr)
        return 1
    reason = "VOICE_RECAP_AVATAR=0"
    if os.environ.get("VOICE_RECAP_AVATAR", "1") != "0":
        duration, pause_ends = analyze(path)
        reason = play_on_avatar(path, timeline(text, marks, duration, pause_ends))
    if reason:
        if reason != "VOICE_RECAP_AVATAR=0":
            print(f"アバターを使わず afplay で再生します（{reason}）", file=sys.stderr)
        # 再生は切り離して、Claude のターンをブロックしない
        subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
