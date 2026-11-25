# 開発環境のセットアップ

全員の環境を Docker Compose でそろえる。PC に直接 Python や PostgreSQL を入れる必要はない。
コマンドはすべて **PowerShell**（Windows の「ターミナル」）で打つ。Ubuntu は使わない。

所要時間の目安: 30〜60 分（ダウンロード待ちを含む）

## 必要なもの
| ソフト | コマンド | 用途 |
|---|---|---|
| WSL2 | `wsl` | Docker Desktop が内部で使う Linux の仕組み |
| Docker Desktop | `docker` | アプリ（画面・API・DB）を動かす |
| Git | `git` | clone・コミット・プッシュ |
| GitHub CLI | `gh` | GitHub へのログイン |
| VS Code | `code` | エディタ |

PC の目安: メモリ 16GB 以上（8GB だと重い）、SSD の空き 30GB 以上。

> **Git と GitHub CLI は別のソフト**。`gh` だけ入れても `git clone` はできない。

## 1. WSL2 を入れる
1. スタートボタンを右クリック →「**ターミナル（管理者）**」を開く
2. 次を実行する
   ```powershell
   wsl --install
   ```
3. 「要求された操作は正常に終了しました。変更を有効にするには、システムを再起動する必要があります。」と出たら PC を再起動する
4. 再起動後に Ubuntu の画面が開いたら、ユーザー名とパスワードを決めて入力する。**開かなくても気にしなくてよい**（Ubuntu は使わない）

> 以前に WSL や Docker Desktop を入れたことがある PC では、Ubuntu が入らないことがある。今回は Ubuntu を使わないので、そのまま次へ進んでよい。

## 2. Docker Desktop を入れる
1. https://www.docker.com/products/docker-desktop/ からダウンロードする
   - ほとんどの PC は **Download for Windows – AMD64**（Intel の CPU も AMD64）
   - Snapdragon の PC だけ ARM64。迷ったら PowerShell で `$env:PROCESSOR_ARCHITECTURE` を実行して、出た方を選ぶ
2. インストーラの「Configuration」画面は**初期値のまま OK**
   - Per-user installation（Recommended）→ **WSL 2**
   - Allow Windows Containers はチェックしない
3. 再起動を求められたら再起動する
4. Docker Desktop を起動する。利用規約は Accept、サインインとアンケートは **Skip** でよい
5. 左下が緑色の「**Engine running**」になれば OK

Settings は**変更しなくてよい**（インストール時に WSL 2 を選んでいれば設定済み）。
「Expose daemon on tcp://localhost:2375 without TLS」は**オフのまま**にする（オンにすると外部から操作される危険がある）。

> Docker Desktop は**起動しておかないと動かない**。`docker` コマンドでエラーが出たら、まず Docker Desktop が起動しているか確認する。

## 3. Git・GitHub CLI・VS Code を入れる
```powershell
winget install Git.Git
winget install GitHub.cli
winget install Microsoft.VisualStudioCode
```
初回に「ソース契約条件に同意しますか？」と聞かれたら `Y` を入力する。

**入れ終わったらターミナルを閉じて開き直す**（閉じないと「認識されません」と出る）。

確認（**すべて**バージョンが表示されれば OK）:
```powershell
git --version
gh --version
docker version
```

> `winget` が使えないときは、Microsoft Store で「アプリ インストーラー」を更新する。それでも使えなければ https://git-scm.com/downloads/win と https://cli.github.com からインストーラを入れる（設定は初期値のまま）。

## 4. Git と GitHub の初期設定（最初の 1 回だけ）
```powershell
git config --global user.name "自分の名前"
git config --global user.email "GitHub に登録したメールアドレス"
git config --global core.autocrlf input   # 改行コードを LF に保つ
git config --global pull.rebase true
```

GitHub にログインする:
```powershell
gh auth login
```
| 質問 | 選ぶもの |
|---|---|
| Where do you use GitHub? | GitHub.com |
| What is your preferred protocol for Git operations? | HTTPS |
| Authenticate Git with your GitHub credentials? | Yes |
| How would you like to authenticate GitHub CLI? | Login with a web browser |

コードが表示されたら、**先に Enter を押してから**ブラウザでコードを入力し「Authorize」を押す。

