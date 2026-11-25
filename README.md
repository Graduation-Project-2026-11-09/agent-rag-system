# AIエージェントを活用した社内問い合わせ・業務支援システム

| 区分 | 技術 |
|---|---|
| 画面 | React + Vite |
| サーバー | Python 3.12 / Flask（Gunicorn）/ worker |
| DB | PostgreSQL 17 + pgvector |
| メール | 開発: Mailpit / AWS: Amazon SES |
| 生成AI | OpenAI API |

## ディレクトリ構成

```
frontend/   画面（React）
backend/    API（Flask）と worker
db/init/    DB 初期化 SQL（pgvector の有効化）
docs/       設計書・API 仕様書
.github/    GitHub Actions・PR テンプレート
```

## 開発環境のセットアップ

初めての人は [docs/development/setup.md](docs/development/setup.md) の手順どおりに進める。

### 必要なもの
- Windows 11 + WSL2（Ubuntu は不要）
- Docker Desktop（起動しておく）
- Git、GitHub CLI、VS Code

### 起動

```powershell
git clone https://github.com/Graduation-Project-2026-11-09/agent-rag-system.git
cd agent-rag-system
copy .env.example .env
docker compose up --build -d
docker compose exec api flask db upgrade   # DB のテーブルを作る
docker compose exec api flask seed-users   # ダミー利用者を登録する（ログイン用）
```

http://localhost:5173 で `yamada@example.co.jp` / `password123` でログインできれば OK。

| URL | 内容 |
|---|---|
| http://localhost:5173 | 画面 |
| http://localhost:5000/api/health | API の動作確認 |
| http://localhost:8025 | Mailpit（送信されたメールの確認） |

### よく使うコマンド

```sh
docker compose exec api pytest              # テスト
docker compose exec api ruff check .        # コードチェック
docker compose exec api ruff format .       # 整形
docker compose exec api flask db migrate -m "説明"   # マイグレーション作成
docker compose exec api flask db upgrade    # マイグレーション適用
docker compose exec frontend npm run lint   # 画面のコードチェック
docker compose down -v                      # DB を含めて初期化
```

Python のパッケージを追加したときは `docker compose run --rm api uv add <パッケージ名>` を実行してから、`docker compose build api` で再ビルドする。

## 開発ルール
- `main` には直接 push しない。ブランチ（`feature/xxx`、`fix/xxx`）を作り、プルリクエストでレビューを受けてからマージする
- CI（テスト・コードチェック）が通らないとマージできない
- `.env` や API キーはコミットしない。開発ではダミー資料だけを使う
- `main` にマージするとステージング（AWS）に自動で反映される
