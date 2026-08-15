# 回答の信頼性対策（途切れ・無応答への対応）

## 概要

NewtonX ADKを使用する際、以下の問題が発生する可能性があります：

1. **出力トークン枯渇**: 回答が途中で途切れる
2. **LLM側のコンディション不良**: 応答が返ってこない

これらの問題に対するベストプラクティスを説明します。

## 1. 回答が途中で途切れる対策（終端マーカー方式）

### 問題

出力トークンが尽きると、回答が途中で終了してしまいます。ユーザーは回答が完全かどうか判断できません。

### 解決策: 終端マーカー方式

**終端マーカー**（例: `__END_OF_RESPONSE__`）を定義し、それが含まれるまで「続き」を要求します。

### 実装手順

#### Step 1: 最初の指示で終端マーカーを含めるよう指示

```python
END_MARKER = "__END_OF_RESPONSE__"

# 長文出力が必要な指示では、必ず終端マーカーを含めるよう指示
response = client.send_message(
    chat_uid=chat_uid,
    message=f"長文のレポートを作成してください。最後に {END_MARKER} を付けてください。"
)
```

#### Step 2: 終端マーカーが出るまで継続取得

```python
full_response = response or ""
max_iterations = 10  # 無限ループ防止

for i in range(max_iterations):
    # 終端マーカーが含まれているか確認
    if END_MARKER in full_response:
        break
    
    # チャット詳細を取得して最後のメッセージのchat_orderを取得
    chat_detail = client.get_chat(chat_uid)
    if not chat_detail:
        break
    
    messages = chat_detail.get('messages', [])
    if not messages:
        break
    
    # 最後のアシスタントメッセージを取得
    last_msg = messages[-1]
    if last_msg['role'] != 'assistant':
        break
    
    parent_order = last_msg['chat_order']
    
    # 続きを要求
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
print(full_response)
```

### 完全な実装例

```python
def get_complete_response(client, chat_uid, initial_message, max_iterations=10):
    """終端マーカー方式で完全な回答を取得"""
    END_MARKER = "__END_OF_RESPONSE__"
    
    # 最初のメッセージ送信
    response = client.send_message(
        chat_uid=chat_uid,
        message=f"{initial_message}\n\n最後に {END_MARKER} を付けてください。"
    )
    
    full_response = response or ""
    
    # 終端マーカーが出るまで継続取得
    for i in range(max_iterations):
        if END_MARKER in full_response:
            break
        
        # チャット詳細を取得
        chat_detail = client.get_chat(chat_uid)
        if not chat_detail:
            break
        
        messages = chat_detail.get('messages', [])
        if not messages:
            break
        
        last_msg = messages[-1]
        if last_msg['role'] != 'assistant':
            break
        
        parent_order = last_msg['chat_order']
        
        # 続きを要求
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
    return full_response.replace(END_MARKER, "").strip()

# 使用例
response = get_complete_response(
    client,
    chat_uid,
    "Pythonのリスト内包表記について詳しく説明してください。"
)
print(response)
```

## 2. 無応答時のリカバリ（新規チャット作成）

### 問題

LLM側のコンディション不良などにより、応答が返ってこない場合があります。そのチャットは**もう使えない**可能性が高いです。

### 解決策: 新規チャットでやり直し

**原因の切り分けより先に復旧を優先**し、同じ `assistant_uid` で新規チャットを作成して同じ指示を再投入します。

### 実装手順

#### Step 1: タイムアウトや例外を検知

```python
import time
from newtonx_adk import APIError, ChatError

try:
    response = client.send_message(chat_uid, message)
    if not response:
        # 応答がNoneの場合も無応答とみなす
        raise Exception("応答が返ってきませんでした")
except (APIError, ChatError, Exception) as e:
    # エラー発生 = 無応答の可能性
    print(f"エラー発生: {e}")
```

#### Step 2: 新規チャットを作成してやり直し

