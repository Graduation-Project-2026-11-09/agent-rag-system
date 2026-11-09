# API 仕様（Flask 実装用）

フロントエンド（React）が呼び出す API の一覧です。モック（`src/mocks/handlers.js`）は、ここに書いた形と同じデータを返します。
Flask で同じ形のレスポンスを返せば、`.env` の `VITE_USE_MOCK=false` だけで実 API に切り替わります。

- ベース URL：`/api`（開発時は Vite のプロキシで `http://localhost:5000` に転送されます）
- 認証：Flask のセッション Cookie（`HttpOnly`）。フロントは `credentials: 'include'` で送信します
- 日時：ISO 8601 形式の文字列（例：`2026-10-02T09:00:00+09:00`）
- エラー：HTTP ステータスと `{ "message": "画面に表示する文言" }`
  - 401：未ログイン
  - 403：権限なし
  - 404：対象が存在しない
  - 409：重複

## 権限

| role | 説明 | 利用できる API |
|---|---|---|
| `user` | 一般利用者 | 認証、チャット、自分の問い合わせ、お知らせ |
| `staff` | 部署担当者 | user の範囲 ＋ `/admin/inquiries`（`handlesDepartment` あてのみ）、`/admin/documents`、`/admin/notices` |
| `admin` | 管理者 | すべて |

## 認証

| メソッド | パス | リクエスト | レスポンス |
|---|---|---|---|
| POST | `/auth/login` | `{ email, password }` | `User` |
| POST | `/auth/logout` | — | 204 |
| GET | `/auth/me` | — | `User`（未ログインは 401） |

```jsonc
// User
{ "id": "u1", "employeeId": "E10234", "name": "山田 花子", "email": "yamada@example.co.jp",
  "department": "営業部", "role": "user", "handlesDepartment": null,
  "status": "active", // active | invited | suspended
  "createdAt": "...", "lastLoginAt": "..." }
```

## マスタ

| メソッド | パス | レスポンス |
|---|---|---|
| GET | `/departments` | `string[]` |
| GET | `/document-categories` | `string[]` |

## チャット

| メソッド | パス | リクエスト | レスポンス |
|---|---|---|---|
| GET | `/conversations` | — | `Conversation[]`（messages は含めない。updatedAt の降順） |
| GET | `/conversations/:id` | — | `Conversation`（messages を含む） |
| POST | `/conversations` | `{ title }` | `Conversation` |
| DELETE | `/conversations/:id` | — | 204 |
| POST | `/conversations/:id/messages` | `{ content }` | **SSE**（下記） |
| POST | `/messages/:id/feedback` | `{ feedback: "good" \| "bad" \| null }` | 204 |

### 質問送信（Server-Sent Events）

`Content-Type: text/event-stream` で、Agent の処理ステップを順番に送信し、最後に回答を送ります。

```
event: step
data: {"id":"s1","type":"analyze","title":"質問内容を分析","detail":"意図：…","items":["氏名の変更","扶養の追加"]}

event: step
data: {"id":"s2","type":"plan","title":"検索戦略を決定","detail":"…","queries":["婚姻 届出","氏名変更 手続き"]}

event: step
data: {"id":"s3","type":"search","title":"社内資料を検索（1回目）","results":[{"documentId":"d3","title":"人事手続きマニュアル","section":"3.2 氏名変更","score":0.91}]}

event: step
data: {"id":"s4","type":"evaluate","title":"情報の充足度を評価：不足あり","detail":"…","sufficient":false}

event: step
data: {"id":"s5","type":"search","title":"追加検索（2回目）","queries":["特別休暇 結婚"],"results":[…]}

event: answer
data: { …Message… }

event: error
data: {"message":"回答の生成に失敗しました"}
```

`step.type` は `analyze`（質問分析）・`plan`（検索戦略）・`search`（検索）・`evaluate`（充足度評価）・`generate`（回答作成）のいずれかです。

Flask の実装例：

```python
@app.post("/api/conversations/<cid>/messages")
@login_required
def send_message(cid):
    content = request.json["content"]
    def stream():
        for step in agent.run(content, user=current_user):   # ステップを yield する
            yield f"event: step\ndata: {json.dumps(step, ensure_ascii=False)}\n\n"
        message = agent.final_message()
        yield f"event: answer\ndata: {json.dumps(message, ensure_ascii=False)}\n\n"
    return Response(stream_with_context(stream()), mimetype="text/event-stream")
```

