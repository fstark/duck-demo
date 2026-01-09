# How to install the duck demo

## Backend

create a python virtual enironment by:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Populate the database with demo data by running:

```bash
python seed_demo.py
```

Run the server using:

```bash
HOST=127.0.0.1 PORT=8000 ./venv/bin/python server.py
```

This will run the MCP server and the UI api server on ``http://127.0.0.1:8000``

## Frontend

go to the ui directory and issue:

```bash
cd ui
npm install
```

Run the dev UI server with:

```bash
npm run dev -- --host --port 5173
```

If you connect to ``http://localhost:5173/`` you should see the demo UI.

## Exposing via ngrok

Install ngrok (mac):

```bash
brew install ngrok/ngrok/ngrok
```

Add your token with:

```bash
ngrok config add-authtoken <your_token>
```

Create a tunnel with:

```bash
ngrok http 8000
```
This will give you a public URL that you can use to access the demo from anywhere.

### API_BASE Configuration

When using ngrok or other tunnels, you may need to set the `API_BASE` environment variable so that image URLs in MCP responses use absolute URLs instead of relative paths:

```bash
export API_BASE=https://your-backend-tunnel.ngrok.io
```

For local development (default):
- `API_BASE=http://127.0.0.1:5173` (automatically set if not specified, uses Vite proxy)

For ngrok tunnels:
- Set `API_BASE` to your backend's public ngrok URL before starting the server
- This ensures MCP tool responses contain absolute image URLs that work across different domains
