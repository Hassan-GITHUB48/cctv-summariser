# Web dashboard

React + Vite + TypeScript + Tailwind front end for the CCTV Incident Summariser API.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api to http://localhost:8000
npm run build    # type-check + production build
npm run lint     # oxlint
npm test         # vitest (pure helpers: formatting, timeline, markdown export)
```

Set `VITE_API_TARGET` to point the dev proxy at a different backend.
