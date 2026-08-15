---
name: newtonx-adk
description: NewtonX ADKを使用してチャット作成、メッセージ送信、ファイル添付、parent_order管理、フォルダ操作を行う際のベストプラクティスとよくある間違いを回避する手順。フォルダ内チャット作成、parent_orderの正しい扱い、添付ファイルの種類別処理、認証設定、回答途切れ対策、無応答時のリカバリを含む。NewtonX ADK v0.10.5対応。
---

# NewtonX ADK 開発ガイド

NewtonX ADK（v0.10.5）を使用する際の**よくある間違いを回避**し、**正しい手順で実装**するためのCursor Skillです。

## Quick Start

```python
from newtonx_adk import NewtonXClient, ConfigManager

# 設定とクライアント初期化
config = ConfigManager()
client = NewtonXClient(config)

# 認証（PATが設定済みなら自動）
if not client.authenticate():
    raise Exception("認証に失敗しました")

# アシスタント取得
assistants = client.get_assistants()
assistant_uid = assistants[0]['uid']

# チャット作成
chat_uid = client.create_chat(
    assistant_uid=assistant_uid,
    title="テストチャット"
)

# メッセージ送信
response = client.send_message(chat_uid, "こんにちは！")
print(response)
```

## アシスタント選択と機能制約（重要）

NewtonXでは、LLMモデルは「アシスタント」という概念で選択します。アシスタントには大きく以下があります。

- **システム組み込みアシスタント**: NewtonX側が提供する標準アシスタント（例: 高速/高性能など）
- **ユーザー/組織が構築したアシスタント**: 独自RAGを含む（NewtonX上では「ナレッジ」と表現）

### 音声ファイル対応（Gemini）

- **名前に `Gemini` が入っているアシスタントのみ**、`audio_file_path`（音声添付）を扱えます。
- それ以外のアシスタントに音声を渡したい場合は、**Geminiアシスタントに切り替える**（新規チャット作成）を前提にしてください。

### Web検索とナレッジ検索（相互排他）

`send_message()` では、以下2つの検索を切り替えできます。

- `web_search`: Web検索のON/OFF
- `knowledge_search`: アシスタントRAG（ナレッジ）のON/OFF

**重要**:
- `web_search` と `knowledge_search` は **どちらか片方だけ** をONにします（同時ONはしない）
- **システム組み込みアシスタントは `knowledge_search=True` にできません**

## 判断フロー（迷いどころの分岐）

### 1. チャットをフォルダ配下に作成したい？

**判断**: フォルダ内に整理したい → `folder_uid` を取得 → `create_chat(folder_uid=...)`

**手順**:
1. `get_folders()` でフォルダ一覧を取得
2. 名前で検索（存在しなければ `create_folder()` で作成）
3. **重要**: `folder['id']` を使用（`uid`/`uuid` ではない）
4. `create_chat(..., folder_uid=folder['id'])`

詳細は [reference_chat.md](reference_chat.md) を参照。

### 2. 前のメッセージの「続き」として送信したい？

**判断**: スレッドの文脈を維持したい → `parent_order` を指定

**手順**:
1. `get_chat(chat_uid)` でチャット詳細を取得
2. `messages[]` から返信したいメッセージを特定
3. **重要**: `message['chat_order']` を使用（`id`/`uuid` ではない）
4. `send_message(..., parent_order=message['chat_order'])`

詳細は [reference_parent_order.md](reference_parent_order.md) を参照。

### 3. ファイルを添付したい？

**判断**: 画像？ドキュメント？音声？ → 種類に応じた処理

**手順**:
- **画像**: `upload_image()` → `image_ids=[...]` で送信
- **ドキュメント**: `upload_document()` → `document_ids=[...]` で送信
- **音声**: `audio_file_path="/path/to/file.wav"` を直接指定（multipart送信）
  - **前提**: 音声対応の **Geminiアシスタント** を使う（名前に `Gemini` を含む）

