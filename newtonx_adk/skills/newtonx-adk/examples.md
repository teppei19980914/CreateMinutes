# 実装例集

## 概要

NewtonX ADKを使用した実装例をまとめています。よくあるパターンをコピー&ペーストして使用できます。

## TIP: web_search と knowledge_search は相互排他

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
    message="社内ナレッジの範囲で要点をまとめて",
    web_search=False,
    knowledge_search=True,
)
```

## 例1: フォルダ配下でチャット作成 → 画像解析 → 続き質問

```python
from newtonx_adk import NewtonXClient, ConfigManager

# 初期化
config = ConfigManager()
client = NewtonXClient(config)
client.authenticate()

# アシスタント取得
assistants = client.get_assistants()
assistant_uid = assistants[0]['uid']

# フォルダ取得または作成
def get_or_create_folder(client, folder_name):
    folders = client.get_folders()
    folder = next((f for f in folders if f['name'] == folder_name), None)
    if folder:
        return folder['id']
    else:
        return client.create_folder(folder_name)

folder_id = get_or_create_folder(client, "画像解析プロジェクト")

# フォルダ内にチャット作成
chat_uid = client.create_chat(
    assistant_uid=assistant_uid,
    title="画像解析チャット",
    folder_uid=folder_id
)

# 画像アップロード
image_id = client.upload_image(chat_uid, "/path/to/image.jpg")

# 画像解析を依頼
response1 = client.send_message(
    chat_uid=chat_uid,
    message="この画像を分析してください",
    image_ids=[image_id]
)
print(f"応答1: {response1}")

# チャット詳細を取得して parent_order を特定
chat_detail = client.get_chat(chat_uid)
messages = chat_detail.get('messages', [])

# 最後のアシスタント応答の chat_order を取得
last_assistant = None
for msg in reversed(messages):
    if msg['role'] == 'assistant':
        last_assistant = msg
        break

if last_assistant:
    parent_order = last_assistant['chat_order']
    
    # parent_order を指定して続きを聞く
    response2 = client.send_message(
        chat_uid=chat_uid,
        message="この画像から読み取れる数値データを表形式でまとめてください",
        parent_order=parent_order
    )
    print(f"応答2: {response2}")
```

## 例2: 終端マーカー方式で長文出力を取得

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
config = ConfigManager()
client = NewtonXClient(config)
client.authenticate()

assistants = client.get_assistants()
chat_uid = client.create_chat(
    assistant_uid=assistants[0]['uid'],
    title="長文出力テスト"
)

response = get_complete_response(
    client,
    chat_uid,
    "Pythonのリスト内包表記について、構文、使用例、パフォーマンス、ベストプラクティスを含めて詳しく説明してください。"
)
print(response)
```

## 例3: 無応答時のリカバリ付きメッセージ送信

```python
import time
from newtonx_adk import NewtonXClient, ConfigManager, APIError, ChatError

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
                time.sleep(1)
            else:
                raise
    
    raise Exception("最大リトライ回数に達しました")

# 使用例
config = ConfigManager()
client = NewtonXClient(config)
client.authenticate()

assistants = client.get_assistants()
assistant_uid = assistants[0]['uid']

try:
    response, chat_uid = send_with_recovery(
        client,
        assistant_uid,
        "質問内容"
    )
    print(f"応答: {response}")
    print(f"チャットUID: {chat_uid}")
except Exception as e:
    print(f"最終的に失敗: {e}")
```

## 例4: 画像とドキュメントの同時添付

```python
from newtonx_adk import NewtonXClient, ConfigManager

config = ConfigManager()
client = NewtonXClient(config)
client.authenticate()

assistants = client.get_assistants()
chat_uid = client.create_chat(
    assistant_uid=assistants[0]['uid'],
    title="複数ファイル解析"
)

# 画像とドキュメントをアップロード
image_id = client.upload_image(chat_uid, "/path/to/image.jpg")
document_id = client.upload_document(chat_uid, "/path/to/document.pdf")

# 両方を同時に添付して送信（画像とドキュメントは同時指定可能）
response = client.send_message(
    chat_uid=chat_uid,
    message="画像とドキュメントを参照して、関連性を分析してください",
    image_ids=[image_id],
    document_ids=[document_id]  # ← 同時指定OK
)

print(response)
```

## 例5: 音声ファイルの添付と要約

```python
from newtonx_adk import NewtonXClient, ConfigManager, FileUploadError, APIError

config = ConfigManager()
client = NewtonXClient(config)
client.authenticate()

assistants = client.get_assistants()
# 音声は「Gemini」アシスタントのみ対応
gemini = next((a for a in assistants if "Gemini" in a.get("name", "")), None)
if not gemini:
    raise Exception("音声対応の Gemini アシスタントが見つかりません")

chat_uid = client.create_chat(
    assistant_uid=gemini['uid'],
    title="音声要約"
)

# 音声ファイルを直接指定（upload不要）
try:
    response = client.send_message(
        chat_uid=chat_uid,
        message="この音声を要約してください",
        audio_file_path="/path/to/audio.wav"  # ← 直接指定
    )
    
    if response:
        print(f"要約: {response}")
    else:
        print("応答が返ってきませんでした")
        
except FileUploadError as e:
    print(f"ファイルアップロードエラー: {e}")
except APIError as e:
    print(f"APIエラー: {e}")
```

