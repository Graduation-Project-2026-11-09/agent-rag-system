# Terraform（AWS の構成）

構成と費用は [docs/architecture/aws.md](../../docs/architecture/aws.md) を参照。

```
infra/terraform/
├─ bootstrap/      最初に1回だけ apply する（state 用 S3、予算アラート）
├─ modules/
│   ├─ network/    VPC、サブネット、セキュリティグループ
│   ├─ app_server/ EC2、Elastic IP、EC2 の IAM ロール
│   ├─ database/   RDS、DB 接続情報（SSM）
│   ├─ storage/    S3（資料）
│   └─ schedule/   EC2・RDS の自動起動・停止
└─ envs/
    └─ stg/        ステージング
```

## ルール
- AWS のリソースは**コンソールから手で変更しない**。必ずコードを変えて PR を出す
- `terraform apply` はインフラ担当（リーダー）が手元で実行する。PR に `plan` の結果を貼る
- `*.tfvars`、`backend.hcl`、`*.tfstate` は**コミットしない**（`.gitignore` 済み）
- state には DB のパスワードなどが含まれる。state 用の S3 は暗号化・非公開にしている

## 準備
AWS アカウントは「Sign up for AWS (new)」で作っているため、IAM Identity Center は使えない。ログインは `aws login`（ブラウザで承認、12 時間有効）を使う。

1. AWS CLI（2.32.0 以上）を入れてログインする
   ```sh
   winget install Amazon.AWSCLI
   aws login --profile agent-rag-signin     # リージョンを聞かれたら ap-southeast-2
   aws sts get-caller-identity --profile agent-rag-signin
   ```
2. Terraform 用のプロファイルを `~/.aws/config` に追加する（最初の1回だけ）。Terraform は `aws login` のセッションを直接読めないため、`credential_process` で渡す
   ```ini
   [profile agent-rag]
   credential_process = aws configure export-credentials --profile agent-rag-signin --format process
   region = ap-southeast-2
   ```
   > `~/.aws/config` には日本語を書かない（Windows 版の AWS CLI が読めなくなる）
3. Terraform 1.16 系を入れる。[公式サイト](https://releases.hashicorp.com/terraform/)から zip をダウンロードして PATH を通す
4. Terraform を実行するターミナルでプロファイルを指定する
   ```powershell
   $env:AWS_PROFILE = "agent-rag"     # PowerShell
   ```
   ```sh
   export AWS_PROFILE=agent-rag       # bash
   ```
   12 時間たってエラーになったら `aws login --profile agent-rag-signin` をやり直す

## 手順
### 1. bootstrap（最初に1回だけ）
```sh
cd infra/terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars   # budget_email を書く
terraform init
terraform plan
terraform apply
```
- 出力される `tfstate_bucket` と `deploy_stg_role_arn` を控える
- 予算アラートの確認メールが届いたら承認する
- bootstrap の state（`terraform.tfstate`）はローカルにできる。**消さずに保管する**（チームの共有ドライブなど。Git には入れない）

### 2. stg を作る
```sh
cd infra/terraform/envs/stg
cp backend.hcl.example backend.hcl   # bucket を bootstrap の出力に書き換える
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```
RDS の作成に 10 分ほどかかる。

### 3. API キーを設定する
OpenAI の API キーは Terraform では `CHANGE_ME` で作るので、手動で上書きする（コードやチャットに貼らない）。
```sh
aws ssm put-parameter --name /agent-rag/stg/OPENAI_API_KEY --type SecureString --overwrite --value "<キー>"
```

### 4. pgvector を有効にする
初回デプロイ時のマイグレーション（`backend/migrations`）で `CREATE EXTENSION IF NOT EXISTS vector` を実行する。

## 変更するとき
```sh
terraform fmt -recursive
terraform validate
terraform plan     # 結果を PR に貼る
```
PR がマージされたら `terraform apply` する。

## 片付け（stg を消す）
```sh
cd infra/terraform/envs/stg
terraform destroy
```
stg は削除保護をオフにしているので、DB と S3 の中身も消える。