確認:
```powershell
gh auth status   # 「✓ Logged in to github.com account 〇〇」と出れば OK
```

> 組織（Graduation-Project-2026-11-09）の招待メールが届いている人は「Join」を押しておく。承認しないとプッシュできない。

## 5. clone して起動する
Docker Desktop が起動している（Engine running）ことを確認してから実行する。
```powershell
cd ~\Desktop
git clone https://github.com/Graduation-Project-2026-11-09/agent-rag-system.git
cd agent-rag-system
copy .env.example .env
docker compose up --build -d
```
初回は 5〜10 分かかる。`OPENAI_API_KEY` は AI 機能を作るときに各自で `.env` に設定する（ログインまでは不要）。

## 6. DB を準備する
```powershell
docker compose exec api flask db upgrade
docker compose exec api flask seed-users
```
`seed-users: 5 件登録しました` と出れば OK。**これをやらないとログインできない。**

## 7. 動作確認
http://localhost:5173 を開き、次のダミーアカウントでログインできれば完了。

- メールアドレス: `yamada@example.co.jp`
- パスワード: `password123`（`.env` の `SEED_USER_PASSWORD`）

ローカル専用のアカウントで、stg のアカウントとは別。

| URL | 内容 |
|---|---|
| http://localhost:5173 | 画面 |
| http://localhost:5000/api/health | API の動作確認 |
| http://localhost:8025 | Mailpit（送信されたメールの確認） |

最後に VS Code で開く:
```powershell
code .
```
おすすめの拡張機能（`.vscode/extensions.json`）のインストールを聞かれたら、すべて入れる。

## 毎日の使い方
| やりたいこと | コマンド |
|---|---|
| 開発を始める | Docker Desktop を起動 → `docker compose up -d` |
| 終わる | `docker compose down` |
| 最新の main を取り込む | `git switch main` → `git pull` → `docker compose up --build -d` → `docker compose exec api flask db upgrade` |
| 調子がおかしい | `docker compose down` → `docker compose up --build -d` |
| DB を作り直す | `docker compose down -v` → `docker compose up -d` → 6 をもう一度 |

## よく使うコマンド
```powershell
docker compose logs -f api                  # ログを見る
docker compose exec api pytest              # テスト
docker compose exec api ruff check .        # コードチェック
docker compose exec api ruff format .       # 整形
docker compose exec api flask db migrate -m "説明"   # マイグレーション作成
docker compose exec api flask db upgrade    # マイグレーション適用
docker compose exec frontend npm run lint   # 画面のコードチェック
```

パッケージを追加したとき:
```powershell
docker compose run --rm api uv add <パッケージ名>          # Python
docker compose run --rm frontend npm install <パッケージ名> # 画面
docker compose build                                       # 再ビルド
```

## 困ったとき
| 症状 | 対処 |
|---|---|
| `git` / `gh` / `docker` が「認識されません」 | 入っていないか、ターミナルを開き直していない。3 をやり直す |
| `wsl --install` で `0x80370102` など仮想化のエラー | BIOS で仮想化がオフ。PC のメーカー名と「仮想化 有効」で検索してオンにする |
| `wsl --install` でヘルプが表示されて終わる | WSL は入っている。そのまま次へ進んでよい |
| `docker` で `cannot find the file specified` など | Docker Desktop が起動していない |
| `git clone` で `already exists` | 同じ名前のフォルダが残っている。消すか別の場所で実行する |
| `git clone` で `Could not resolve host` | ネットにつながっていない。学校の Wi-Fi で駄目ならテザリングで試す |
| `port is already allocated` | 同じポートを使うアプリを止める（PostgreSQL を PC に直接入れている場合など） |
| `service "api" is not running` | 起動に失敗している。`docker compose logs api` の結果をチームに共有する |
| 画面は出るのにログインできない | 6 をやっていない |
| 画面を編集しても反映されない | `docker compose restart frontend` |
| パッケージを追加したのに `ModuleNotFoundError` | `docker compose build api` で再ビルド |
| `\r: command not found` | 改行コードが CRLF になっている。`git config --global core.autocrlf input` を設定して clone し直す |
| PC が重い | メモリ 8GB だと厳しい。使わないアプリを閉じる |
