# Khetix Backend (FastAPI)

FastAPI server that queues **cutter** and **servo** commands for the ESP8266 (`carv2.ino`). Drive commands (`F`/`B`/`L`/`R`/`S`) stay on Arduino + Bluetooth via the KhetiX Flutter app.

## Stack

- **FastAPI** — HTTP API
- **Upstash Redis / Vercel KV** — command queue + device state
- **Vercel** — deployment target (native FastAPI support)

## Project layout

```
backend/
  main.py           # FastAPI routes
  store.py          # Redis helpers
  requirements.txt
  vercel.json
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `API_KEY` | Shared secret for Flutter app + ESP8266 (`x-api-key` header) |
| `KV_REST_API_URL` | Auto-set when Vercel KV is linked |
| `KV_REST_API_TOKEN` | Auto-set when Vercel KV is linked |

## API

### `POST /api/command`

Send a command from the Flutter app.

```bash
curl -X POST https://car-v5lm.vercel.app/api/command \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_KEY" \
  -d '{"deviceId":"khetix-001","cmd":"1"}'
```

Servo:

```bash
curl -X POST https://car-v5lm.vercel.app/api/command \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_KEY" \
  -d '{"deviceId":"khetix-001","cmd":"servo","angle":90}'
```

Commands: `1` (cutter on), `2` (cutter off), `servo` (with `angle` 0–180).

### `GET /api/poll?deviceId=khetix-001`

ESP8266 polls every ~300 ms. Returns pending command once, then clears it.

```bash
curl "https://car-v5lm.vercel.app/api/poll?deviceId=khetix-001" \
  -H "x-api-key: YOUR_KEY"
```

Responses:

- `{ "cmd": null }` — nothing pending
- `{ "cmd": "1" }` or `{ "cmd": "2" }`
- `{ "cmd": "servo", "angle": 90 }`

### `GET /api/status?deviceId=khetix-001`

Optional UI sync for the Flutter app.

```bash
curl "https://car-v5lm.vercel.app/api/status?deviceId=khetix-001" \
  -H "x-api-key: YOUR_KEY"
```

## Local development

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt

# Set env vars (use your Upstash/Vercel KV credentials)
set API_KEY=your-dev-key
set KV_REST_API_URL=https://...
set KV_REST_API_TOKEN=...

uvicorn main:app --reload --port 8000
```

Open `http://127.0.0.1:8000/docs` for Swagger UI.

## Deploy to Vercel

1. Install Vercel CLI: `npm i -g vercel`
2. From `backend/`:

   ```bash
   vercel
   ```

3. In the Vercel dashboard for this project:
   - **Storage → Create → KV** (links `KV_REST_API_URL` + `KV_REST_API_TOKEN`)
   - **Settings → Environment Variables** → add `API_KEY`
4. Redeploy: `vercel --prod`
5. Copy the production URL into:
   - `iot/carv2.ino` → `API_BASE`
   - Flutter build defines (see below)

Vercel auto-detects `main.py` as a FastAPI app when `fastapi` is in `requirements.txt`.

## Flutter app config

Build with dart-defines (do not hardcode secrets in source for production):

```bash
flutter run \
  --dart-define=KHETIX_API_BASE=https://car-v5lm.vercel.app \
  --dart-define=KHETIX_DEVICE_ID=khetix-001 \
  --dart-define=KHETIX_API_KEY=YOUR_KEY
```

## ESP8266 config

Edit the top of `iot/carv2.ino`:

- `WIFI_SSID`, `WIFI_PASS`
- `API_BASE` — your Vercel URL
- `DEVICE_ID` — must match Flutter (`khetix-001`)
- `API_KEY` — same as Vercel `API_KEY`

## End-to-end test

1. Deploy backend; run the `curl` commands above
2. Flash `carv2.ino`; confirm Serial shows WiFi + poll activity
3. Open KhetiX → connect Bluetooth to Arduino
4. Toggle cutter / move servo → ESP8266 responds
5. Joystick → Arduino motors respond via Bluetooth only
