# システム構成

AIエージェントを活用した社内問い合わせ・業務支援システム。従業員がチャットで質問すると、AI が社内資料を検索して根拠つきで回答する。解決しない場合は担当部署への問い合わせを下書きする（送信は必ず利用者が承認する）。

## 使用技術
| 区分 | 技術 | バージョン |
|---|---|---|
| 画面 | React + Vite（JavaScript） | React 19 / Vite 8 |
| サーバー | Python + Flask（本番は Gunicorn） | Python 3.12 |
| バックグラウンド処理 | worker（Flask のアプリを共有） | |
| DB | PostgreSQL + pgvector（ベクトル検索） | 17 |
| 生成AI | OpenAI API（回答生成・埋め込み） | |
| メール | 開発: Mailpit / AWS: Amazon SES | |
| ファイル保存 | Amazon S3 | |
| Web サーバ | Caddy（画面の配信・`/api` の転送・HTTPS） | |
| パッケージ管理 | uv（Python）/ npm（JavaScript） | |
| コードチェック | ruff（Python）/ ESLint（JavaScript） | |
| テスト | pytest | |
| 開発環境 | Docker Compose | |
| インフラ | AWS（Terraform で管理） | Terraform 1.16 |
| CI/CD | GitHub Actions | |
| AI レビュー | CodeRabbit | |

## 全体図
```
 利用者（PC・スマホのブラウザ）
        │ HTTP(S)
        ▼
 ┌──────────── EC2（Docker Compose）────────────┐
 │  web（Caddy）── 画面のファイルを配信           │
 │     │ /api/*                                  │
 │     ▼                                         │
 │  api（Flask）── ログイン・チャット・各機能     │──▶ OpenAI API
 │  worker ─────── 資料の取り込み・予約配信など   │──▶ S3（資料の原本）
 └──────────┬────────────────────────────────────┘──▶ SES（メール）
            ▼
   RDS（PostgreSQL 17 + pgvector）
```
開発時は Caddy の代わりに Vite の開発サーバが `/api` を Flask に転送する。

## ディレクトリ構成
```
agent-rag-system/
├─ frontend/                 画面（React）。モックアップ（55 画面）を流用
│   ├─ src/api/              API の呼び出し（認証は実 API、それ以外はまだモック）
│   ├─ src/mocks/            ダミーデータとモック API（実装が進んだら削除）
│   ├─ src/pages/            画面
│   └─ Caddyfile             stg・本番で画面を配信する Caddy の設定
├─ backend/                  API と worker（同じ Python プロジェクト）
│   ├─ app/                  Flask アプリ
│   │   ├─ __init__.py       create_app（アプリの組み立て）
│   │   ├─ config.py         設定（環境変数から読む）
│   │   ├─ extensions.py     DB などの拡張機能
│   │   └─ routes/           API のエンドポイント
│   ├─ worker/               バックグラウンド処理
│   ├─ migrations/           DB マイグレーション（Flask-Migrate）
│   ├─ tests/                pytest
│   ├─ pyproject.toml        依存パッケージと ruff・pytest の設定
│   └─ uv.lock               依存パッケージのバージョン固定
├─ db/init/                  DB 初期化 SQL（pgvector の有効化）
├─ infra/terraform/          AWS の構成（Terraform）
├─ deploy/stg/               stg の EC2 で動かす compose.yml と deploy.sh
├─ docs/                     設計書・開発ルール
├─ .github/                  CI・PR テンプレート
├─ .claude/                  Claude Code の設定
├─ CLAUDE.md                 Claude Code が必ず読むルール
├─ compose.yml               ローカル開発用の Docker Compose
└─ .env.example              環境変数のひな形
```

## 環境
| 環境 | 場所 | 反映のタイミング | データ |
|---|---|---|---|
| 開発 | 各自の PC（Docker Compose） | 保存すると即反映 | ダミー資料のみ |
| ステージング | AWS | main にマージすると自動（数分後） | ダミー資料のみ |
| 本番（発表用） | AWS | タグを付けたときだけ（設定予定） | ダミー資料のみ |

## 権限
| 権限 | できること |
|---|---|
| 一般利用者 | 質問、根拠資料の確認、問い合わせの作成・確認、お知らせの確認 |
| 部署担当者 | 上記 ＋ 自部署あての問い合わせへの回答、自部署の資料のアップロード、お知らせの配信 |
| 管理者 | すべて（アカウント・資料・お知らせ・全部署の問い合わせ・利用履歴の管理） |
