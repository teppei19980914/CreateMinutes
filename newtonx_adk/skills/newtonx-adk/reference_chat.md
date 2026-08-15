# フォルダ内チャット作成の詳細ガイド

## 概要

NewtonX ADKでチャットをフォルダ配下に作成する際の正しい手順と、よくある間違いを回避する方法を説明します。

## 重要なポイント

**フォルダIDの取得**: `get_folders()` の戻り値では `folder['id']` を使用します。`uid` や `uuid` フィールドは存在しません。

## 手順

### 1. フォルダ一覧の取得

```python
folders = client.get_folders()
```

**戻り値の形式**:
```python
[
    {
        'type': 'folder',
        'id': 5656,           # ← これを使用（整数）
        'name': '領収書読み取り'
    },
    {
        'type': 'folder',
        'id': 6316,
        'name': 'AI最新技術'
    }
]
```

### 2. フォルダの検索または作成

```python
def get_or_create_folder(client, folder_name):
    """フォルダを取得、存在しなければ作成"""
    folders = client.get_folders()
    
    # 名前で検索
    target_folder = next(
        (f for f in folders if f['name'] == folder_name),
        None
    )
    
    if target_folder:
        return target_folder['id']  # ← 'id' を使用
    else:
        # 存在しない場合は作成
        folder_id = client.create_folder(folder_name)
        return folder_id
```

### 3. フォルダ内にチャットを作成

```python
# フォルダIDを取得
folder_id = get_or_create_folder(client, "プロジェクトA")

# チャットを作成（folder_uid パラメータに渡す）
chat_uid = client.create_chat(
    assistant_uid=assistant_uid,
    title="新しいチャット",
    folder_uid=folder_id  # ← folder_uid パラメータ名だが、値は folder['id']
)
```

## よくある間違い

### ❌ 間違い1: `uid` や `uuid` を使おうとする

```python
# 間違い
folder_uid = folder['uid']  # ← このフィールドは存在しない
chat_uid = client.create_chat(..., folder_uid=folder_uid)
```

**正しい方法**:
```python
# 正しい
folder_id = folder['id']  # ← 'id' を使用
chat_uid = client.create_chat(..., folder_uid=folder_id)
```

### ❌ 間違い2: フォルダ名を直接渡す

```python
# 間違い
chat_uid = client.create_chat(
    assistant_uid=assistant_uid,
    title="チャット",
    folder_uid="プロジェクトA"  # ← 文字列ではなく、ID（整数）が必要
)
```

**正しい方法**:
```python
# 正しい
folders = client.get_folders()
folder = next((f for f in folders if f['name'] == "プロジェクトA"), None)
if folder:
    chat_uid = client.create_chat(
        assistant_uid=assistant_uid,
        title="チャット",
        folder_uid=folder['id']  # ← ID（整数）を渡す
    )
```

## 実装例

### 完全な実装例

```python
from newtonx_adk import NewtonXClient, ConfigManager

config = ConfigManager()
client = NewtonXClient(config)
client.authenticate()

# アシスタント取得
assistants = client.get_assistants()
assistant_uid = assistants[0]['uid']

# フォルダ取得または作成
def ensure_folder(client, folder_name):
    folders = client.get_folders()
    folder = next((f for f in folders if f['name'] == folder_name), None)
    if folder:
        return folder['id']
    else:
        return client.create_folder(folder_name)

# フォルダ内にチャット作成
folder_id = ensure_folder(client, "開発用チャット")
chat_uid = client.create_chat(
    assistant_uid=assistant_uid,
    title="テストチャット",
    folder_uid=folder_id
)

print(f"チャット作成完了: {chat_uid}")
```

## 関連API

- `get_folders() -> List[Dict]`: フォルダ一覧取得
- `create_folder(name: str) -> Optional[str]`: フォルダ作成（戻り値はフォルダID）
- `create_chat(assistant_uid: str, title: Optional[str] = None, folder_uid: Optional[str] = None) -> Optional[str]`: チャット作成
- `move_chat_to_folder(chat_uid: str, folder_uid: str) -> bool`: 既存チャットをフォルダに移動

## 注意事項

- `folder_uid` パラメータ名は `uid` だが、実際に渡す値は `folder['id']`（整数）です
- フォルダが存在しない場合は、`create_folder()` で作成してから使用します
- `create_folder()` の戻り値はフォルダID（整数）です