**重要**: `image_ids` と `audio_file_path` は**同時指定不可**（相互排他）

詳細は [reference_attachments.md](reference_attachments.md) を参照。

### 3.5 Web検索/ナレッジ検索を切り替えたい？

**判断**: Web検索したい？ナレッジ検索したい？ → どちらか片方だけON

**手順**:
- **Web検索**: `web_search=True, knowledge_search=False`
- **ナレッジ検索**: `web_search=False, knowledge_search=True`
  - **前提**: ナレッジを持つアシスタント（システムアシスタントは不可）

### 4. 回答が途中で途切れた？

**判断**: 出力トークン枯渇などで途中終了 → **終端マーカー方式**で継続取得

**手順**:
1. 長文出力が必要な指示では、**必ず終端マーカー（例: `__END_OF_RESPONSE__`）を含める**よう指示
2. 応答に終端マーカーが含まれていない場合、`parent_order` を指定して「続きを出力してください。最後に `__END_OF_RESPONSE__` を付けてください」と送信
3. 終端マーカーが出るまで繰り返し

詳細は [reference_response_reliability.md](reference_response_reliability.md) を参照。

### 5. 応答が返ってこない？

**判断**: LLM側のコンディション不良など → **そのチャットは使い捨て**、新規チャットでやり直し

**手順**:
1. タイムアウトや例外が発生したら、**原因切り分けより先に復旧を優先**
2. 同じ `assistant_uid` で**新規チャットを作成**
3. 同じ指示/添付を再投入
4. 必要に応じて元のチャットは削除

詳細は [reference_response_reliability.md](reference_response_reliability.md) を参照。

## よくある間違いチェックリスト

実装前に以下を確認:

- [ ] **フォルダIDの混同**: `get_folders()` の戻り値で `folder['id']` を使っているか？（`uid`/`uuid` ではない）
- [ ] **parent_orderの混同**: `get_chat()` から取得した `message['chat_order']` を使っているか？（`id`/`uuid` ではない）
- [ ] **添付の相互排他**: `image_ids` と `audio_file_path` を同時指定していないか？
- [ ] **音声対応アシスタント**: 音声は **Geminiアシスタント**（名前に `Gemini`）で送っているか？
- [ ] **検索の相互排他**: `web_search` と `knowledge_search` を同時にONにしていないか？（片方だけON）
- [ ] **システムアシスタントの制約**: システムアシスタントで `knowledge_search=True` にしていないか？
- [ ] **認証設定**: PATをハードコードしていないか？`tools/setup_config.py` または `newtonx-config` を使用しているか？
- [ ] **長文出力**: 終端マーカーを要求する指示を含めているか？
- [ ] **無応答時の対応**: 同一チャットへ延々と再送していないか？新規チャット作成に切り替えているか？

## 出力テンプレート

Cursorがコードを生成する際は、以下のパターンに従う:

### フォルダ内チャット作成

```python
# フォルダ取得または作成
folders = client.get_folders()
target_folder = next((f for f in folders if f['name'] == "フォルダ名"), None)
if not target_folder:
    folder_id = client.create_folder("フォルダ名")
else:
    folder_id = target_folder['id']  # ← 'id' を使用

# チャット作成
chat_uid = client.create_chat(
    assistant_uid=assistant_uid,
    title="チャットタイトル",
    folder_uid=folder_id  # ← folder_uid パラメータに渡す
)
```

### parent_order指定

```python
# チャット詳細取得
chat_detail = client.get_chat(chat_uid)
if not chat_detail:
    raise Exception("チャットが見つかりません")

# 最後のアシスタント応答を取得
last_assistant_msg = None
for msg in reversed(chat_detail.get('messages', [])):
    if msg['role'] == 'assistant':
        last_assistant_msg = msg
        break

if last_assistant_msg:
    parent_order = last_assistant_msg['chat_order']  # ← 'chat_order' を使用
    response = client.send_message(
        chat_uid=chat_uid,
        message="続きを教えて",
        parent_order=parent_order  # ← parent_order パラメータに渡す
    )
```

