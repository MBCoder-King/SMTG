# SMTG Final Architecture (Web MVP)

## 1) Runtime Layout

- **Backend API server**: `backend/app.py` (Python stdlib HTTP server).
- **Database**: SQLite (`backend/smtg.db`).
- **Frontend client**: static PWA (`web/`) served by backend.
- **Container deploy**: `Dockerfile`.

## 2) Folder Structure

```text
SMTG/
├── backend/
│   ├── app.py
│   └── smtg.db
├── web/
│   ├── index.html
│   ├── styles.css
│   ├── script.js
│   ├── manifest.webmanifest
│   └── sw.js
├── docs/
│   ├── architecture.md
│   ├── phase-status.md
│   └── ui-ux-spec.md
├── design/
│   └── design-tokens.json
├── Dockerfile
├── README.md
└── .gitignore
