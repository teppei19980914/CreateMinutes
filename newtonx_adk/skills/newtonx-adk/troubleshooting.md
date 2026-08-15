# トラブルシューティングガイド

## 概要

NewtonX ADKを使用する際によく発生する問題と、その解決方法をまとめています。

## 認証関連

### 401 Unauthorized / 403 Forbidden

**症状**: 認証エラーが発生する

**原因**:
- PAT（Personal Access Token）が設定されていない
- PATが無効または期限切れ
- Host設定が間違っている

**解決方法**:

1. **設定を確認**
```bash
PYTHONPATH=./src python tools/check_config.py
```

2. **設定を再実行**
```bash
PYTHONPATH=./src python tools/setup_config.py
```

3. **コードで確認**
```python
from newtonx_adk import ConfigManager, AuthManager

config = ConfigManager()
auth = AuthManager(config)
headers = auth.get_headers()

# Authorizationヘッダーが存在するか確認
if not headers.get("Authorization", "").startswith("Bearer "):
    print("認証情報が設定されていません")
    # setup_config.py を実行してください
```

### PATをハードコードしてしまう

**症状**: コードにPATを直接書いてしまう

**原因**: セキュリティ上の問題

**解決方法**:
- ❌ **絶対にしない**: `personal_access_token="your_token_here"` をコードに書く
- ✅ **正しい方法**: `tools/setup_config.py` または `newtonx-config` を使用

```python
# ❌ 間違い
config_manager.update_config(
    host="seraku.newton-x.net",
    personal_access_token="your_token_here"  # ← 絶対にしない
)

# ✅ 正しい
# setup_config.py で設定済みのConfigManagerを使用
config_manager = ConfigManager()  # 自動的に設定を読み込む
```

## ファイルアップロード関連

### ファイルアップロードに失敗する

**症状**: `FileUploadError` が発生する

**原因**:
- ファイルが存在しない
- ファイルサイズが制限を超えている（音声: 15MB）
- ファイル形式が対応していない

**解決方法**:

```python
import os
from newtonx_adk import FileUploadError

file_path = "/path/to/file.jpg"

# ファイルの存在確認
if not os.path.exists(file_path):
    raise Exception(f"ファイルが存在しません: {file_path}")

# ファイルサイズ確認（音声の場合）
if file_path.endswith(('.wav', '.mp3', '.aiff', '.aac', '.ogg', '.flac')):
    file_size = os.path.getsize(file_path)
    max_size = 15 * 1024 * 1024  # 15MB
    if file_size > max_size:
        raise Exception(f"ファイルサイズが15MBを超えています: {file_size / 1024 / 1024:.2f}MB")

try:
    image_id = client.upload_image(chat_uid, file_path)
except FileUploadError as e:
    print(f"アップロードエラー: {e}")
    # エラーメッセージを確認して対処
```

### 音声を送ったが扱えない（Gemini以外）

**症状**:
- 音声を送っても期待どおりに処理されない
- もしくはエラー/無応答になる

**原因**:
- **名前に `Gemini` を含むアシスタント以外**は音声ファイル非対応

**解決方法**:
1. `get_assistants()` で **名前に `Gemini` を含むアシスタント**を選ぶ
2. そのアシスタントで**新規チャットを作り直し**、`audio_file_path` を送る

### image_ids と audio_file_path を同時指定してしまう

**症状**: エラーが発生する、または意図した動作にならない

**原因**: 相互排他パラメータを同時に指定している

**解決方法**:

```python
# ❌ 間違い
response = client.send_message(
    chat_uid=chat_uid,
    message="画像と音声を分析してください",
    image_ids=[image_id],
    audio_file_path="/path/to/audio.wav"  # ← 同時指定不可
)

# ✅ 正しい: どちらか一方のみ
# 画像のみ
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

## チャット・メッセージ関連

### フォルダIDの混同

**症状**: フォルダ内にチャットが作成されない

**原因**: `get_folders()` の戻り値で `uid` や `uuid` を使おうとしている

**解決方法**:

```python
# ❌ 間違い
folders = client.get_folders()
folder = folders[0]
folder_uid = folder['uid']  # ← このフィールドは存在しない

# ✅ 正しい
folders = client.get_folders()
folder = folders[0]
folder_id = folder['id']  # ← 'id' を使用

chat_uid = client.create_chat(
    assistant_uid=assistant_uid,
    title="チャット",
    folder_uid=folder_id  # ← folder_uid パラメータ名だが、値は folder['id']
)
```

### parent_order の混同

**症状**: スレッドの文脈が維持されない

**原因**: `id` や `uuid` を `parent_order` に指定している

**解決方法**:

```python
# ❌ 間違い
chat_detail = client.get_chat(chat_uid)
message = chat_detail['messages'][0]
parent_order = message['id']  # ← 間違い

# ✅ 正しい
chat_detail = client.get_chat(chat_uid)
message = chat_detail['messages'][0]
parent_order = message['chat_order']  # ← 'chat_order' を使用

response = client.send_message(
    chat_uid=chat_uid,
    message="続きを教えて",
    parent_order=parent_order
)
```

### web_search / knowledge_search の指定ミス（相互排他）

**症状**:
- 期待した検索が走らない（Web検索/ナレッジ検索の挙動が不安定）
- 場合によってはエラー/無応答に繋がる

**原因**:
- `web_search` と `knowledge_search` を **両方ON** にしている

**解決方法**（どちらか片方だけON）:

```python
# ✅ Web検索
response = client.send_message(
    chat_uid=chat_uid,
    message="最新のAI技術について教えてください",
    web_search=True,
    knowledge_search=False,
)