```jsonc
// Message（role: "assistant"）
{
  "id": "m10", "role": "assistant", "content": "Markdown の回答。根拠は [1] のように番号で引用",
  "createdAt": "...",
  "agent": { "steps": [/* step と同じ形 */], "searchCount": 2, "durationMs": 5000 },
  "sources": [
    { "index": 1, "documentId": "d3", "title": "人事手続きマニュアル", "fileType": "docx",
      "department": "人事部", "updatedAt": "...", "section": "3.2 氏名変更", "page": 8,
      "excerpt": "回答に使用したチャンクの本文" }
  ],
  "nextSteps": [
    { "id": "t1", "title": "氏名変更届の提出", "description": "人事システム > 各種届出", "department": "人事部", "deadline": "速やかに" }
  ],
  // Agent が「社内資料だけでは解決できない」と判断したときだけ値を入れる。それ以外は null
  "inquirySuggestion": { "department": "人事部", "reason": "…", "subject": "…", "body": "AI が作成した問い合わせ文の下書き" },
  "inquiryId": null,   // 問い合わせ送信済みなら Inquiry の id
  "feedback": null
}
// Message（role: "user"）: { "id", "role": "user", "content", "createdAt" }
```

> 検索対象は、ログインユーザーが閲覧できる資料に限定してください（`visibility` が `all`、または `departments` にユーザーの所属部署を含むもの）。

## 問い合わせ

| メソッド | パス | 権限 | リクエスト | レスポンス |
|---|---|---|---|---|
| GET | `/inquiries/mine` | 全員 | — | `Inquiry[]` |
| POST | `/inquiries` | 全員 | `{ messageId, department, subject, body, context }` | `Inquiry` |
| GET | `/admin/inquiries?status=&department=&q=` | staff/admin | — | `Inquiry[]` |
| GET | `/admin/inquiries/:id` | staff/admin | — | `Inquiry` |
| PATCH | `/admin/inquiries/:id` | staff/admin | `{ status?, assignee? }` | `Inquiry` |
| POST | `/admin/inquiries/:id/replies` | staff/admin | `{ body }` | `Inquiry` |

`POST /inquiries` は、利用者が確認画面で「承認して送信」を押したときだけ呼ばれます（AI が自動で送信することはありません）。

```jsonc
// Inquiry
{ "id": "q1", "number": "INQ-2026-0142", "userId": "u6", "userName": "田中 優子", "userDepartment": "開発部",
  "department": "人事部", "subject": "…", "body": "…",
  "status": "open",  // open | in_progress | resolved
  "assignee": null, "createdAt": "...", "updatedAt": "...",
  "context": { "question": "元の質問", "sources": ["育児・介護休業規程 第18条"], "aiAnswerSummary": "…" },
  "replies": [{ "id": "r1", "author": "高橋 健太", "authorRole": "staff", "body": "…", "createdAt": "..." }] }
```

## お知らせ・通知設定

| メソッド | パス | 権限 | リクエスト | レスポンス |
|---|---|---|---|---|
| GET | `/notices` | 全員 | — | `{ id, title, body, priority, publishAt, read }[]`（配信中かつ自分が対象のもの） |
| POST | `/notices/:id/read` | 全員 | — | 204 |
| GET | `/admin/notices` | staff/admin | — | `Notice[]` |
| GET | `/admin/notices/:id` | staff/admin | — | `Notice` |
| POST | `/admin/notices` | staff/admin | `NoticeInput` | `Notice` |
| PUT | `/admin/notices/:id` | staff/admin | `NoticeInput` | `Notice` |
| DELETE | `/admin/notices/:id` | staff/admin | — | 204 |
| GET | `/admin/notification-settings` | admin | — | `NotificationSettings` |
| PUT | `/admin/notification-settings` | admin | `NotificationSettings` | `NotificationSettings` |

