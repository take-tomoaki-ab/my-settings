#!/usr/bin/env python3
"""手持ちの WAV から Irodori-TTS 用の参照ボイスを作る。

WAV を無音で 3〜10 秒ほどの発話に切り分けて clips/ に保存し、DACVAE で潜在表現に
エンコードしたものを ref.pt にまとめる。irodori_server.py はこの ref.pt を参照音声として使う。
Irodori-TTS の環境で動かす:

  uv run --project ~/Desktop/codes/Irodori-TTS --no-sync python build_voice.py ~/Music/voice-recap/recap-*.wav

環境変数:
  VOICE_RECAP_VOICE_NAME  ボイス名。既定 gal
  VOICE_RECAP_VOICES_DIR  保存先。既定 ~/Library/Application Support/voice-recap/voices
  VOICE_RECAP_IRODORI_DIR 既定 ~/Desktop/codes/Irodori-TTS
  VOICE_RECAP_CODEC       既定 Aratako/Semantic-DACVAE-Japanese-32dim
"""
import argparse
import array
import math
import os
import sys
import wave

MIN_SEC, TARGET_SEC, MAX_REF_SEC = 3.0, 6.0, 120.0
IRODORI_DIR = os.path.expanduser(os.environ.get("VOICE_RECAP_IRODORI_DIR", "~/Desktop/codes/Irodori-TTS"))


def read_mono16(path: str) -> tuple[array.array, int]:
    with wave.open(path) as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"16bit PCM の WAV だけ扱える: {path}")
    a = array.array("h", frames)
    if ch > 1:
        a = array.array("h", a[::ch])
    return a, sr


def split(a: array.array, sr: int) -> list[array.array]:
    """200ms 以上の無音の真ん中で切り、TARGET_SEC 前後の塊にまとめる。"""
    win = int(sr * 0.01)
    silent = []
    for i in range(0, len(a) - win, win):
        chunk = a[i:i + win]
        rms = math.sqrt(sum(x * x for x in chunk) / win) / 32768
        silent.append(20 * math.log10(rms + 1e-9) < -35)
    cuts, run = [], 0
    for k, s in enumerate(silent):
        if s:
            run += 1
            continue
        if run >= 20:
            cuts.append((k - run // 2) * win)
        run = 0
    cuts.append(len(a))
    out, start = [], 0
    for c in cuts:
        sec = (c - start) / sr
        if sec >= TARGET_SEC or (c == len(a) and sec >= MIN_SEC):
            out.append(a[start:c])
            start = c
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("wavs", nargs="+")
    p.add_argument("--name", default=os.environ.get("VOICE_RECAP_VOICE_NAME", "gal"))
    p.add_argument("--device", default="cpu")
    args = p.parse_args()

    voices = os.path.expanduser(os.environ.get(
        "VOICE_RECAP_VOICES_DIR", "~/Library/Application Support/voice-recap/voices"))
    voice_dir = os.path.join(voices, args.name)
    clip_dir = os.path.join(voice_dir, "clips")
    os.makedirs(clip_dir, exist_ok=True)
    for f in os.listdir(clip_dir):
        os.unlink(os.path.join(clip_dir, f))

    clips, total = [], 0.0
    for path in args.wavs:
        a, sr = read_mono16(path)
        for seg in split(a, sr):
            if total >= MAX_REF_SEC:
                break
            clip = os.path.join(clip_dir, f"clip{len(clips):03d}.wav")
            with wave.open(clip, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(seg.tobytes())
            clips.append(clip)
            total += len(seg) / sr
    if not clips:
        print("切り出せる発話がなかった", file=sys.stderr)
        return 1

    sys.path.insert(0, IRODORI_DIR)
    import torch
    from irodori_tts.codec import DACVAECodec
    from irodori_tts.inference_runtime import _load_audio

    codec = DACVAECodec.load(
        os.environ.get("VOICE_RECAP_CODEC", "Aratako/Semantic-DACVAE-Japanese-32dim"),
        device=args.device,
    )
    pieces = []
    for clip in clips:
        wav, sr = _load_audio(clip)
        # 推論時の既定（-16 dB に正規化）と揃える
        pieces.append(codec.encode_waveform(wav.unsqueeze(0), sample_rate=sr, normalize_db=-16.0).cpu())
    latent = torch.cat(pieces, dim=1)[0]
    ref = os.path.join(voice_dir, "ref.pt")
    torch.save(latent, ref)
    print(f"{len(clips)} 本（{total:.1f} 秒）から {ref} を作った")
    return 0


if __name__ == "__main__":
    sys.exit(main())