# ✅ ナレッジ検索（RAG）
response = client.send_message(
    chat_uid=chat_uid,
    message="社内資料の範囲で要点をまとめて",
    web_search=False,
    knowledge_search=True,
)
```

### システムアシスタントで knowledge_search をONにしてしまう

**症状**:
- ナレッジ検索が有効にならない/エラーになる

**原因**:
- **システム組み込みアシスタントはナレッジ検索（RAG）を使えない**

**解決方法**:
- ナレッジを使いたい場合は、**ナレッジ付きのアシスタント**（ユーザー/組織で構築したアシスタント）を選ぶ

## 回答の信頼性関連

### 回答が途中で途切れる（出力トークン枯渇）

**症状**: 回答が途中で終了する

**原因**: 出力トークンが尽きた

**解決方法**: 終端マーカー方式を使用

詳細は [reference_response_reliability.md](reference_response_reliability.md) を参照。

```python
END_MARKER = "__END_OF_RESPONSE__"

# 最初の指示で終端マーカーを含めるよう指示
response = client.send_message(
    chat_uid=chat_uid,
    message=f"長文のレポートを作成してください。最後に {END_MARKER} を付けてください。"
)

full_response = response or ""

# 終端マーカーが出るまで継続取得
for i in range(10):  # 最大10回
    if END_MARKER in full_response:
        break
    
    chat_detail = client.get_chat(chat_uid)
    messages = chat_detail.get('messages', [])
    if messages:
        last_msg = messages[-1]
        if last_msg['role'] == 'assistant':
            parent_order = last_msg['chat_order']
            continuation = client.send_message(
                chat_uid=chat_uid,
                message=f"続きを出力してください。最後に {END_MARKER} を付けてください。",
                parent_order=parent_order
            )
            if continuation:
                full_response += continuation

# 終端マーカーを除去
full_response = full_response.replace(END_MARKER, "").strip()
```

### 応答が返ってこない（無応答）

**症状**: `send_message()` が `None` を返す、またはタイムアウト/例外が発生する

**原因**: LLM側のコンディション不良など

**解決方法**: 新規チャットを作成してやり直す

詳細は [reference_response_reliability.md](reference_response_reliability.md) を参照。

```python
import time
from newtonx_adk import APIError, ChatError

def send_with_recovery(client, assistant_uid, message, max_retries=2):
    """無応答時に新規チャットでやり直す"""
    chat_uid = None
    
    for attempt in range(max_retries):
        try:
            # 新規チャット作成
            if not chat_uid:
                chat_uid = client.create_chat(
                    assistant_uid=assistant_uid,
                    title=f"リカバリチャット {attempt + 1}"
                )
            
            # メッセージ送信
            response = client.send_message(chat_uid, message)
            
            if response:
                return response, chat_uid
            
            # 応答がNoneの場合は新規チャットで再試行
            chat_uid = None
            
        except (APIError, ChatError, Exception) as e:
            print(f"エラー発生（試行 {attempt + 1}/{max_retries}）: {e}")
            chat_uid = None
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

## 設定関連

### Host設定が間違っている

**症状**: 404エラーが発生する

**原因**: `host` に `/api` が含まれている、または含まれていない

**解決方法**:

```python
# ❌ 間違い
config_manager.update_config(
    host="seraku.newton-x.net/api"  # ← /api を含めない
)

# ✅ 正しい
config_manager.update_config(
    host="seraku.newton-x.net"  # ← /api は含めない（自動的に追加される）
)
```

### 設定ファイルが見つからない

**症状**: `ConfigManager()` で設定が読み込まれない

**原因**: 設定ファイルが存在しない、またはパスが間違っている

**解決方法**:

```bash
# 設定ツールを実行
PYTHONPATH=./src python tools/setup_config.py
```

## その他のエラー

### APIError: 500 Internal Server Error

**症状**: サーバー側のエラー

**原因**: NewtonX側の一時的な問題

**解決方法**:
- しばらく待ってから再試行
- リトライロジックを実装

```python
import time
from newtonx_adk import APIError

def send_with_retry(client, chat_uid, message, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.send_message(chat_uid, message)
        except APIError as e:
            if e.status_code == 500 and attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数バックオフ
                print(f"サーバーエラー、{wait_time}秒後にリトライ...")
                time.sleep(wait_time)
            else:
                raise
```

### タイムアウトエラー

**症状**: リクエストがタイムアウトする

**原因**: ネットワークの問題、または処理に時間がかかりすぎている

**解決方法**:
- タイムアウト時間を延長（設定可能な場合）
- リトライロジックを実装

## チェックリスト

問題が発生したら、以下を確認:

- [ ] 認証設定が正しいか？（`tools/check_config.py` で確認）
- [ ] PATをハードコードしていないか？
- [ ] フォルダIDで `folder['id']` を使っているか？
- [ ] `parent_order` で `message['chat_order']` を使っているか？
- [ ] `image_ids` と `audio_file_path` を同時指定していないか？
- [ ] ファイルが存在し、サイズ制限内か？
- [ ] 長文出力で終端マーカーを要求しているか？
- [ ] 無応答時に新規チャットでやり直しているか？

## 関連リソース

- [APIリファレンス](../../docs/adk/API_REFERENCE.md)
- [使用ガイド](../../docs/adk/USAGE_GUIDE.md)
- [回答の信頼性対策](reference_response_reliability.md)
