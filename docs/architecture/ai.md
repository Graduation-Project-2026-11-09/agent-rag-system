# AI の構成（Agentic RAG）

> **このドキュメントは一部未定。** 計画書（プロジェクト計画書）に書かれた方針をまとめたもの。「未定」の項目は、決まりしだい更新する。

## 方針（計画書より）
- 一般的な RAG に AI エージェントの機能を組み合わせた **Agentic RAG** を採用する
- 回答には**必ず根拠資料を表示**する。根拠が見つからない場合は推測で答えず、担当部署への問い合わせを提案する
- AI は**自動で送信・申請しない**。問い合わせは利用者が確認・承認してから送る
- 通常の RAG と Agentic RAG を**切り替えられるようにし**、同じ質問で「必要な情報を取得できた割合・回答の正確性・回答時間・料金」を比較する
- 開発・検証では**ダミー資料だけ**を使う（外部の AI に本物の社内資料を送らない）

## エージェント
### 検索Agent
質問を分析し、どの資料を・どんな言葉で検索するかを判断する。

```
質問
 │
 ▼
① 質問分析 ─── 何を調べればよいか（観点）を洗い出す
 │              例:「結婚した」→ 氏名変更・扶養・社会保険・慶弔制度
 ▼
② 検索語の展開 ─ 利用者の言葉を、社内資料の正式な言葉に言い換える
 │
 ▼
③ 検索 ─────── pgvector でベクトル検索（利用者が見られる資料だけ）
 │
 ▼
④ 充足度の評価 ─ 回答に必要な情報がそろったか判断する
 │      │
 │      └─ 足りない → 条件を変えて ②へ（再検索は最大 1 回）
 ▼
⑤ 回答の作成 ─── 観点ごとに整理し、根拠資料の番号を付ける
                  次に行う手続きを、期限・担当部署つきのチェックリストにする
```
①〜④の過程は画面にリアルタイムで表示する（質問送信から 3 秒以内に表示を開始する）。

### 業務支援Agent
資料だけでは解決できない場合に、次の行動を提案する。
- 「担当部署への問い合わせを作成しますか？」と提案する
- 会話の内容・確認済みの資料・不明点から、宛先部署・件名・本文の下書きを作る
- 利用者が編集し、「承認して送信」を押したときだけ送信する

### 実装（`backend/app/ai/`）
| 項目 | 決めたこと |
|---|---|
| 作り方 | ライブラリを使わず自作する。①〜⑤ を順に呼ぶ普通の関数（`agent.py`）。流れが決まっているので、AI に道具を選ばせる仕組みは不要。呼ぶ回数（＝費用）を制御しやすい |
| AI の呼び出し | OpenAI の Responses API と構造化出力（JSON Schema・strict）。各段階の出力の形を Pydantic で決める（`llm.py`）。`store: false` で入力を OpenAI 側に保存させない |
| 通常の RAG | 質問文で 1 回検索して ⑤ だけ行う（`run_basic`）。`AI_RAG_MODE=basic` でチャットも切り替えられる |
| 根拠がないとき | 検索で何も見つからなければ ⑤ を呼ばずに決まった文を返し、問い合わせを提案する。⑤ が存在しない番号を引用したら消す（ルール 6） |
| 公開範囲 | 検索の SQL の中で `visibility_type = 'all'` または `visible_departments` に所属部署を含む資料に絞る。管理者はすべて（ルール 7）。HNSW 索引で絞り込みと併用するため `hnsw.iterative_scan = relaxed_order` を使う |
| ストリーミング | SSE。①〜⑤ の過程を 1 段階ずつ `step` イベントで送り、最後に `answer` を送る（docs/api-spec.md） |
| プロンプト | `prompts.py` にまとめ、Git で変更履歴を残す。変えたら評価で確かめる |
| 費用の記録 | 回答ごとに入力・出力のトークン数と費用の目安を `messages` に保存し、利用履歴で見られるようにする |
| DB の接続 | AI の応答を待つ間はトランザクションを開かない（`idle_in_transaction_session_timeout` が 60 秒のため）。利用者の情報は `Viewer` に写してから使う |

### 処理ごとのモデル（環境変数で変えられる）
| 処理 | 環境変数 | 既定 | 推論の量 |
|---|---|---|---|
| ① 質問分析 | `AI_MODEL_ANALYZE` | gpt-6.1-terra | low |
| ② 検索語の展開 | `AI_MODEL_EXPAND` | gpt-6.1-terra | low |
| ③ 検索（埋め込み） | `AI_EMBEDDING_MODEL` | text-embedding-3-large | — |
| ④ 充足度の評価 | `AI_MODEL_EVALUATE` | gpt-6.1-sol | medium |
| ⑤ 回答の作成 | `AI_MODEL_ANSWER` | gpt-6.1-sol | medium |
| 問い合わせの下書き | `AI_MODEL_INQUIRY` | gpt-6.1-terra | low |

