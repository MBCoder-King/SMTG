python3 backend/app.py
# Social Media Time Guard (SMTG)

A working, deployable web MVP for reducing endless social scrolling with calm UX, analytics, and privacy-first defaults.

## Is user-behavior analysis working?

Yes (current MVP level). The app analyzes behavioral metadata using rules-based logic:
- scroll-heavy ratio,
- late-night usage,
- nudge acceptance,
- productive vs non-productive sessions,
- risk classification + recommendations.

Endpoint: `GET /api/behavior/analyze`.

## Is Instagram / Facebook / YouTube Shorts integrable?

Yes, but currently as **policy-safe partial integration** (not direct feed-level analysis):
- Uses OS app-usage signals and session heuristics.
- No social-media content scraping.
- No direct private feed access.

Endpoint: `GET /api/integrations`.

## Phase Progress

- **Phase 1 (MVP Build): Complete** for this web implementation.
- **Phase 2 (ML + Personalization): Partially complete** (rules-based personalization done, full ML training pipeline pending).

See: `docs/phase-status.md`.

## Final Project Structure (copy/paste reference)

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
