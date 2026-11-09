# AWS 構成（ステージング）

シドニーリージョン（ap-southeast-2）。AWS アカウントが「Sign up for AWS (new)」で作られており、リージョンは住所の国で自動的に決まり変更できないため。すべて Terraform（`infra/terraform/`）で管理し、AWS コンソールから手で変更しない。構築手順は [infra/terraform/README.md](../../infra/terraform/README.md)。

## 方針
- **最小構成**: ALB・NAT ゲートウェイ・ECS は使わず、EC2 1台 + RDS で動かす
- **平日 9:00〜15:00 だけ起動**: 8:45 に自動起動、15:00 に自動停止（祝日は考慮しない）
- **バックアップは起動中に取る**: RDS は停止中に自動バックアップを取らないため、バックアップは JST 12:00、メンテナンスは水曜 13:00 に設定している
- **ドメインなし**: EC2 の固定 IP（Elastic IP）でアクセスする。ドメインは本番の前に検討する
- **SSH を開けない**: サーバへの接続とデプロイは Systems Manager（Session Manager / Run Command）で行う
- **GitHub に AWS の鍵を置かない**: このアカウントは AWS 管理の SCP で OIDC プロバイダの作成が禁止されているため、GitHub Actions は AWS にログインしない。イメージは GHCR に置き、EC2 が 2 分ごとに取りに行く（下記「自動デプロイ」）
- **無料プランの制限**: RDS のバックアップ保持期間に上限があるため、stg は 1 日にしている（計画書の 7 日は本番で対応）

## 構成図
```
 インターネット
      │ 80 / 443 のみ
 ┌────▼──────────────── VPC 10.0.0.0/16 ─────────────────────────┐
 │ ┌─ パブリックサブネット ─┐   ┌─ プライベートサブネット ×2 ─┐ │
 │ │ EC2 t3.small           │   │ RDS PostgreSQL 17           │ │
 │ │ （Elastic IP）          │──▶│ db.t4g.micro・シングル AZ   │ │
 │ │  web / api / worker    │5432│ 毎日バックアップ・1日保持   │ │
 │ └────────────────────────┘   └─────────────────────────────┘ │
 └────────────────────────────────────────────────────────────────┘
   │ IAM ロールで接続
   ├─▶ S3（資料の原本・非公開・7世代保持）
   ├─▶ SSM Parameter Store（DB 接続情報・API キー）
   └─▶ SES（メール）※設定予定

 EventBridge Scheduler ── 平日 8:45 起動 / 15:00 停止 ──▶ EC2・RDS
 GitHub Actions ──▶ GHCR（ghcr.io）へ push ◀── EC2 が 2 分ごとに pull して入れ替え
```

## リソース一覧
| サービス | 設定 | Terraform |
|---|---|---|
| VPC | パブリック1・プライベート2（RDS 用に2つの AZ）。NAT なし | `modules/network` |
| セキュリティグループ | EC2: 80/443 のみ許可。RDS: EC2 からの 5432 のみ許可 | `modules/network` |
| EC2 | t3.small、Ubuntu 24.04、EBS 20GB（暗号化）、スワップ 2GB、IMDSv2 必須、CPU クレジットは standard（追加料金なし） | `modules/app_server` |
| Elastic IP | 停止・起動しても IP が変わらない | `modules/app_server` |
| RDS | PostgreSQL 17、db.t4g.micro、20GB gp3、シングル AZ、非公開 | `modules/database` |
| S3 | 資料の原本。非公開・暗号化・バージョニング（7世代） | `modules/storage` |
| SSM Parameter Store | `/agent-rag/stg/DATABASE_URL`、`SECRET_KEY`、`OPENAI_API_KEY`、`DOCUMENTS_BUCKET`、`SEED_USER_PASSWORD`（動作確認用ダミー利用者のパスワード） | `envs/stg`、`modules/database` |
| EventBridge Scheduler | EC2・RDS の自動起動・停止 | `modules/schedule` |
| IAM | EC2 用ロール、Scheduler 用ロール、GitHub Actions 用ロール（必要な権限だけ） | 各モジュール、`bootstrap` |
| Budgets | 月 $30 を超えそうになったらメール | `bootstrap` |
| S3（state 用） | Terraform の state を保存 | `bootstrap` |

本番は計画書どおり EC2 t3.medium / RDS db.t4g.small を想定（`envs/prod` は未作成）。

