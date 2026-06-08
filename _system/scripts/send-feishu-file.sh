#!/bin/bash
# send-feishu-file.sh <file_path> <file_name>

FILE_PATH="$1"
FILE_NAME="$2"

if [ -z "$FILE_PATH" ] || [ -z "$FILE_NAME" ] || [ ! -f "$FILE_PATH" ]; then
  echo "Usage: $0 <file_path> <file_name>"
  exit 1
fi

APP_ID="cli_aa883a5a0b791bef"
APP_SECRET="ATc6R9oHtN0NUdCzaiPHEcUrs66fIX6x"
USER_ID="ou_2ba3d8bedd4e2cb6bcfddf0e273d1bd6"

# Get token
curl -s -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json" \
  -d "{\"app_id\":\"$APP_ID\",\"app_secret\":\"$APP_SECRET\"}" > /tmp/feishu_token.json

TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/feishu_token.json')).get('tenant_access_token',''))")

if [ -z "$TOKEN" ] || [ "$TOKEN" = "None" ]; then
  echo "FAIL get_token"
  exit 1
fi

# Upload file
curl -s -X POST "https://open.feishu.cn/open-apis/im/v1/files" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file_type=stream" \
  -F "file_name=$FILE_NAME" \
  -F "file=@$FILE_PATH" > /tmp/feishu_upload.json

FILE_KEY=$(python3 -c "import json; d=json.load(open('/tmp/feishu_upload.json')); print(d.get('data',{}).get('file_key',''))")

if [ -z "$FILE_KEY" ] || [ "$FILE_KEY" = "None" ]; then
  echo "FAIL upload"
  cat /tmp/feishu_upload.json
  exit 1
fi

# Send
curl -s -X POST "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"receive_id\":\"$USER_ID\",\"msg_type\":\"file\",\"content\":\"{\\\"file_key\\\":\\\"$FILE_KEY\\\"}\"}" > /tmp/feishu_send.json

python3 -c "import json; d=json.load(open('/tmp/feishu_send.json')); print('OK' if d.get('code')==0 else 'FAIL: '+d.get('msg',''))"
