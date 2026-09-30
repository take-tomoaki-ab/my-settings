#!/usr/bin/env python3
"""Irodori-TTS を常駐させ、Unix ソケットで読み上げ依頼を受ける。

モデルの読み込みに十数秒かかるので、speak.py が初回に起動して、以降は使い回す。
一定時間依頼が来なければ終了してメモリを返す。Irodori-TTS の環境で動かす:

  uv run --project ~/Desktop/codes/Irodori-TTS --no-sync python irodori_server.py

依頼（1 行の JSON）: {"text": "...", "out": "/path/to.wav"}
応答（1 行の JSON）: {"ok": true, "duration": 12.3} または {"ok": false, "error": "..."}

環境変数:
  VOICE_RECAP_IRODORI_DIR   既定 ~/Desktop/codes/Irodori-TTS
  VOICE_RECAP_IRODORI_MODEL  既定 Aratako/Irodori-TTS-v4.1-Small-MF
  VOICE_RECAP_IRODORI_DEVICE 既定 mps（使えなければ cpu）
  VOICE_RECAP_CAPTION        声と話し方の指示（キャプション）。既定は付けない。
                             付けると短い文の長さを長めに見積もり、余りを意味のない声で埋めやすい
  VOICE_RECAP_SEED           既定 0。文ごとの声のブレを抑えるため固定する
  VOICE_RECAP_IDLE           何秒依頼がなければ終了するか。既定 1800
  VOICE_RECAP_VOICE_NAME / VOICE_RECAP_VOICES_DIR  build_voice.py と同じ
"""
import json
import os
import re
import signal
import socket
import sys
import time
import wave

import torch

sys.path.insert(0, os.path.expanduser(os.environ.get("VOICE_RECAP_IRODORI_DIR", "~/Desktop/codes/Irodori-TTS")))
from irodori_tts.inference_runtime import (
    InferenceRuntime,
    RuntimeKey,
    SamplingRequest,
    download_hf_checkpoint,
)

SOCK = os.path.expanduser("~/Library/Application Support/voice-recap/irodori.sock")
# 1 回に合成する長さ。長すぎると読み飛ばしや崩れが出やすい
MAX_CHUNK_CHARS = 80
GAP_SEC = 0.15
KANJI = re.compile(r"[\u4e00-\u9fff0-9０-９]")


def max_seconds(text: str) -> float:
    """読み上げ時間の上限の見積もり。漢字と数字は読みが長いので重めに数える。

    長さ予測は短い文ほど長めに外れ、余った時間を意味のない声で埋めてしまうので、これで抑える。
    """
    return 0.8 + sum(0.3 if KANJI.match(c) else 0.17 for c in text)


def chunks(text: str) -> list[str]:
    """文末で区切り、MAX_CHUNK_CHARS 以内にまとめる。"""
    sentences = [s.strip() for s in re.findall(r"[^。！？!?\n]+[。！？!?]*", text) if s.strip()]
    out, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) > MAX_CHUNK_CHARS:
            out.append(cur)
            cur = ""
        cur += s
    if cur:
        out.append(cur)
    return out


class Server:
    def __init__(self) -> None:
        device = os.environ.get("VOICE_RECAP_IRODORI_DEVICE", "mps")
        if device == "mps" and not torch.backends.mps.is_available():
            device = "cpu"
        ckpt = download_hf_checkpoint(
            os.environ.get("VOICE_RECAP_IRODORI_MODEL", "Aratako/Irodori-TTS-v4.1-Small-MF"))
        self.runtime = InferenceRuntime.from_key(RuntimeKey(
            checkpoint=ckpt, model_device=device, codec_device=device))
        voices = os.path.expanduser(os.environ.get(
            "VOICE_RECAP_VOICES_DIR", "~/Library/Application Support/voice-recap/voices"))
        self.ref = os.path.join(voices, os.environ.get("VOICE_RECAP_VOICE_NAME", "gal"), "ref.pt")
        if not os.path.isfile(self.ref):
            raise FileNotFoundError(f"参照ボイスがない: {self.ref}（build_voice.py で作る）")
        self.caption = os.environ.get("VOICE_RECAP_CAPTION", "").strip() or None
        self.seed = int(os.environ.get("VOICE_RECAP_SEED", "0"))

    def synthesize(self, text: str, out: str) -> float:
        sr, pieces = None, []
        for part in chunks(text):
            req = SamplingRequest(text=part, caption=self.caption, ref_latent=self.ref, seed=self.seed)
            r = self.runtime.synthesize(req)
            limit = max_seconds(part)
            if r.audio.shape[-1] / r.sample_rate > limit:
                req.seconds = limit
                r = self.runtime.synthesize(req)
            sr = r.sample_rate
            pieces.append(r.audio.detach().to("cpu", torch.float32).mean(dim=0))
            pieces.append(torch.zeros(int(sr * GAP_SEC)))
        if not pieces:
            raise ValueError("読み上げるテキストが空")
        # MPS は使い終わった領域を抱えたままにするので、依頼ごとに返す（放っておくと 10 GB を超える）
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        audio = torch.cat(pieces[:-1]).clamp(-1, 1)
        pcm = (audio * 32767).round().to(torch.int16).numpy().tobytes()
        tmp = out + ".part"
        with wave.open(tmp, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm)
        os.replace(tmp, out)
        return audio.numel() / sr

    def handle(self, conn: socket.socket) -> None:
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(65536)
            if not chunk:
                break
            buf += chunk
        if not buf.strip():
            return  # speak.py の起動確認の接続
        try:
            req = json.loads(buf.decode())
            duration = self.synthesize(req["text"], req["out"])
            res = {"ok": True, "duration": round(duration, 3)}
        except Exception as e:  # 依頼ごとの失敗でサーバは落とさない
            res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        try:
            conn.sendall((json.dumps(res, ensure_ascii=False) + "\n").encode())
        except OSError:
            pass  # 依頼元が先に切れた


def main() -> int:
    idle = float(os.environ.get("VOICE_RECAP_IDLE", "1800"))
    server = Server()
    # 1 回空打ちして、初回依頼の待ち時間（デバイスのウォームアップ）を減らす
    server.runtime.synthesize(SamplingRequest(text="あ。", ref_latent=server.ref, seed=0))
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()

    os.makedirs(os.path.dirname(SOCK), exist_ok=True)
    if os.path.exists(SOCK):
        os.unlink(SOCK)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(SOCK)
    s.listen(4)
    s.settimeout(idle)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print(f"ready: {SOCK}", flush=True)
    try:
        while True:
            try:
                conn, _ = s.accept()
            except socket.timeout:
                print(f"{idle:.0f} 秒依頼がないので終了する", flush=True)
                return 0
            with conn:
                t0 = time.time()
                server.handle(conn)
                print(f"handled in {time.time() - t0:.1f}s", flush=True)
    finally:
        s.close()
        if os.path.exists(SOCK):
            os.unlink(SOCK)


if __name__ == "__main__":
    sys.exit(main())
