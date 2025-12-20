# Duck Demo UI

Minimal React + Vite + Tailwind UI for the demo data served at `/api`.

## Run

```bash
npm install
npm run dev -- --host --port 5173
```

Optional: set `VITE_API_BASE` to point to the backend if it is on a different origin (defaults to `/api`).

## Pages

- Customers (list)
- Items/stock (stock summaries)
- Sales orders (list + detail with lines/pricing/shipments)
- Shipments and production detail panels

Currently read-only; can add POST/PUT later by calling the existing helpers behind `/api`.
