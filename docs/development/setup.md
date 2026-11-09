# 開発環境のセットアップ

全員の環境を Docker Compose でそろえる。PC に直接 Python や PostgreSQL を入れる必要はない。

## 必要なもの
| ソフト | 用途 |
|---|---|
| Windows 11 + WSL2（Ubuntu） | Linux 環境。Docker が内部で使う |
| Docker Desktop | コンテナの実行 |
| Git | ソース管理 |
| VS Code | エディタ |

PC の目安: メモリ 16GB 以上、SSD の空き 50GB 以上。

## 1. WSL2 を入れる
1. PowerShell を**管理者として実行**し、次を実行する
   ```powershell
   wsl --install
   ```
2. PC を再起動する
3. 起動した Ubuntu の画面でユーザー名とパスワードを設定する
4. 確認（`VERSION` が `2` になっていれば OK）
   ```powershell
   wsl -l -v
   ```

## 2. Docker Desktop を入れる
1. https://www.docker.com/products/docker-desktop/ からインストーラをダウンロードして実行する
   - 「Use WSL 2 instead of Hyper-V」にチェックを入れる
2. Docker Desktop を起動し、Settings を開く
   - General → **Use the WSL 2 based engine** がオン
   - Resources → WSL integration → **Ubuntu** をオン
3. 確認
   ```sh
   docker version
   docker run --rm hello-world
   ```

> Docker Desktop は**起動しておかないと動かない**。`docker` コマンドで `cannot find the file specified` などが出たら、まず Docker Desktop が起動しているか確認する。

## 3. Git を設定する
```sh
git config --global user.name "山田 太郎"
git config --global user.email "GitHub に登録したメールアドレス"
git config --global core.autocrlf input   # 改行コードを LF に保つ
git config --global pull.rebase true
```

GitHub へのログインは GitHub CLI を使うと簡単。
```powershell
winget install GitHub.cli
gh auth login   # GitHub.com → HTTPS → ブラウザでログイン
```
コードが表示されたら**先に Enter を押してから**ブラウザでコードを入力する。

## 4. VS Code を設定する
リポジトリを開くと、おすすめの拡張機能（`.vscode/extensions.json`）のインストールを聞かれるので、すべて入れる。

## 5. リポジトリを clone して起動する
```sh
git clone https://github.com/Graduation-Project-2026-11-09/agent-rag-system.git
cd agent-rag-system
cp .env.example .env      # OPENAI_API_KEY は各自で設定する
docker compose up --build
```

> **置き場所のおすすめ**: WSL（Ubuntu）のホーム（`~/`）に clone すると動作が速い。Windows 側のフォルダ（デスクトップなど）でも動くが、ファイルの変更検知が遅くなることがある。

| URL | 内容 |
|---|---|
| http://localhost:5173 | 画面（「API: ok（DB: OK）」と出れば成功） |
| http://localhost:5000/api/health | API の動作確認 |
| http://localhost:8025 | Mailpit（送信されたメールの確認） |

## よく使うコマンド
```sh
docker compose up -d                        # バックグラウンドで起動
docker compose logs -f api                  # ログを見る
docker compose down                         # 停止
docker compose down -v                      # DB を含めて初期化

docker compose exec api pytest              # テスト
docker compose exec api ruff check .        # コードチェック
docker compose exec api ruff format .       # 整形
docker compose exec api flask db migrate -m "説明"   # マイグレーション作成
docker compose exec api flask db upgrade    # マイグレーション適用
docker compose exec frontend npm run lint   # 画面のコードチェック
```

パッケージを追加したとき:
```sh
docker compose run --rm api uv add <パッケージ名>          # Python
docker compose run --rm frontend npm install <パッケージ名> # 画面
docker compose build                                       # 再ビルド
```

## 困ったとき
| 症状 | 対処 |
|---|---|
| `port is already allocated` | 同じポートを使うアプリを止める（PostgreSQL を PC に直接入れている場合など） |
| 画面を編集しても反映されない | `docker compose restart frontend` |
| パッケージを追加したのに `ModuleNotFoundError` | `docker compose build api` で再ビルド |
| DB の中身をリセットしたい | `docker compose down -v` → `docker compose up` |
| `\r: command not found` | 改行コードが CRLF になっている。`git config --global core.autocrlf input` を設定して clone し直す |
