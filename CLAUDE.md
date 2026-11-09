# CLAUDE.md

このファイルは Claude Code が毎回必ず読む。チームで Claude を使うときの共通ルール。
ルールを変えるときは PR でレビューを受ける。

## プロジェクト
AIエージェントを活用した社内問い合わせ・業務支援システム（卒業制作）。
React + Vite / Flask（Python 3.12）/ PostgreSQL 17 + pgvector / OpenAI API / AWS（Terraform）。

必ず以下を読んでから作業すること:
@docs/architecture/overview.md
@docs/development/coding-style.md
@docs/development/git-workflow.md

必要に応じて読む: `docs/development/review.md`、`docs/architecture/aws.md`、`docs/architecture/ai.md`、`infra/terraform/README.md`

## 絶対に守ること
1. **秘密情報を扱わない**: `.env`、`*.tfvars`、`backend.hcl` を読まない・作らない・コミットしない。API キーやパスワードをコードやログに書かない。利用者から秘密情報を貼られたら、使わずに削除してもらうよう伝える
2. **本物の社内資料・個人情報を使わない**: テストデータ・サンプルはダミーで作る
3. **main に直接 push しない**: 必ずブランチを作り、PR を出す。`git push --force` は使わない（必要なら `--force-with-lease`）
4. **AWS を勝手に変更しない**: `terraform apply` / `destroy`、`aws` コマンドでの作成・変更・削除は、利用者が明示的に指示したときだけ。`plan` の結果を見せて確認を取ってから実行する
5. **AI が自動で送信・申請する機能を作らない**: 問い合わせなどの送信は、必ず利用者の承認操作を経る（計画書の要件）
6. **根拠のない回答をさせない**: RAG の実装では、根拠資料がない場合に推測で回答しない作りにする
7. **資料の公開範囲を守る**: 検索・引用のクエリでは、必ず利用者の権限と所属部署で絞り込む

## 作業の進め方
- 変更の前に、関係するコードとドキュメントを読む。既存の書き方に合わせる
- コメントと docstring は**日本語・Google 形式**（`docs/development/coding-style.md`）
- 作業を終える前に、テストとコードチェックを実行して通ることを確認する
  ```sh
  docker compose exec api pytest
  docker compose exec api ruff check . && docker compose exec api ruff format --check .
  docker compose exec frontend npm run lint
  ```
- 機能を追加・変更したらテストも書く
- 仕様や構成が変わったら `docs/` も更新する
- PR のタイトルは `<種類>(<範囲>): <何をしたか>`（例: `feat(backend): ログイン API を追加`）。本文は `.github/pull_request_template.md` に沿って書く
- パッケージを追加するときは、公開から2週間以上たったバージョンを使う。追加した理由を PR に書く

## よく使うコマンド
```sh
docker compose up --build                     # 開発環境の起動
docker compose run --rm api uv add <pkg>      # Python のパッケージ追加
docker compose run --rm frontend npm install <pkg>
docker compose exec api flask db migrate -m "説明"
docker compose exec api flask db upgrade
```
