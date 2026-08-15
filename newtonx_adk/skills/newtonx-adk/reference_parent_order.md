# parent_order の正しい扱い方

## 概要

`parent_order` は、メッセージをスレッドの文脈に紐付けるために使用するパラメータです。**前のメッセージの `chat_order` を指定**することで、そのメッセージへの返信として扱われます。

## 重要なポイント

**`parent_order` には `chat_order` を指定**: `id` や `uuid` ではなく、`message['chat_order']`（整数）を使用します。

## 手順

### 1. チャット詳細を取得

```python
chat_detail = client.get_chat(chat_uid)
```

**戻り値の `messages` 構造**:
```python
{
    'messages': [
        {
            'role': 'user',
            'content': 'バイブコーディングとは',
            'chat_order': 1,        # ← これを使用
            'parent_order': 0,      # 0はルートメッセージ
            'model': 'gpt-4o',
            ...
        },
        {
            'role': 'assistant',
            'content': 'バイブコーディングとは、AIを活用して...',
            'chat_order': 2,        # ← これを使用
            'parent_order': 1,      # メッセージ1への返信
            'model': 'gpt-4o',
            ...
        }
    ]
}
```

### 2. 返信したいメッセージを特定

```python
# 最後のアシスタント応答に返信する場合
chat_detail = client.get_chat(chat_uid)
messages = chat_detail.get('messages', [])

# 最後のアシスタントメッセージを取得
last_assistant_msg = None
for msg in reversed(messages):
    if msg['role'] == 'assistant':
        last_assistant_msg = msg
        break

if last_assistant_msg:
    parent_order = last_assistant_msg['chat_order']  # ← 'chat_order' を使用
```

### 3. parent_order を指定してメッセージ送信

```python
response = client.send_message(
    chat_uid=chat_uid,
    message="続きを教えて",
    parent_order=parent_order  # ← chat_order の値を渡す
)
```

## よくある間違い

### ❌ 間違い1: `id` や `uuid` を使おうとする

```python
# 間違い
parent_order = message['id']  # ← このフィールドは存在しない、または文字列
response = client.send_message(..., parent_order=parent_order)
```

**正しい方法**:
```python
# 正しい
parent_order = message['chat_order']  # ← 'chat_order'（整数）を使用
response = client.send_message(..., parent_order=parent_order)
```

### ❌ 間違い2: `parent_order` を省略してしまう

```python
# 間違い: 前のメッセージへの返信なのに parent_order を指定しない
response = client.send_message(
    chat_uid=chat_uid,
    message="続きを教えて"  # ← parent_order が指定されていない
)
# これだと新しいスレッドとして扱われ、文脈が失われる
```

**正しい方法**:
```python
# 正しい: parent_order を指定して文脈を維持
chat_detail = client.get_chat(chat_uid)
last_msg = chat_detail['messages'][-1]
parent_order = last_msg['chat_order']

response = client.send_message(
    chat_uid=chat_uid,
    message="続きを教えて",
    parent_order=parent_order  # ← 文脈を維持
)
```

### ❌ 間違い3: `parent_order` に間違った値を指定

```python
# 間違い: 存在しない chat_order を指定
response = client.send_message(
    chat_uid=chat_uid,
    message="続きを教えて",
    parent_order=999  # ← 存在しない chat_order
)
```

**正しい方法**:
```python
# 正しい: 実際に存在する chat_order を取得して使用
chat_detail = client.get_chat(chat_uid)
messages = chat_detail.get('messages', [])

# 返信したいメッセージを特定
target_msg = messages[-1]  # 例: 最後のメッセージ
parent_order = target_msg['chat_order']  # ← 実際に存在する値

response = client.send_message(
    chat_uid=chat_uid,
    message="続きを教えて",
    parent_order=parent_order
)
```

## 実装例

### 基本的な使用例

```python
from newtonx_adk import NewtonXClient, ConfigManager

config = ConfigManager()
client = NewtonXClient(config)
client.authenticate()

# チャット作成
assistants = client.get_assistants()
chat_uid = client.create_chat(
    assistant_uid=assistants[0]['uid'],
    title="parent_orderテスト"
)

# 最初のメッセージ
response1 = client.send_message(chat_uid, "Pythonのリストとタプルの違いは？")
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
        message="具体例も教えてください",
        parent_order=parent_order  # ← 前の応答への返信として扱われる
    )
    print(f"応答2: {response2}")
```

### ヘルパー関数

```python
def send_followup(client, chat_uid, message):
    """前のアシスタント応答への返信を送信"""
    chat_detail = client.get_chat(chat_uid)
    if not chat_detail:
        raise Exception("チャットが見つかりません")
    
    messages = chat_detail.get('messages', [])
    
    # 最後のアシスタントメッセージを取得
    last_assistant = None
    for msg in reversed(messages):
        if msg['role'] == 'assistant':
            last_assistant = msg
            break
    
    if not last_assistant:
        # アシスタント応答がない場合は通常送信
        return client.send_message(chat_uid, message)
    
    parent_order = last_assistant['chat_order']
    return client.send_message(
        chat_uid=chat_uid,
        message=message,
        parent_order=parent_order
    )

# 使用例
response = send_followup(client, chat_uid, "続きを教えて")
```

## 関連API

- `get_chat(chat_uid: str) -> Optional[Dict]`: チャット詳細取得（`messages` 配列を含む）
- `send_message(chat_uid: str, message: str, parent_order: int = 0) -> Optional[str]`: メッセージ送信

## 注意事項

- `parent_order=0` はルートメッセージ（デフォルト）
- `parent_order` には**整数**（`chat_order`）を指定します
- `chat_order` は1から始まる連番です
- 存在しない `chat_order` を指定してもエラーにはなりませんが、意図した動作にならない可能性があります