質問 1 回あたりの費用の目安は、検索Agent で約 7.5 円（再検索 1 回で約 10 円）、通常の RAG で約 4 円（2026-11 の料金、1 ドル 150 円）。

### 評価の実行（`backend/app/evaluation.py`）
評価用の質問セット（下記）を、通常の RAG と検索Agent の両方で解く。料金を半額にするため OpenAI の Batch API を使う。
```sh
docker compose exec api flask seed-documents            # ダミー資料を取り込んでおく
docker compose exec api flask evaluate start            # 全問・両方式。最初の段階を Batch で送る
docker compose exec api flask evaluate advance <実行ID>  # 結果が届いていれば次の段階を送る（終わるまで繰り返す）
docker compose exec api flask evaluate start --question q01 --question q11 --sync  # 1 問ずつ実行（回答時間を測る）
```
- Batch は 1 回の結果が届くまで最大 24 時間かかる。検索Agent は段階ごとに Batch を送るので、全体で最大 6 回（①・②・④・②・④・⑤ と問い合わせの下書き）
- Batch API では回答時間を測れない。回答時間は `--sync` か、チャットの利用履歴で測る
- 結果は `backend/evaluation/runs/<実行ID>/` に保存する（Git には含めない）。`report.md` に方式ごとの集計と 1 問ずつの回答、`results.json` にすべての値
- 自動で計算する指標: 検索の再現率（正解の見出しが検索結果に入ったか）、引用の再現率（回答で引用したか）、問い合わせ提案の正解率、平均費用。回答の正確さ（含めるべき点）は `report.md` を見て人が確認する

## 資料の取り込み（worker）
```
登録（資料管理画面 / 開発用の flask import-document）
   → 原本を保存（AWS: S3 / 開発: documents ボリュームの /data/documents）
   → documents・document_versions に登録（status=processing, processing_stage=uploaded）

worker（5 秒ごとに DB を確認。取り込み待ちがなくなるまで続けて処理する）
   → extracting: テキスト抽出
   → chunking  : チャンク分割
   → embedding : ベクトル化（OpenAI）
   → document_chunks に保存 → status=indexed（失敗したら status=error と理由）
```
| 項目 | 決めたこと |
|---|---|
| 対応形式 | PDF（pypdf）・Word（.docx、python-docx）・テキスト（.txt・.md）。Excel・PowerPoint はその後 |
| 埋め込みモデル | **text-embedding-3-large・3072 次元**。pgvector の `vector` 型は 2000 次元までしか HNSW 索引を作れないため、半精度の **`halfvec(3072)`** で保存する（検索の精度はほぼ変わらない） |
| ベクトル化する文 | 「資料名 + 見出し + 本文」。「第18条」だけでは何の資料か分からないため |
| チャンクの分け方 | **見出し + 文字数**。「第○章」「第○条」「3.2 」「3. 」「# 」「【】」などの見出しで分け、800 字を超える部分は文の区切りで分ける（前のチャンクと 100 字重ねる）。本文のない見出し（「第3章」の直後に「第18条」など）は次の見出しとまとめる。Word の見出しスタイルも使う |
| 表記の揺れ | 見出しの判定は、全角英数字を半角にしてから行う（NFKC）。PDF から取り出した文字は全角・半角が混ざりやすいため。保存する本文は元の表記のまま |
| worker への伝え方 | DB の `documents.status` を見に行く。`SELECT … FOR UPDATE SKIP LOCKED` で、worker が複数あっても二重に処理しない |
| 止まった処理 | 取り込みを始めてから 30 分たっても終わらない資料は、worker が止まったとみなして取り込み直す |
| 版 | 改定したら新しい版を追加する。取り込みが終わったら古い版のチャンクは削除する（版の情報と原本は履歴として残る）。取り込み中に新しい版が登録されたら、古い版の結果は保存しない |
| 読み取れない資料 | 画像だけの PDF・パスワード付き PDF・壊れたファイルは status=error にし、理由を `error_message` に保存する（reindex で取り込み直せる） |

### テーブル
| テーブル | 内容 |
|---|---|
| `documents` | 資料。公開範囲（`visibility_type`: all / departments、`visible_departments`）、取り込みの状態、最新の版の番号 |
| `document_versions` | 版。原本のファイル名・形式・サイズ・ページ数・保存先のキー（ランダムな名前）・施行日 |
| `document_chunks` | チャンク。本文・見出し（`section`）・ページ・ベクトル（`halfvec(3072)`、HNSW 索引・コサイン距離） |

