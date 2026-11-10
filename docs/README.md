# ドキュメント一覧

設計書・API 仕様書・開発ルールを置く。仕様を変更するときは Issue に記録し、リーダーの承認を得る。

## 開発ルール（全員が最初に読む）
| ドキュメント | 内容 |
|---|---|
| [development/setup.md](development/setup.md) | 開発環境の作り方（WSL2・Docker・VS Code） |
| [development/git-workflow.md](development/git-workflow.md) | ブランチ・コミット・PR の命名ルール、マージ戦略 |
| [development/review.md](development/review.md) | PR の書き方とレビューの仕方 |
| [development/coding-style.md](development/coding-style.md) | 命名ルール、コメントの書き方（Google 形式） |

## 設計
| ドキュメント | 内容 |
|---|---|
| [architecture/overview.md](architecture/overview.md) | 使用技術とプロジェクトの構成 |
| [architecture/aws.md](architecture/aws.md) | AWS の構成と月額費用 |
| [architecture/ai.md](architecture/ai.md) | AI（Agentic RAG）の構成と評価の方法 |
| [architecture/domain-model.md](architecture/domain-model.md) | ドメインモデル（集約・状態遷移・ルール） |
| [architecture/db.md](architecture/db.md) | DB 設計（テーブル定義・ER 図） |
| [api-spec.md](api-spec.md) | API 仕様書（画面と Flask の取り決め）。すべての画面の API を実装済み |
| [../infra/terraform/README.md](../infra/terraform/README.md) | Terraform で AWS を構築する手順 |