## 月額費用の目安（ステージング）
東京リージョンのオンデマンド料金をもとにした（シドニーもほぼ同じ水準）**概算**。1ドル = 150 円で計算。AWS（日本）の請求には別途消費税 10% がかかる。正確な料金は [AWS Pricing Calculator](https://calculator.aws/) で確認すること。

稼働時間: 平日 約 21.7 日 × 6.25 時間（8:45〜15:00）＝ **約 136 時間 / 月**（常時稼働は 730 時間）

| 項目 | 単価（概算） | 平日 9-15 時のみ | 常時稼働 |
|---|---|---|---|
| EC2 t3.small | $0.0272 / 時間 | $3.69 | $19.86 |
| RDS db.t4g.micro | $0.025 / 時間 | $3.39 | $18.25 |
| EBS 20GB（EC2 のディスク） | $0.096 / GB・月 | $1.92 | $1.92 |
| RDS ストレージ 20GB | $0.138 / GB・月 | $2.76 | $2.76 |
| パブリック IPv4（Elastic IP） | $0.005 / 時間 | $3.65 | $3.65 |
| S3（数 GB） | | $0.50 | $0.50 |
| RDS バックアップ（DB サイズ以内） | | $0 | $0 |
| EventBridge Scheduler・SSM・Budgets | 無料枠内 | $0 | $0 |
| データ転送（月 100GB まで無料） | | $0 | $0 |
| **合計（税抜）** | | **約 $16（約 2,400 円）** | **約 $47（約 7,000 円）** |

ポイント:
- **停止中もかかる費用**（ディスク・IP アドレス・保存データ）が約 $9 あり、これが最低ラインになる
- スケジュールを使うと、常時稼働より **約 2/3 安くなる**
- OpenAI API の料金は別途かかる（利用量しだい）。API キーに利用上限を設定すること
- 新しい AWS アカウントにはクレジットが付く場合がある。残高は AWS コンソールの「請求とコスト管理」で確認する

## 時間外に使いたいとき
- **一時的に**: AWS コンソール、または CLI で手動で起動する（15:00 以降に起動した場合、自動では止まらないので使い終わったら手動で止める）
  ```sh
  aws ec2 start-instances --instance-ids <instance_id>
  aws rds start-db-instance --db-instance-identifier agent-rag-stg
  ```
- **しばらく常時稼働にする**（発表前など）: `envs/stg` で `enable_schedule = false` にして `terraform apply`

注意:
- RDS は起動に5〜10分かかる。RDS は停止しても7日たつと自動で起動するが、平日に毎日停止するので問題ない
- 停止中は stg にデプロイできない。また、worker の定期処理（予約配信・週次レポートなど）も動かない

## 自動デプロイ
```
main にマージ
  → GitHub Actions（.github/workflows/deploy-stg.yml）
      CI（テスト・lint・ビルド）→ 成功したら api / web のイメージを GHCR に push（タグ main と commit SHA）
  → stg の EC2（systemd の app-deploy.timer が 2 分ごと）
      deploy/stg/deploy.sh を main から取得して実行
        - SSM Parameter Store から .env を作る
        - GHCR から最新イメージを pull
        - api のイメージが変わっていたら マイグレーション と ダミー利用者の登録
        - 変わったコンテナだけ入れ替え
```
- マージからの反映は数分（Actions のビルド ＋ 最大 2 分）
- EC2 が停止中（15:00〜翌 8:45）にマージした分は、起動後の最初の実行で反映される
- 反映の様子は EC2 で `journalctl -u app-deploy -f` で見られる（Session Manager で接続）
- GHCR のイメージ（`agent-rag-api`、`agent-rag-web`）は **Public** にしておく（EC2 がログインなしで取得するため）

## 動作確認用のアカウント
`flask seed-users` でダミーの利用者（`frontend/src/mocks/db.js` と同じ人物）を登録している。パスワードは SSM の `SEED_USER_PASSWORD`。
```sh
aws ssm get-parameter --name /agent-rag/stg/SEED_USER_PASSWORD --with-decryption --query Parameter.Value --output text
```
| メールアドレス | 権限 |
|---|---|
| yamada@example.co.jp | 一般利用者 |
| sato@example.co.jp | 部署担当者（人事部） |
| admin@example.co.jp | 管理者 |

## まだ入っていないもの
- SES（メール送信）
- CloudWatch のアラームと SNS による障害通知
- 本番環境（`envs/prod`）とドメイン・HTTPS