```python
def send_with_recovery(client, assistant_uid, message, max_retries=2):
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
            
            # メッセージ送信
            response = client.send_message(chat_uid, message)
            
            if response:
                return response, chat_uid
            
            # 応答がNoneの場合は新規チャットで再試行
            chat_uid = None
            
        except (APIError, ChatError, Exception) as e:
            print(f"エラー発生（試行 {attempt + 1}/{max_retries}）: {e}")
            chat_uid = None  # 次の試行で新規作成
            if attempt < max_retries - 1:
                time.sleep(1)  # 少し待ってから再試行
            else:
                raise
    
    raise Exception("最大リトライ回数に達しました")

# 使用例
try:
    response, chat_uid = send_with_recovery(
        client,
        assistant_uid,
        "質問内容"
    )
    print(response)
except Exception as e:
    print(f"最終的に失敗: {e}")
```

### 完全な実装例（添付ファイル対応）

```python
def send_with_recovery_and_attachments(
    client,
    assistant_uid,
    message,
    image_ids=None,
    document_ids=None,
    audio_file_path=None,
    max_retries=2
):
    """無応答時に新規チャットでやり直す（添付ファイル対応）"""
    chat_uid = None
    
    for attempt in range(max_retries):
        try:
            # 注意: audio_file_path を使う場合は「Gemini」アシスタント（音声対応）を選ぶこと
            # 新規チャット作成
            if not chat_uid:
                chat_uid = client.create_chat(
                    assistant_uid=assistant_uid,
                    title=f"リカバリチャット {attempt + 1}"
                )
            
            # 添付ファイルを再アップロード（必要に応じて）
            retry_image_ids = image_ids
            retry_document_ids = document_ids
            
            # メッセージ送信
            response = client.send_message(
                chat_uid=chat_uid,
                message=message,
                image_ids=retry_image_ids,
                document_ids=retry_document_ids,
                audio_file_path=audio_file_path
            )
            
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
    # 画像をアップロード
    image_id = client.upload_image(chat_uid, "/path/to/image.jpg")
    
    # リカバリ付きで送信
    response, new_chat_uid = send_with_recovery_and_attachments(
        client,
        assistant_uid,
        "この画像を分析してください",
        image_ids=[image_id]
    )
    print(response)
except Exception as e:
    print(f"最終的に失敗: {e}")
```

## ベストプラクティス

### 1. 長文出力が必要な場合は必ず終端マーカーを要求

```python
# ✅ 良い例
message = "長文のレポートを作成してください。最後に __END_OF_RESPONSE__ を付けてください。"

# ❌ 悪い例
message = "長文のレポートを作成してください。"  # 終端マーカーがない
```

### 2. 無応答時は原因切り分けより先に復旧を優先

```python
# ✅ 良い例: すぐに新規チャットでやり直す
if not response:
    new_chat_uid = client.create_chat(assistant_uid, "リカバリ")
    response = client.send_message(new_chat_uid, message)

# ❌ 悪い例: 同じチャットに延々と再送
for i in range(10):  # 無限に再送
    response = client.send_message(chat_uid, message)
    if response:
        break
```

### 3. 無限ループを防ぐ

```python
# ✅ 良い例: 最大試行回数を設定
max_iterations = 10
for i in range(max_iterations):
    ...

# ❌ 悪い例: 無限ループ
while True:  # 危険
    ...
```

## 関連API

- `send_message(...) -> Optional[str]`: メッセージ送信（応答がNoneの場合もある）
- `get_chat(chat_uid: str) -> Optional[Dict]`: チャット詳細取得
- `create_chat(...) -> Optional[str]`: 新規チャット作成

## 注意事項

- 終端マーカーは**ユーザーが定義する文字列**です（`__END_OF_RESPONSE__` は一例）
- 無応答時のリカバリは**同じ指示を再投入**します（添付ファイルも再アップロードが必要な場合あり）
- 元のチャットは必要に応じて削除（`delete_chat()`）できます
