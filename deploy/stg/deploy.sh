#!/bin/bash
# stg の EC2 で 2 分ごとに実行される（systemd の app-deploy.timer）。
# GHCR から main の最新イメージを取得し、変わっていればコンテナを入れ替える。
# このファイル自体も毎回 main から取得するので、変更は main にマージした数分後に反映される。
#
# 環境変数（systemd の app-deploy.service で設定）:
#   AWS_REGION  SSM Parameter Store のリージョン
#   SSM_PREFIX  アプリの設定値のパス（例: /agent-rag/stg）
set -euo pipefail

REPO_RAW="https://raw.githubusercontent.com/Graduation-Project-2026-11-09/agent-rag-system/main"
API_IMAGE="ghcr.io/graduation-project-2026-11-09/agent-rag-api:main"
APP_DIR=/opt/app
MIGRATED_MARKER="$APP_DIR/.migrated-image-id"

cd "$APP_DIR"

curl -fsSL "$REPO_RAW/deploy/stg/compose.yml" -o compose.yml

# 設定値は SSM Parameter Store から取得して .env に書き出す（Git には置かない）
tmp=$(mktemp)
aws ssm get-parameters-by-path --region "$AWS_REGION" --path "$SSM_PREFIX" --with-decryption \
  --query 'Parameters[].[Name,Value]' --output text \
  | while IFS=$'\t' read -r name value; do printf '%s=%s\n' "${name##*/}" "$value"; done > "$tmp"
install -m 600 "$tmp" .env
rm -f "$tmp"

docker compose pull --quiet

# マイグレーションは api のイメージが変わったときだけ実行する。
# 起動直後で RDS がまだ準備中なら失敗するので、成功したときだけ記録して次回やり直す
api_image_id=$(docker image inspect --format '{{.Id}}' "$API_IMAGE")
if [ "$(cat "$MIGRATED_MARKER" 2>/dev/null)" != "$api_image_id" ]; then
  echo "[deploy] running migrations for $api_image_id"
  # ダミーの利用者も登録する（登録済みなら何もしない。パスワードは SSM の SEED_USER_PASSWORD）
  docker compose run --rm --no-deps api sh -c 'flask --app app db upgrade && flask --app app seed-users'
  echo "$api_image_id" > "$MIGRATED_MARKER"
fi

# イメージや設定（.env・compose.yml）が変わったコンテナだけ作り直される
docker compose up -d --remove-orphans
docker image prune -f > /dev/null
