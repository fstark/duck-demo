# WTF — Known Gotchas

## Dashboard shows fewer records than expected

The web UI dashboards fetch data from REST APIs that apply a default `limit` to queries. If you import or create records and don't see them in the UI, it's likely pagination — not a bug.

- **Customers API** (`/api/customers`): default limit = 100
- The actual database may contain more records than the dashboard displays

To verify, query the API with a higher limit: `?limit=500` or check the DB directly.
