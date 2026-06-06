# Khetix Backend (FastAPI)

FastAPI server that queues **cutter** and **servo** commands for the ESP8266 (`carv2.ino`). Drive commands (`F`/`B`/`L`/`R`/`S`) stay on Arduino + Bluetooth via the KhetiX Flutter app.

## Environment variables

| Variable | Description |
|----------|-------------|
| `KV_REST_API_URL` | Auto-set when Vercel KV is linked |
| `KV_REST_API_TOKEN` | Auto-set when Vercel KV is linked |

## API

### `POST /api/command`

```bash
curl -X POST https://car-v5lm.vercel.app/api/command \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"khetix-001","cmd":"1"}'
```

### `GET /api/poll?deviceId=khetix-001`

```bash
curl "https://car-v5lm.vercel.app/api/poll?deviceId=khetix-001"
```

### `GET /api/status?deviceId=khetix-001`

```bash
curl "https://car-v5lm.vercel.app/api/status?deviceId=khetix-001"
```

## Deploy

1. From `backend/`: link Vercel KV storage, then `vercel --prod`
2. Redeploy after code changes so auth removal takes effect