## 例6: エラーハンドリング付きの完全な実装

```python
from newtonx_adk import (
    NewtonXClient,
    ConfigManager,
    AuthenticationError,
    APIError,
    FileUploadError,
    ChatError
)

def safe_send_message(client, chat_uid, message, **kwargs):
    """エラーハンドリング付きメッセージ送信"""
    try:
        response = client.send_message(chat_uid, message, **kwargs)
        return response, None
    except AuthenticationError as e:
        print(f"認証エラー: {e}")
        print("認証を再実行してください")
        return None, "authentication_error"
    except FileUploadError as e:
        print(f"ファイルアップロードエラー: {e}")
        return None, "upload_error"
    except APIError as e:
        print(f"APIエラー: {e}")
        print(f"ステータスコード: {e.status_code}")
        return None, "api_error"
    except ChatError as e:
        print(f"チャットエラー: {e}")
        return None, "chat_error"
    except Exception as e:
        print(f"予期しないエラー: {e}")
        return None, "unknown_error"

# 使用例
config = ConfigManager()
client = NewtonXClient(config)

if not client.authenticate():
    print("認証に失敗しました")
    exit(1)

assistants = client.get_assistants()
chat_uid = client.create_chat(
    assistant_uid=assistants[0]['uid'],
    title="エラーハンドリングテスト"
)

response, error_type = safe_send_message(
    client,
    chat_uid,
    "こんにちは！"
)

if response:
    print(f"応答: {response}")
else:
    print(f"エラーが発生しました: {error_type}")
```

## 例7: 複数チャットの管理

```python
from newtonx_adk import NewtonXClient, ConfigManager

config = ConfigManager()
client = NewtonXClient(config)
client.authenticate()

assistants = client.get_assistants()
assistant_uid = assistants[0]['uid']

# 複数のチャットを作成
chat_uids = []
for i in range(3):
    chat_uid = client.create_chat(
        assistant_uid=assistant_uid,
        title=f"チャット {i+1}"
    )
    chat_uids.append(chat_uid)

# 各チャットにメッセージを送信
for chat_uid in chat_uids:
    response = client.send_message(
        chat_uid,
        f"チャット {chat_uids.index(chat_uid) + 1} からのメッセージ"
    )
    print(f"チャット {chat_uids.index(chat_uid) + 1}: {response}")

# チャット一覧を取得
all_chats = client.get_chats()
print(f"全チャット数: {len(all_chats)}")

# 特定のチャットを削除
if chat_uids:
    client.delete_chat(chat_uids[0])
    print(f"チャット {chat_uids[0]} を削除しました")
```

## 例8: フォルダ操作の完全な例

```python
from newtonx_adk import NewtonXClient, ConfigManager

config = ConfigManager()
client = NewtonXClient(config)
client.authenticate()

assistants = client.get_assistants()
assistant_uid = assistants[0]['uid']

# フォルダ一覧を取得
folders = client.get_folders()
print("既存のフォルダ:")
for folder in folders:
    print(f"  - {folder['name']} (ID: {folder['id']})")

# 新しいフォルダを作成
new_folder_id = client.create_folder("新規プロジェクト")
print(f"フォルダ作成: {new_folder_id}")

# フォルダ内にチャットを作成
chat_uid = client.create_chat(
    assistant_uid=assistant_uid,
    title="プロジェクトチャット",
    folder_uid=new_folder_id  # ← folder['id'] を使用
)
print(f"チャット作成: {chat_uid}")

# フォルダ内のチャット一覧を取得
folder_chats = client.get_folder_chats(new_folder_id)
print(f"フォルダ内のチャット数: {len(folder_chats)}")

# 既存のチャットをフォルダに移動
existing_chat_uid = client.create_chat(
    assistant_uid=assistant_uid,
    title="移動前のチャット"
)
client.move_chat_to_folder(existing_chat_uid, new_folder_id)
print(f"チャット {existing_chat_uid} をフォルダに移動しました")
```

## 関連リソース

- [SKILL.md](SKILL.md): メインのSkillドキュメント
- [reference_chat.md](reference_chat.md): フォルダ操作の詳細
- [reference_parent_order.md](reference_parent_order.md): parent_orderの詳細
- [reference_attachments.md](reference_attachments.md): 添付ファイルの詳細
- [reference_response_reliability.md](reference_response_reliability.md): 回答の信頼性対策
- [troubleshooting.md](troubleshooting.md): トラブルシューティング
