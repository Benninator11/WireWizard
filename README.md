# WireWizard & ServerWizard

## Start
Open `index.html` via a local web server or GitHub Pages. The start page routes to `#server` and `#wire`; hardware data is requested only when ServerWizard opens.

## Files
- `index.html` – launcher and URL-hash routing
- `server.html` – ServerWizard
- `wire.html` – WireWizard
- `hardware-data.json` – CPU/GPU lists, lazy-loaded by launcher
- `manifest.json`, `sw.js` – PWA metadata and offline cache

## Install as PWA
Serve the project over HTTPS (for example GitHub Pages), then use the browser's Add to Home Screen option. Service workers do not run from `file://`.

## Project backup
Each planner includes JSON export/import controls. Existing automatic browser storage remains in place.
