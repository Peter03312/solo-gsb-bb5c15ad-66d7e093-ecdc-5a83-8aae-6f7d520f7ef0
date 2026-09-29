#!/usr/bin/env bash
# End-to-end demo against a running service (default http://localhost:8000).
set -euo pipefail

BASE="${BASE_URL:-http://localhost:8000}"
SECRET="${WEBHOOK_SECRET:-dev-webhook-secret}"

send_event() {
  python3 - "$BASE" "$SECRET" "$1" <<'PY'
import hashlib, hmac, json, sys, time, urllib.request

base, secret, event_json = sys.argv[1], sys.argv[2], sys.argv[3]
body = event_json.encode()
ts = str(int(time.time()))
sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
req = urllib.request.Request(
    f"{base}/webhooks/events", data=body,
    headers={"X-Webhook-Timestamp": ts, "X-Webhook-Signature": f"sha256={sig}",
             "Content-Type": "application/json"})
print(urllib.request.urlopen(req).read().decode())
PY
}

echo "==> income evt-1 (+100.00 USD)"
send_event '{"event_id":"evt-1","account_id":"acct-demo","type":"income","amount":"100.00","currency":"USD","occurred_at":"2026-09-20T10:00:00Z"}'

echo "==> refund evt-2 (-30.00 USD, out of order: occurred earlier)"
send_event '{"event_id":"evt-2","account_id":"acct-demo","type":"refund","amount":"30.00","currency":"USD","occurred_at":"2026-09-20T09:00:00Z","reference_event_id":"evt-1"}'

echo "==> duplicate evt-1 (idempotent)"
send_event '{"event_id":"evt-1","account_id":"acct-demo","type":"income","amount":"100.00","currency":"USD","occurred_at":"2026-09-20T10:00:00Z"}'

echo "==> balance"
curl -s "$BASE/accounts/acct-demo/balance"; echo

echo "==> reconcile window"
curl -s -X POST "$BASE/reconcile" -H 'Content-Type: application/json' -d '{
  "account_id": "acct-demo",
  "start": "2026-09-20T00:00:00Z",
  "end": "2026-09-20T23:59:59Z",
  "expected_balance": {"USD": "70.00"},
  "expected_events": [
    {"event_id": "evt-1", "type": "income", "amount": "100.00"},
    {"event_id": "evt-2", "type": "refund", "amount": "30.00"}
  ]
}'; echo

echo "==> funding gaps (negative-balance periods)"
# Refund 120 at 11:00 (balance -120); income 100 at 12:00 (balance -20,
# still a gap); income 30 at 13:00 (balance +10, recovered).
send_event '{"event_id":"gap-r1","account_id":"acct-gap","type":"refund","amount":"120.00","currency":"USD","occurred_at":"2026-09-21T11:00:00Z"}'
send_event '{"event_id":"gap-i1","account_id":"acct-gap","type":"income","amount":"100.00","currency":"USD","occurred_at":"2026-09-21T12:00:00Z"}'
send_event '{"event_id":"gap-i2","account_id":"acct-gap","type":"income","amount":"30.00","currency":"USD","occurred_at":"2026-09-21T13:00:00Z"}'

curl -s -G "$BASE/accounts/acct-gap/negative-balances" \
  --data-urlencode "currency=USD" \
  --data-urlencode "start=2026-09-21T00:00:00Z" \
  --data-urlencode "end=2026-09-22T00:00:00Z"; echo
