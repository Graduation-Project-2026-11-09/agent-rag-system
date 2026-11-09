# Git の運用ルール

## 全体の流れ
```
Issue を作る
  → main からブランチを作る
  → コミット・push
  → PR を作る（CI と CodeRabbit が自動で走る）
  → リーダーか副リーダーが Approve
  → Squash マージ（auto-merge を使うと承認と同時にマージされる）
  → main にマージされると stg に自動デプロイ（数分後）
```

## ブランチ
- `main` は常に動く状態に保つ。**直接 push しない**（ブランチ保護で禁止している）
- 作業ごとに `main` から新しいブランチを作る。1つの PR は1つの目的にする

### ブランチ名
```
<種類>/<Issue番号>-<短い説明（英語・ケバブケース）>
```
| 例 | 意味 |
|---|---|
| `feat/12-chat-input` | Issue #12 のチャット入力機能 |
| `fix/34-login-error` | Issue #34 のログインのバグ修正 |
| `docs/git-workflow` | Issue のないドキュメント修正 |

種類は下の「PR のタイトル」と同じものを使う。

## PR のタイトル（＝ main に残るコミットメッセージ）
Squash マージでは **PR のタイトルがそのまま main のコミットメッセージになる**ので、次の形式で書く（[Conventional Commits](https://www.conventionalcommits.org/ja/) に準拠）。

```
<種類>(<範囲>): <何をしたか（日本語）>
```

| 種類 | 使うとき |
|---|---|
| `feat` | 機能の追加 |
| `fix` | バグ修正 |
| `docs` | ドキュメントだけの変更 |
| `refactor` | 動作を変えないコードの整理 |
| `test` | テストの追加・修正 |
| `ci` | GitHub Actions の変更 |
| `chore` | 上記以外（設定、依存パッケージの更新など） |

範囲（省略可）: `frontend` / `backend` / `worker` / `ai` / `db` / `infra`

例:
- `feat(frontend): チャット画面に質問例を表示する`
- `fix(backend): 利用停止中のアカウントでログインできる問題を修正`
- `chore(infra): stg の EC2 を t3.small に変更`

## コミット
- ブランチ内のコミットは最終的に1つにまとめられるので、細かくてよい
- メッセージは PR のタイトルと同じ形式を推奨（必須ではない）
- 1つのコミットに関係ない変更を混ぜない

## マージ戦略: Squash マージのみ
リポジトリの設定で **Squash マージだけ**を許可している。

| 理由 |
|---|
| main の履歴が「1 PR = 1 コミット」になり、何をいつ入れたか追いやすい |
| 途中の「typo 修正」などのコミットが main に残らない |
| 問題があったときに PR 単位で `git revert` できる |

マージの条件（ブランチ保護）:
- CI（backend / frontend）が成功している
- リーダーか副リーダーが Approve している
- ブランチが最新の main を取り込んでいる（古いときは PR 画面の「Update branch」を押す）
- レビューのコメントがすべて Resolve されている

マージ後、ブランチは自動で削除される。

## main の変更を取り込む
```sh
git switch main
git pull
git switch feat/12-chat-input
git rebase main          # 競合したら修正して git rebase --continue
git push --force-with-lease
```
`--force` は使わず `--force-with-lease` を使う（他人の push を消さないため）。

## リリース（本番）
本番へは `v1.0.0` のようなタグを付けたときだけ反映する（設定予定）。
