---
name: voice-recap
description: 1 ターン前の Claude の回答をギャル口調で短く要約し、ローカルの Irodori-TTS（既定。Gemini TTS にも切り替え可）で音声化して、デスクトップの常駐アバター（DesktopAvatar）に口パクと表情つきで喋らせる。「/voice-recap」「今の読み上げて」「さっきの要約を音声で」などで起動する。
allowed-tools: Bash(python3:*), Bash(~/.claude/skills/voice-recap/scripts/speak.py:*)
---

# voice-recap スキル

直前のやり取りを、耳で聞いて分かる長さの要約にして、常駐アバターに喋らせる。
アバター本体は別リポジトリ `~/Desktop/codes/desktop-avatar`（`make install` で `~/Applications/DesktopAvatar.app` に入る）。
音声合成は既定でローカルの [Irodori-TTS](https://github.com/Aratako/Irodori-TTS)（`Aratako/Irodori-TTS-v4.1-Small-MF`）を使い、以前 Gemini TTS で作った WAV を参照音声にして同じ声に寄せる。

## 対象

- 対象は、このコマンドを呼ぶ直前のユーザー発話と、それに対する Claude の回答（1 ターン分）
- 引数があれば、その指示を優先する（例: `/voice-recap 結論だけ`、`/voice-recap 30秒くらいで`）
- 直前のターンが存在しない場合は、読み上げずにその旨を伝えて終わる

## 手順

1. 直前のターンを要約した**読み上げ用台本**を書く（下の規範に従う）
2. 台本を標準入力で渡してスクリプトを実行する

   ```bash
   ~/.claude/skills/voice-recap/scripts/speak.py <<'RECAP'
   （台本）
   RECAP
   ```

   - スクリプトは表情タグを除いた本文を TTS に渡し、WAV を `~/Music/voice-recap` に保存する。Irodori-TTS のときは常駐サーバ（`scripts/irodori_server.py`）に依頼し、居なければ起動する（初回は 10 秒ほど、以降は数秒）。サーバは 30 分依頼がないと自分で終了するそのあと WAV と表情タイムラインをアバターに渡して即終了する（アバターが起動していなければ起動する）
   - アバターが入っていない、または応答しないときは、標準エラーに理由を 1 行出して `afplay` で再生する
   - 成功すると保存先 WAV のパスを 1 行出力する
3. ユーザーへの返答は、台本の本文（表情タグを除いたもの）と「再生したよ」程度の一言だけにする。WAV のパスは聞かれない限り出さない

## 台本の規範

### 中身

- 長さは 150〜300 字（読み上げ 30〜60 秒）が目安。引数で長さの指定があればそれに従う
- 「何を頼まれて、何をして、結論どうなったか、次に何が要るか」の順で話す。全部あるとは限らないので、ないものは飛ばす
- 主張・数値・ファイル名・コマンド名の正確さは元の回答と同じ基準を守る。要約で話を盛らない
- コードブロック、URL、長いパスは読み上げない。「`claude/skills` の下にファイルを 2 つ作った」のように言い換える
- 記号（`→`、`/`、`*`、表、箇条書き記号）は使わない。耳で聞いて通じる文章にする
- 英字のツール名・略語は読みをカタカナで書く（`voice-recap` は「ボイスリキャップ」、`TTS` は「ティーティーエス」、`Gemini` は「ジェミニ」）。Irodori-TTS は英字の読みが崩れやすい。数字はそのまま書いてよい

### 表情タグ

- 段落や文の頭に `[表情: 笑顔]` のようにタグを書くと、そこから次のタグまでアバターがその表情になる。タグの無い冒頭は「通常」
- 使える表情と使い分け（キャラクター設定は desktop-avatar の `character/CHARACTER.md`）

  | 表情 | 使う場面 |
  | --- | --- |
  | 通常 | 説明全般 |
  | 笑顔 | 成功・オチ |
  | ドヤ | 結論・うまくいった時 |
  | 驚き | 予想外の結果 |
  | ジト目 | やらかしにツッコむ |
  | 困り | 失敗・詰まった時 |
  | 考え中 | 問いかけ・前振り |
  | 照れ | 褒められた時 |

- 1 本の台本で表情を変えるのは 2〜4 回までにする。文ごとに変えると顔がせわしなく見える
- タグは読み上げられないので、文の一部として当てにしない

### 口調（ギャル）

- 語尾: 「〜なんだよね」「〜じゃん」「〜なの」「〜わけ」「〜だよ」「〜てね」。**「〜だ」「〜である」「〜のだ」「〜だろうか」は使わない**
- つなぎ: 「ってさ」「でさ」「じゃあさ」「でも逆に」。くだけた言い方（おんなじ／おっきい／ラク）は使ってよい
- スラング（無理ゲー 等）は 1 本に 1〜2 個まで。**技術用語・数字・固有名詞はくだけさせない**
- 一人称は必要なときだけ出してよい。出すなら「あーし」（「私」「あたし」は使わない）。キャラクター名は台本に出さない
- 「？」「！」の直後に空白を入れない

## 失敗時

- `Irodori-TTS の環境が見つからない`: 下の「Irodori-TTS のセットアップ」を案内する
- `参照ボイスがない`（`Irodori-TTS サーバが終了した` の理由として出る）: `build_voice.py` で参照ボイスを作るよう案内する
- `Irodori-TTS エラー` / `サーバが起動しない`: `~/Library/Logs/voice-recap/irodori.log` の末尾を見て伝える。急ぐなら `VOICE_RECAP_ENGINE=gemini` で Gemini に戻せる
- `GEMINI_API_KEY が未設定です`: 環境変数 `GEMINI_API_KEY` の設定をユーザーに案内する
- `Gemini API エラー 4xx/5xx`: エラー本文を要約して伝える。モデル名が原因なら `VOICE_RECAP_MODEL` で差し替えられることを伝える
- 音声が含まれていない: レスポンス冒頭を添えて伝える
- `アバターを使わず afplay で再生します（…）`: 音声は流れているので、失敗扱いにはしない。理由が「DesktopAvatar.app が入っていない」なら、desktop-avatar で `make install` を実行するよう一言添える

## 設定（環境変数）

| 変数 | 既定値 | 用途 |
| --- | --- | --- |
| `VOICE_RECAP_ENGINE` | `irodori` | `irodori`（ローカル）か `gemini` |
| `VOICE_RECAP_IRODORI_DIR` | `~/Desktop/codes/Irodori-TTS` | Irodori-TTS の clone 先 |
| `VOICE_RECAP_IRODORI_MODEL` | `Aratako/Irodori-TTS-v4.1-Small-MF` | Irodori のモデル。読みの精度を優先するなら `Aratako/Irodori-TTS-v4.1-Small`（40 ステップで遅い） |
| `VOICE_RECAP_VOICE_NAME` | `gal` | 参照ボイスの名前（`~/Library/Application Support/voice-recap/voices/<名前>/`） |
| `VOICE_RECAP_CAPTION` | なし | Irodori に渡す声と話し方の指示。付けると短い文で意味のない声が混ざりやすいので、既定では付けない |
| `VOICE_RECAP_SEED` | `0` | Irodori の乱数シード。文ごとの声のブレを抑えるため固定する |
| `VOICE_RECAP_IDLE` | `1800` | Irodori サーバが何秒依頼なしで終了するか |
| `GEMINI_API_KEY` | なし（gemini のとき必須） | Gemini API キー |
| `VOICE_RECAP_MODEL` | `gemini-3.8-flash-tts` | Gemini の TTS モデル |
| `VOICE_RECAP_VOICE` | `voice_q5fi42vgyamm` | 声の ID。既定はカスタムボイス「Japanese Female 1」（2027-09-24 に期限切れ）。プリセットなら `leda` など |
| `VOICE_RECAP_STYLE` | 明るいギャル調の指示 | 読み上げスタイル（`speech_metadata.style`） |
| `VOICE_RECAP_DIR` | `~/Music/voice-recap` | WAV の保存先。スクリプトは消さないので、不要になったら手で消す |
| `VOICE_RECAP_AVATAR` | `1` | `0` にするとアバターを使わず `afplay` で再生する |

Irodori サーバが読むのは起動時の環境変数なので、Irodori 系の変数を変えたら `pkill -f irodori_server.py` でサーバを止めてから呼ぶ。

## Irodori-TTS のセットアップ

1. clone して環境を作る（macOS は `cpu` extra で MPS が使える）

   ```bash
   git clone https://github.com/Aratako/Irodori-TTS.git ~/Desktop/codes/Irodori-TTS
   cd ~/Desktop/codes/Irodori-TTS && uv sync --extra cpu
   ```

2. Gemini TTS で作った WAV から参照ボイスを作る。無音で 3〜10 秒の発話に切り分け、合計 120 秒ぶんまで使う。Irodori の出力（`-irodori.wav`）は混ぜない

   ```bash
   cd ~/Desktop/codes/Irodori-TTS && uv run --no-sync python ~/.claude/skills/voice-recap/scripts/build_voice.py \
     $(ls ~/Music/voice-recap/recap-*.wav | grep -v -- -irodori)
   ```

モデルは初回起動時に Hugging Face から取得する（`~/.cache/huggingface`）。生成音声には Irodori-TTS の既定で SilentCipher の透かしが入る。
