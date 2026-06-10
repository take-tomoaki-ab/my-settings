#!/usr/bin/env python3
"""UserPromptSubmit hook: ローマ字プロンプトをひらがなに変換する。

プロンプトの先頭（またはスラッシュコマンドを除いた先頭）が `=` のとき、
それ以降をローマ字とみなしてひらがなへ変換し、additionalContext として
Claude に渡す。ローマ字として解釈できないトークンは原文のまま残す。
解釈できないトークンは QWERTY 隣接キーの打ち間違いを仮定して 1 文字
置換を試し、解釈可能になる候補が一意ならば自動採用する。
"""
import json
import re
import sys

TABLE = {
    "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
    "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご",
    "sa": "さ", "si": "し", "shi": "し", "su": "す", "se": "せ", "so": "そ",
    "za": "ざ", "zi": "じ", "ji": "じ", "zu": "ず", "ze": "ぜ", "zo": "ぞ",
    "ta": "た", "ti": "ち", "chi": "ち", "tu": "つ", "tsu": "つ",
    "te": "て", "to": "と",
    "da": "だ", "di": "ぢ", "du": "づ", "de": "で", "do": "ど",
    "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "ha": "は", "hi": "ひ", "hu": "ふ", "fu": "ふ", "he": "へ", "ho": "ほ",
    "ba": "ば", "bi": "び", "bu": "ぶ", "be": "べ", "bo": "ぼ",
    "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ",
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も",
    "ya": "や", "yu": "ゆ", "yo": "よ",
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "wa": "わ", "wo": "を", "wi": "うぃ", "we": "うぇ",
    "vu": "ゔ", "va": "ゔぁ", "vi": "ゔぃ", "ve": "ゔぇ", "vo": "ゔぉ",
    "fa": "ふぁ", "fi": "ふぃ", "fe": "ふぇ", "fo": "ふぉ",
    "kya": "きゃ", "kyu": "きゅ", "kyo": "きょ",
    "gya": "ぎゃ", "gyu": "ぎゅ", "gyo": "ぎょ",
    "sha": "しゃ", "shu": "しゅ", "sho": "しょ",
    "sya": "しゃ", "syu": "しゅ", "syo": "しょ",
    "ja": "じゃ", "ju": "じゅ", "jo": "じょ",
    "jya": "じゃ", "jyu": "じゅ", "jyo": "じょ",
    "zya": "じゃ", "zyu": "じゅ", "zyo": "じょ",
    "cha": "ちゃ", "chu": "ちゅ", "cho": "ちょ",
    "tya": "ちゃ", "tyu": "ちゅ", "tyo": "ちょ",
    "dya": "ぢゃ", "dyu": "ぢゅ", "dyo": "ぢょ",
    "nya": "にゃ", "nyu": "にゅ", "nyo": "にょ",
    "hya": "ひゃ", "hyu": "ひゅ", "hyo": "ひょ",
    "bya": "びゃ", "byu": "びゅ", "byo": "びょ",
    "pya": "ぴゃ", "pyu": "ぴゅ", "pyo": "ぴょ",
    "mya": "みゃ", "myu": "みゅ", "myo": "みょ",
    "rya": "りゃ", "ryu": "りゅ", "ryo": "りょ",
    "she": "しぇ", "che": "ちぇ", "je": "じぇ",
    "thi": "てぃ", "dhi": "でぃ",
    "xa": "ぁ", "xi": "ぃ", "xu": "ぅ", "xe": "ぇ", "xo": "ぉ",
    "la": "ぁ", "li": "ぃ", "lu": "ぅ", "le": "ぇ", "lo": "ぉ",
    "xya": "ゃ", "xyu": "ゅ", "xyo": "ょ",
    "lya": "ゃ", "lyu": "ゅ", "lyo": "ょ",
    "xtu": "っ", "ltu": "っ", "xtsu": "っ", "ltsu": "っ",
}

VOWELS = "aiueo"

PUNCT_MAP = {".": "。", ",": "、", "?": "？", "!": "！"}


