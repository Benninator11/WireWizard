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


## 3D rack visualization
- Rack equipment is shown with individual chassis depth, front details and status indicators.
- The rear view renders rounded 3D cable bodies and connector housings in the cabinet scene.
- Cable path length is shown as an estimate including connector and slack allowance.
- The power overview includes an estimated current at 230 V; it is not a live electrical measurement.
