# content-curator UI

A minimal web interface for the content curator API — search by reader
profile, view ranked results with fit explanations, discover and add new
content to the index (either by pasting URLs directly, or by searching a
topic to find candidates first).

## Architecture

This is a Next.js app with a specific security-motivated design: the
browser never holds the backend's API key. Instead:

```
Browser --> Next.js API routes (server-side) --> FastAPI backend
            (holds CURATOR_API_KEY here,
             never sent to the browser)
```

`app/api/recommend/route.js` and `app/api/ingest/route.js` are server-side
proxies — they read `CURATOR_API_KEY` from a server-only environment
variable, attach it to the outgoing request, and forward to the FastAPI
backend. The browser only ever talks to this app's own `/api/*` routes.

## Setup

```bash
npm install
cp .env.local.example .env.local
```

Edit `.env.local`:
- `BACKEND_URL` — where your FastAPI backend is running (default assumes
  `http://localhost:8000`, i.e. running locally per the main project's
  `DEV_SETUP.md`)
- `CURATOR_API_KEY` — the same value from the backend's own `.env` file

## Run locally

Make sure the FastAPI backend is already running (see the main project's
`DEV_SETUP.md`), then:

```bash
npm run dev
```

Open `http://localhost:3000`.

## Deploying

This frontend can be deployed independently of the backend (e.g. to
Vercel), but **the backend must be reachable from wherever this is
deployed** — a backend running on `localhost` on your laptop is not
reachable from a Vercel deployment, since `localhost` only means "this
same machine." Setting `BACKEND_URL` to a public URL only works once the
backend is actually hosted somewhere reachable at that URL — deploying
this frontend alone doesn't solve that; the backend needs its own real
hosting first (see the main project's `TODO.md`/`DESIGN.md` for the
options considered for that).

When deploying, set `BACKEND_URL` and `CURATOR_API_KEY` as environment
variables in your hosting platform's dashboard (not in a committed file).

## Design tokens

Colors, fonts, and spacing are defined as CSS custom properties in
`app/globals.css`. The palette intentionally matches the project logo
(`../assets/logo.svg`) — same amber accent, same dark navy base — so the
brand is consistent from logo to product.