def to_hiragana(s):
    """ローマ字文字列をひらがなへ変換。解釈できなければ None。"""
    out = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        # 促音: 同じ子音の連続（n は除く）
        if (
            ch not in VOWELS
            and ch != "n"
            and i + 1 < n
            and s[i + 1] == ch
        ):
            out.append("っ")
            i += 1
            continue
        if ch == "n":
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt == "":
                out.append("ん")
                i += 1
                continue
            if nxt == "'":
                out.append("ん")
                i += 2
                continue
            # IME 式の "nn"（直後が音節を作らない場合）
            if nxt == "n" and (i + 2 >= n or s[i + 2] not in VOWELS + "y"):
                out.append("ん")
                i += 2
                continue
            # 子音の前の n は ん
            if nxt not in VOWELS + "y":
                out.append("ん")
                i += 1
                continue
        for length in (4, 3, 2, 1):
            if i + length <= n and s[i : i + length] in TABLE:
                out.append(TABLE[s[i : i + length]])
                i += length
                break
        else:
            return None
    return "".join(out)


def build_adjacency():
    rows = [("qwertyuiop", 0.0), ("asdfghjkl", 0.25), ("zxcvbnm", 0.75)]
    pos = {}
    for r, (keys, offset) in enumerate(rows):
        for c, key in enumerate(keys):
            pos[key] = (r, c + offset)
    adj = {}
    for k1, (r1, x1) in pos.items():
        adj[k1] = [
            k2
            for k2, (r2, x2) in pos.items()
            if k1 != k2 and abs(r1 - r2) <= 1 and abs(x1 - x2) <= 1.0
        ]
    return adj

ADJACENT = build_adjacency()


def correct_typo(token):
    """QWERTY 隣接キーへの 1 文字置換で変換可能になる候補を探す。"""
    candidates = {}  # 変換結果 -> 置換後トークン
    for i, ch in enumerate(token):
        for alt in ADJACENT.get(ch, []):
            fixed = token[:i] + alt + token[i + 1 :]
            converted = to_hiragana(fixed)
            if converted is not None:
                candidates[converted] = fixed
    return candidates


def convert_token(token, notes):
    # 末尾の句読点を分離して変換
    trailing = ""
    core = token
    while core and core[-1] in PUNCT_MAP:
        trailing = PUNCT_MAP[core[-1]] + trailing
        core = core[:-1]
    if not core or not re.fullmatch(r"[a-z']+", core):
        return token  # 英単語・ファイル名・記号入りは原文のまま
    converted = to_hiragana(core)
    if converted is not None:
        return converted + trailing
    candidates = correct_typo(core)
    if len(candidates) == 1:
        hira, fixed = next(iter(candidates.items()))
        notes.append(f"「{core}」は誤タイプとみなし「{fixed}」({hira}) に訂正")
        return hira + trailing
    if len(candidates) > 1:
        cand_str = " / ".join(candidates.keys())
        notes.append(f"「{core}」は変換できず。誤タイプ訂正の候補: {cand_str}")
    return token


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    prompt = data.get("prompt", "")
    m = re.match(r"^\s*(/\S+\s+)?=", prompt)
    if not m:
        return
    head = prompt[: m.end() - 1]  # スラッシュコマンド部分（あれば）
    body = prompt[m.end():]
    notes = []
    parts = re.split(r"(\s+)", body)
    converted = "".join(
        p if p.isspace() or p == "" else convert_token(p, notes) for p in parts
    )
    result = (head + converted).strip()
    context = (
        "ユーザーのプロンプトは先頭が `=` のローマ字入力です。"
        "以下がひらがなに変換した本来の指示です。こちらを指示として扱ってください:\n\n"
        f"{result}"
    )
    if notes:
        context += "\n\n変換時の注記:\n" + "\n".join(f"- {n}" for n in notes)
        context += (
            "\n訂正候補が複数ある語は、文脈から最も自然な解釈を選んでください。"
        )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": context,
                }
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
