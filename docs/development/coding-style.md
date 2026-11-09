# コーディング規約

自動で直せるものはツールに任せる（Python: ruff、JavaScript: ESLint、共通: `.editorconfig`）。ここにはツールで決まらないことを書く。

## 命名ルール

### Python（backend / worker）
| 対象 | 形式 | 例 |
|---|---|---|
| 変数・関数・メソッド | snake_case | `search_documents()` |
| クラス | PascalCase | `SearchAgent` |
| 定数 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT = 3` |
| モジュール（ファイル） | snake_case | `search_agent.py` |
| 非公開（モジュール内だけで使う） | 先頭に `_` | `_build_query()` |
| 真偽値 | `is_` / `has_` / `can_` で始める | `is_active`, `has_permission` |

### JavaScript / React（frontend）
| 対象 | 形式 | 例 |
|---|---|---|
| 変数・関数 | camelCase | `sendMessage()` |
| コンポーネント（関数・ファイル） | PascalCase | `ChatInput.jsx` |
| カスタムフック | `use` で始める camelCase | `useChatHistory.js` |
| 定数 | UPPER_SNAKE_CASE | `MAX_FILE_SIZE_MB` |
| イベント処理 | `handle` + 対象 + 動作 | `handleSubmitClick` |
| props で渡すイベント | `on` + 動作 | `onSubmit` |

### DB（PostgreSQL）
| 対象 | 形式 | 例 |
|---|---|---|
| テーブル | snake_case・**複数形** | `users`, `inquiries`, `document_chunks` |
| カラム | snake_case | `display_name` |
| 主キー | `id` | |
| 外部キー | `<参照先テーブルの単数形>_id` | `user_id`, `department_id` |
| 日時 | `<動作>_at`（タイムゾーン付き） | `created_at`, `updated_at`, `deleted_at` |
| 真偽値 | `is_` で始める | `is_published` |

### API
| 対象 | 形式 | 例 |
|---|---|---|
| パス | `/api/` + 複数形の名詞（ケバブケース） | `GET /api/inquiries`, `POST /api/chat-sessions` |
| 1件の操作 | `/<複数形>/<id>` | `PATCH /api/inquiries/42` |
| JSON のキー | **camelCase**（画面・API 仕様書とそろえる。Python 側の `to_dict()` で変換する） | `{"createdAt": "..."}` |

### その他
| 対象 | 形式 | 例 |
|---|---|---|
| 環境変数・SSM パラメータ名 | UPPER_SNAKE_CASE | `OPENAI_API_KEY` |
| AWS リソース名 | `agent-rag-<環境>-<役割>` | `agent-rag-stg-app` |
| Terraform のリソース名・変数 | snake_case | `aws_instance.this`, `instance_type` |

### 共通
- 名前は英語で、略さない（`usr` ではなく `user`。`id` `url` `db` など一般的なものは可）
- 1文字の変数はループのインデックスなどに限る

## コメントの書き方（Google 形式）
- コメント・docstring は**日本語**で書く
- 「何をしているか」はコードで分かるようにし、コメントには**なぜそうしているか**を書く
- 公開する関数・クラス（他のファイルから使うもの）には docstring を書く

### Python: Google スタイルの docstring
```python
def search_documents(query: str, user: User, limit: int = 5) -> list[DocumentChunk]:
    """利用者が閲覧できる資料の中から、質問に近いチャンクを検索する。

    公開範囲の絞り込みは検索の前に行う。検索後に絞り込むと、
    件数が limit より少なくなるため。

    Args:
        query: 検索語。検索Agent が言い換えたもの。
        user: 質問した利用者。所属部署で公開範囲を判定する。
        limit: 返す最大件数。

    Returns:
        類似度の高い順に並んだチャンクのリスト。該当がなければ空のリスト。

    Raises:
        EmbeddingError: OpenAI API でのベクトル化に失敗した場合。
    """
```

| セクション | 書くこと |
|---|---|
| 1行目 | 何をするか（1文） |
| 本文（任意） | 補足、注意点、なぜそうしたか |
| `Args:` | 引数ごとの説明 |
| `Returns:` | 戻り値の説明（`None` を返すなら省略） |
| `Raises:` | 呼び出し側が対処すべき例外 |

クラスは1行目にクラスの役割を書き、属性があれば `Attributes:` に書く。

### JavaScript: JSDoc（Google JavaScript Style Guide）
```jsx
/**
 * 質問を送信し、回答をストリーミングで受け取る。
 *
 * 生成中に停止できるよう、AbortController を外から渡せるようにしている。
 *
 * @param {string} question 利用者が入力した質問。
 * @param {AbortSignal} signal 生成を停止するためのシグナル。
 * @return {Promise<Answer>} 根拠資料つきの回答。
 */
export async function sendQuestion(question, signal) {
```

コンポーネントは props を説明する。
```jsx
/**
 * 回答に使った根拠資料のプレビュー。
 *
 * @param {Object} props
 * @param {Source} props.source 表示する資料。
 * @param {() => void} props.onClose 閉じるボタンを押したとき。
 */
export default function SourcePreview({ source, onClose }) {
```

### 行コメント
```python
# OpenAI API の料金を抑えるため、再検索は最大 3 回まで（計画書のリスク対策⑦）
MAX_RETRY_COUNT = 3
```

### TODO
```python
# TODO(#45): 画像だけの PDF に対応する
```
TODO には必ず Issue 番号を付ける。
