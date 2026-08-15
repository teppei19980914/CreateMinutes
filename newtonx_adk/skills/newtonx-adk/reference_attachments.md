# 添付ファイルの種類別処理ガイド

## 概要

NewtonX ADKでは、画像、ドキュメント、音声の3種類のファイルを添付できます。それぞれ異なる処理方法があり、**画像と音声は同時に指定できません**（相互排他）。

## 添付ファイルの種類

| 種類 | アップロード方法 | 送信時のパラメータ | 同時指定可否 |
|------|-----------------|-------------------|------------|
| **画像** | `upload_image()` | `image_ids=[...]` | ❌ 音声と同時不可 |
| **ドキュメント** | `upload_document()` | `document_ids=[...]` | ✅ 画像と同時可 |
| **音声** | 不要（直接指定） | `audio_file_path="..."` | ❌ 画像と同時不可 |

## 画像の添付

### 手順

1. **画像をアップロード**して `image_id` を取得
2. `send_message()` の `image_ids` パラメータに渡す

```python
# 1. 画像アップロード
image_id = client.upload_image(
    chat_uid=chat_uid,
    file_path="/path/to/image.jpg",
    file_name="image.jpg"  # オプション
)

if not image_id:
    raise Exception("画像アップロードに失敗しました")

# 2. メッセージ送信（image_ids を使用）
response = client.send_message(
    chat_uid=chat_uid,
    message="この画像を分析してください",
    image_ids=[image_id]  # ← List[str] 形式
)
```

### 複数画像の添付

```python
# 複数画像をアップロード
image_paths = ["/path/to/image1.jpg", "/path/to/image2.png"]
image_ids = []

for path in image_paths:
    image_id = client.upload_image(chat_uid, path)
    if image_id:
        image_ids.append(image_id)

# メッセージ送信（複数の image_ids）
response = client.send_message(
    chat_uid=chat_uid,
    message="これらの画像を比較してください",
    image_ids=image_ids  # ← 複数のIDを指定
)
```

### ヘルパーメソッド（存在する場合）

```python
# upload_images() が存在する場合
image_ids = client.upload_images(
    chat_uid,
    ["/path/to/a.png", "/path/to/b.jpg"]
)

# send_message_with_images() が存在する場合
response = client.send_message_with_images(
    chat_uid=chat_uid,
    message="これらの画像から読み取れる内容を教えて",
    image_file_paths=["/path/to/a.png", "/path/to/b.jpg"]
)
```

## ドキュメントの添付

### 手順

1. **ドキュメントをアップロード**して `document_id` を取得
2. `send_message()` の `document_ids` パラメータに渡す

```python
# 1. ドキュメントアップロード
document_id = client.upload_document(
    chat_uid=chat_uid,
    file_path="/path/to/document.pdf",
    file_name="document.pdf"  # オプション
)

if not document_id:
    raise Exception("ドキュメントアップロードに失敗しました")

# 2. メッセージ送信（document_ids を使用）
response = client.send_message(
    chat_uid=chat_uid,
    message="このドキュメントの要点をまとめてください",
    document_ids=[document_id]  # ← List[str] 形式
)
```

### 複数ドキュメントの添付

```python
# 複数ドキュメントをアップロード
document_paths = ["/path/to/doc1.pdf", "/path/to/doc2.docx"]
document_ids = []

for path in document_paths:
    doc_id = client.upload_document(chat_uid, path)
    if doc_id:
        document_ids.append(doc_id)

# メッセージ送信（複数の document_ids）
response = client.send_message(
    chat_uid=chat_uid,
    message="これらのドキュメントを比較してください",
    document_ids=document_ids
)
```

## 音声の添付

### 手順

**前提**: 音声ファイルは **名前に `Gemini` を含むアシスタント** でのみ扱えます（それ以外は音声非対応）。

**音声ファイルはアップロード不要**。`send_message()` の `audio_file_path` パラメータに直接ファイルパスを指定します。

```python
# 音声ファイルを直接指定（upload不要）
response = client.send_message(
    chat_uid=chat_uid,
    message="この音声を要約してください",
    audio_file_path="/path/to/audio.wav"  # ← 直接ファイルパスを指定
)
```

### 対応ファイル形式と制限

- **対応形式**: `.wav`, `.mp3`, `.aiff`, `.aac`, `.ogg`, `.flac`
- **最大ファイルサイズ**: 15MB
- **送信形式**: `multipart/form-data`（自動的に変換される）

### エラーハンドリング

```python
from newtonx_adk import FileUploadError, APIError

try:
    response = client.send_message(
        chat_uid=chat_uid,
        message="この音声を文字起こししてください",
        audio_file_path="/path/to/audio.mp3"
    )
    if response:
        print(f"応答: {response}")
except FileUploadError as e:
    print(f"ファイルアップロードエラー: {e}")
except APIError as e:
    print(f"APIエラー: {e}")
```