### 添付ファイル（画像）

```python
# 画像アップロード
image_id = client.upload_image(chat_uid, "/path/to/image.jpg")
if not image_id:
    raise Exception("画像アップロードに失敗しました")

# メッセージ送信（image_ids を使用）
response = client.send_message(
    chat_uid=chat_uid,
    message="この画像を分析してください",
    image_ids=[image_id]  # ← List[str] 形式
)
```

### 添付ファイル（音声）

```python
# 音声ファイルを直接指定（upload不要）
response = client.send_message(
    chat_uid=chat_uid,
    message="この音声を要約してください",
    audio_file_path="/path/to/audio.wav"  # ← image_ids と同時指定不可
)
```

### 終端マーカー方式（長文出力）

```python
# 最初の指示（終端マーカーを含めるよう指示）
response = client.send_message(
    chat_uid=chat_uid,
    message="長文のレポートを作成してください。最後に __END_OF_RESPONSE__ を付けてください。"
)

full_response = response or ""

# 終端マーカーが出るまで継続
END_MARKER = "__END_OF_RESPONSE__"
max_iterations = 10  # 無限ループ防止

for i in range(max_iterations):
    if END_MARKER in full_response:
        break
    
    # 最後のメッセージのchat_orderを取得
    chat_detail = client.get_chat(chat_uid)
    last_msg = chat_detail.get('messages', [])[-1] if chat_detail else None
    if last_msg and last_msg['role'] == 'assistant':
        parent_order = last_msg['chat_order']
        continuation = client.send_message(
            chat_uid=chat_uid,
            message=f"続きを出力してください。最後に {END_MARKER} を付けてください。",
            parent_order=parent_order
        )
        if continuation:
            full_response += continuation
    else:
        break

# 終端マーカーを除去
full_response = full_response.replace(END_MARKER, "").strip()
```

### 無応答時のリカバリ

```python
import time
from newtonx_adk import APIError, ChatError

def send_with_recovery(client, assistant_uid, message, max_retries=2, timeout=30):
    """無応答時に新規チャットでやり直す"""
    chat_uid = None
    
    for attempt in range(max_retries):
        try:
            # 新規チャット作成（または再利用）
            if not chat_uid:
                chat_uid = client.create_chat(
                    assistant_uid=assistant_uid,
                    title=f"リカバリチャット {attempt + 1}"
                )
            
            # メッセージ送信（タイムアウト設定）
            response = client.send_message(chat_uid, message)
            if response:
                return response, chat_uid
            
            # 応答がNoneの場合は新規チャットで再試行
            chat_uid = None
            
        except (APIError, ChatError, Exception) as e:
            print(f"エラー発生（試行 {attempt + 1}/{max_retries}）: {e}")
            chat_uid = None  # 次の試行で新規作成
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise
    
    raise Exception("最大リトライ回数に達しました")

# 使用例
try:
    response, chat_uid = send_with_recovery(client, assistant_uid, "質問内容")
    print(response)
except Exception as e:
    print(f"最終的に失敗: {e}")
```

## 追加リソース

- **フォルダ操作の詳細**: [reference_chat.md](reference_chat.md)
- **parent_orderの詳細**: [reference_parent_order.md](reference_parent_order.md)
- **添付ファイルの詳細**: [reference_attachments.md](reference_attachments.md)
- **回答の信頼性対策**: [reference_response_reliability.md](reference_response_reliability.md)
- **トラブルシューティング**: [troubleshooting.md](troubleshooting.md)
- **実装例**: [examples.md](examples.md)

## バージョン情報

- **NewtonX ADK**: v0.10.5（このリポジトリの `pyproject.toml` に基づく）
- **APIリファレンス**: `docs/adk/API_REFERENCE.md`
- **使用ガイド**: `docs/adk/USAGE_GUIDE.md`