### コード
| 場所 | 内容 |
|---|---|
| `backend/app/ingestion/registration.py` | 資料の登録（原本の保存と取り込み待ちへの登録） |
| `backend/app/ingestion/extract.py` | テキスト抽出 |
| `backend/app/ingestion/chunking.py` | チャンク分割 |
| `backend/app/ingestion/pipeline.py` | worker が行う取り込みの流れ |
| `backend/app/ai/embedding.py` | ベクトル化（取り込みと検索の両方で使う） |
| `backend/app/storage.py` | 原本の保存先（`DOCUMENTS_BUCKET` があれば S3、なければ `DOCUMENTS_DIR`） |

### 開発環境で試す
```sh
# ダミー資料 23 件をまとめて登録する（登録済みの資料は飛ばす）。worker が数秒〜数分で取り込む
docker compose exec api flask seed-documents
# 1 件だけ登録する（パスは api コンテナの /app = backend/ から見た位置）
docker compose exec api flask import-document seed/documents/files/vpn_manual.md --department 情報システム部
# 部署限定にする場合
docker compose exec api flask import-document <ファイル> --department 人事部 --visible-department 人事部
```
`.env` に `OPENAI_API_KEY` が必要（設定したら `docker compose up -d` で worker を作り直す）。本物の社内資料は登録しない（OpenAI API に送られるため）。

### ダミー資料（`backend/seed/documents/`）
架空の会社「株式会社サンプル」の規程・マニュアル 23 件。画面のモック（`frontend/src/mocks/db.js`）と資料名・部署・公開範囲・見出しをそろえている。
| 内容 | 件数 |
|---|---|
| 部署 | 人事部 7・総務部 5・経理部 4・情報システム部 4・営業部 1・開発部 1・マーケティング部 1 |
| 形式 | PDF 9（うち 1 件は文字のない画像だけの PDF で、取り込みに失敗する例）・Word 6・Markdown 6・テキスト 2 |
| 公開範囲 | 全員 17・部署限定 6 |

- 内容は `source/*.md` に書き、`seed/build_documents.py` で各形式のファイル（`files/`）を作る。資料を直したら作り直してコミットする
  ```sh
  docker compose run --rm --no-deps api uv run --with reportlab==5.1.0 python seed/build_documents.py
  ```
- 資料の一覧（部署・公開範囲・タグ）は `manifest.json`
- テキストの資料は見出しの記号がなく、書き方（「1. 」「第1条」など）から見出しを判定する。Markdown は `#` の行だけを見出しにする
- 分かっている制約: PDF の表は、1 セルが 1 行に分かれて取り出される（行と列の対応が失われる）

### 評価用の質問セット（`backend/evaluation/questions.json`）
ダミー資料に対する 48 問。質問ごとに、質問者の部署・権限、正解の根拠（資料名と見出し）、回答に含めるべき点、問い合わせを提案すべき部署を持つ。
| 種類 | 内容 |
|---|---|
| single | 1つの資料の1か所で答えられる |
| multi | 複数の資料を組み合わせる（例: 結婚したときの手続き） |
| paraphrase | 利用者の言葉と資料の言葉が違う（例: 「引っ越した」→ 住所変更） |
| not_in_documents | 資料に答えがない。推測せず問い合わせを提案するのが正解 |
| restricted | 質問者が閲覧できない資料にしか答えがない。引用してはいけない |
| unreadable | 取り込みに失敗した資料にしか答えがない |

`tests/test_seed_data.py` で、正解の見出しが実際のチャンクに存在すること、質問者がその資料を閲覧できることを確認している。

## 目標値（計画書より・案）
| 項目 | 目標 |
|---|---|
| 検索過程の表示開始 | 質問送信から 3 秒以内 |
| 回答完了 | 再検索を含めて平均 30 秒以内 |
| 同時利用 | 50 名程度 |

## 費用の対策
- 再検索の回数に上限（1 回）を設ける。計画書では 3 回だったが、質問1回あたりの費用を約 16 円から約 10 円に抑えるため 1 回にした（AI の動作確認と評価は担当者1人が自費のクレジットで行う）
- AI の利用量（トークン数）を記録し、利用履歴で確認できるようにする
- OpenAI の API キーに利用上限を設定する

## 未定の項目
| 項目 | 検討すること |
|---|---|
| 検索方式 | 今はベクトル検索のみ。評価の結果を見て、キーワード検索と組み合わせる（ハイブリッド検索）か決める |
| 類似度の下限 | `MIN_SCORE = 0.25`（これより低いチャンクは使わない）。評価の結果を見て調整する |