## よくある間違い

### ❌ 間違い1: `image_ids` と `audio_file_path` を同時指定

```python
# 間違い: 同時指定は不可
response = client.send_message(
    chat_uid=chat_uid,
    message="画像と音声を分析してください",
    image_ids=[image_id],
    audio_file_path="/path/to/audio.wav"  # ← エラーになる
)
```

**正しい方法**: どちらか一方のみ指定する

```python
# 正しい: 画像のみ
response = client.send_message(
    chat_uid=chat_uid,
    message="この画像を分析してください",
    image_ids=[image_id]
)

# または音声のみ
response = client.send_message(
    chat_uid=chat_uid,
    message="この音声を要約してください",
    audio_file_path="/path/to/audio.wav"
)
```

### ❌ 間違い2: 音声ファイルを `upload_image()` でアップロードしようとする

```python
# 間違い: 音声ファイルはアップロード不要
audio_id = client.upload_image(chat_uid, "/path/to/audio.wav")  # ← 間違い
response = client.send_message(..., image_ids=[audio_id])
```

**正しい方法**: `audio_file_path` を直接指定

```python
# 正しい: 音声ファイルは直接指定
response = client.send_message(
    chat_uid=chat_uid,
    message="この音声を要約してください",
    audio_file_path="/path/to/audio.wav"  # ← 直接指定
)
```

### ❌ 間違い3: `document_ids` にファイルパスを渡す

```python
# 間違い: document_ids にはIDを渡す（ファイルパスではない）
response = client.send_message(
    chat_uid=chat_uid,
    message="ドキュメントを分析してください",
    document_ids=["/path/to/document.pdf"]  # ← 間違い（IDが必要）
)
```

**正しい方法**: まずアップロードしてIDを取得

```python
# 正しい: まずアップロードしてIDを取得
document_id = client.upload_document(chat_uid, "/path/to/document.pdf")
response = client.send_message(
    chat_uid=chat_uid,
    message="ドキュメントを分析してください",
    document_ids=[document_id]  # ← IDを渡す
)
```

## 実装例

### 画像とドキュメントの同時添付

```python
# 画像とドキュメントは同時に指定可能
image_id = client.upload_image(chat_uid, "/path/to/image.jpg")
document_id = client.upload_document(chat_uid, "/path/to/document.pdf")

response = client.send_message(
    chat_uid=chat_uid,
    message="画像とドキュメントを参照して分析してください",
    image_ids=[image_id],
    document_ids=[document_id]  # ← 同時指定OK
)
```

### エラーハンドリング付きの完全な例

```python
from newtonx_adk import NewtonXClient, ConfigManager, FileUploadError, APIError

config = ConfigManager()
client = NewtonXClient(config)
client.authenticate()

assistants = client.get_assistants()
chat_uid = client.create_chat(
    assistant_uid=assistants[0]['uid'],
    title="添付ファイルテスト"
)

# 画像添付
try:
    image_id = client.upload_image(chat_uid, "/path/to/image.jpg")
    if image_id:
        response = client.send_message(
            chat_uid=chat_uid,
            message="この画像を分析してください",
            image_ids=[image_id]
        )
        print(f"応答: {response}")
except FileUploadError as e:
    print(f"画像アップロードエラー: {e}")
except APIError as e:
    print(f"APIエラー: {e}")

# 音声添付
try:
    response = client.send_message(
        chat_uid=chat_uid,
        message="この音声を要約してください",
        audio_file_path="/path/to/audio.wav"
    )
    if response:
        print(f"応答: {response}")
except FileUploadError as e:
    print(f"音声ファイルエラー: {e}")
except APIError as e:
    print(f"APIエラー: {e}")
```

## 関連API

- `upload_image(chat_uid: str, file_path: str, file_name: Optional[str] = None) -> Optional[str]`: 画像アップロード
- `upload_document(chat_uid: str, file_path: str, file_name: Optional[str] = None) -> Optional[str]`: ドキュメントアップロード
- `send_message(chat_uid: str, message: str, image_ids: Optional[List[str]] = None, document_ids: Optional[List[str]] = None, audio_file_path: Optional[str] = None) -> Optional[str]`: メッセージ送信

## 注意事項

- **画像と音声は同時指定不可**（相互排他）
- **画像とドキュメントは同時指定可能**
- **音声ファイルはアップロード不要**（`audio_file_path` に直接指定）
- 音声ファイルを指定すると、リクエストは自動的に `multipart/form-data` 形式になります
- ファイルサイズ制限: 音声は15MBまで