```jsonc
// NoticeInput（publishAt が null で isDraft=false なら即時配信）
{ "title": "…", "body": "…", "priority": "normal", // normal | important
  "target": { "type": "all" }, // または { "type": "departments", "departments": ["営業部"] }
  "channels": ["in_app", "email"], "publishAt": null, "expireAt": null, "isDraft": false }
// Notice = NoticeInput（isDraft を除く）＋
//   { id, status: draft | scheduled | published | expired, createdBy, createdAt, readCount, targetCount }

// NotificationSettings
{ "events": [{ "key": "inquiry_created", "label": "…", "description": "…", "inApp": true, "email": true }],
  "departmentContacts": [{ "department": "人事部", "email": "jinji@example.co.jp" }],
  "weeklyReport": { "enabled": true, "dayOfWeek": "mon", "recipients": "admin@example.co.jp" } }
```

## アカウント（管理者）

| メソッド | パス | リクエスト | レスポンス |
|---|---|---|---|
| GET | `/admin/users?q=&department=&role=&status=` | — | `User[]` |
| POST | `/admin/users` | `{ employeeId, name, email, department, role, handlesDepartment, passwordMode: "invite" \| "password", password }` | `User`（重複は 409） |
| POST | `/admin/users/bulk` | `{ users: [{ employeeId, name, email, department, role }] }` | `{ created, errors: [{ row, message }] }` |
| PATCH | `/admin/users/:id` | `User` の一部（`status` の変更で利用停止・再開） | `User` |
| DELETE | `/admin/users/:id` | — | 204 |
| POST | `/admin/users/:id/password-reset` | — | 204 |

## ドキュメント

| メソッド | パス | 権限 | リクエスト | レスポンス |
|---|---|---|---|---|
| GET | `/admin/documents?q=&category=&department=&status=` | staff/admin | — | `Document[]` |
| GET | `/admin/documents/:id` | staff/admin | — | `Document`（`versions` を含む） |
| POST | `/admin/documents` | staff/admin | `multipart/form-data`：`file`、`meta`（JSON 文字列） | `Document`（status: processing） |
| PATCH | `/admin/documents/:id` | staff/admin | `{ title?, category?, department?, visibility?, tags? }` | `Document` |
| POST | `/admin/documents/:id/reindex` | staff/admin | — | `Document` |
| DELETE | `/admin/documents/:id` | staff/admin | — | 204 |
| GET | `/documents/:id` | 全員（閲覧権限がある資料のみ） | — | `Document` |
| GET | `/documents/:id/file` | 全員（閲覧権限がある資料のみ） | — | 原本ファイル |

```jsonc
// meta
{ "category": "人事手続き", "department": "人事部", "visibility": { "type": "all" },
  "tags": ["結婚", "扶養"], "effectiveDate": "2026-10-01" }

// Document
{ "id": "d1", "title": "就業規則", "fileName": "shugyo_kisoku_2026.pdf", "fileType": "pdf", "size": 1843200, "pages": 48,
  "category": "…", "department": "人事部", "visibility": { "type": "all" }, "tags": ["休暇"],
  "status": "indexed",            // processing | indexed | error
  "processingStage": null,        // processing 中：uploaded | extracting | chunking | embedding
  "errorMessage": null, "chunks": 212, "version": 5, "effectiveDate": "2026-04-01",
  "updatedAt": "...", "uploadedBy": "佐藤 美咲",
  "versions": [{ "version": 5, "updatedAt": "...", "by": "佐藤 美咲", "note": "2026年4月改定" }] }
```

アップロード後、フロントは `GET /admin/documents/:id` を約 0.7 秒ごとに呼び、`processingStage` と `status` で進み具合を表示します。

## 利用履歴（管理者）

| メソッド | パス | レスポンス |
|---|---|---|
| GET | `/admin/logs?days=&result=&department=&q=` | `Log[]` |
| GET | `/admin/logs/summary?days=` | `{ total, resolvedRate, inquiryCount, avgSearchCount, avgDurationMs, goodRate, savedMinutes }` |

```jsonc
// Log
{ "id": "l1", "at": "...", "userId": "u1", "userName": "…", "department": "…", "question": "…",
  "messageId": "m10", "searchCount": 2, "sourceCount": 5,
  "result": "resolved",   // resolved（自己解決） | inquiry（問い合わせ） | no_answer（回答不可）
  "feedback": "good", "durationMs": 5200, "steps": [/* Agent ステップ */], "sources": ["就業規則 第32条"] }
```

`savedMinutes` は企画書の試算と同じく「自己解決 1 件あたり 20 分」で計算しています。
