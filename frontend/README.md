# Frontend (QuickDash)

QuickDash pure-HTML / Vanilla JS frontend.

## Quick development

1. Install dev deps:
   ```bash
   cd frontend
   npm install
   ```

2. Start a static HTTP server (recommended):
   ```bash
   npm start
   # open http://localhost:8080
   ```

Notes:
- Do NOT open HTML files via `file://` as `fetch()` and some libraries will fail. Use the server above.
- If you don't have backend running, create or edit `config.local.json` and add a valid `keys.google_maps` if you want maps to work locally.
- The project uses `<base href="/">` by default; adjust if serving from a subpath.

Integration tests (Playwright)

Requirements:
- Node.js (14+)
- npm

Install dev dependencies in `frontend/`:

  cd frontend
  npm install

Run the integration test (it will start the local static server automatically):

  npm run test:integration

The test 'navbar location click opens LocationPicker' verifies that clicking the navbar location injects/opens the location picker modal and that no delivery address is auto-saved by the click.
