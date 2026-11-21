# GoVan QA and DevOps test report

**Test date:** 2026-11-01  
**Repository:** `C:\Users\Hp\Desktop\travelease\GoVan_WebBased-main`

## Executive result

The backend test suite passes and both frontend projects lint and build after dependency security updates. The API and both Vite servers started successfully in the isolated QA environment. The demo seed ran twice without duplicate records.

The application is **not feature-complete for the broader AI/demo acceptance list**: no optimization, clustering, ML ETA, smart-scheduling, GPS-simulation, or demo-reset APIs/scripts were found. Those areas are recorded as untestable/missing rather than passed. Browser interaction testing of the dashboards was not completed because desktop computer-use access to Chrome was not approved; browser-specific form behavior, console output, and responsive appearance still require manual verification.

## Environment and startup

- Runtime versions observed: Python 3.14.4, Node.js 20.19.6, npm 10.8.2.
- Backend dependencies are in `backend/requirements.txt`. `httpx` is now explicitly declared for the geocoding router; `python-multipart` now has a minimum version of 0.0.10.
- Admin frontend: React/Vite, Leaflet, React Router. PWA: React/Vite, Leaflet, React Router, `vite-plugin-pwa`.
- Both frontends read `VITE_API_URL`, defaulting to `http://localhost:8000`.
- Backend reads `DATABASE_URL`; absent it uses `backend/govan.db`. SQLite schema creation and SQLite compatibility migrations run during app import/startup; there is no Alembic migration history.
- `.env.example` documents `GOVAN_SECRET_KEY`, `GOVAN_ENV`, `GOVAN_CORS_ORIGINS`, `DATABASE_URL`, optional `ROUTING_BASE_URL`, `ROUTING_TIMEOUT_SECONDS`, and optional demo `TRAFFIC_SCENARIO`. It is not automatically loaded by the app; export values in the process environment.
- Ports 8000, 5173, and 5174 were free at initial inspection. Backend started on 8000, admin Vite on 5173, and the PWA Vite on 5174 without startup errors.
- Startup commands are listed below in **Manual browser checks**.
- `python -m pip check`: passed after upgrading `python-multipart` to 0.0.33.

## Tests executed

### Backend

- `python -m pytest tests -q`: **69 passed**, 295 warnings, 158.03 seconds.
- After the multipart environment upgrade: `python -m pytest tests/test_auth.py tests/test_password_reset.py tests/test_routing.py tests/test_route_updates.py -q`: **22 passed**, 18 warnings.
- Test coverage in the existing suite includes auth, reset tokens, role checks, organization isolation, route/vehicle/user operations, bookings, trips/locations/stops, notifications, alerts, reports, migration compatibility, routing fallback, and validation.
- API smoke tests against the running backend: `/health` returned `ok`; demo super-admin login succeeded; authenticated `/routes/` returned two seeded routes with fallback geometry; unauthenticated `/vehicles/` returned 401; a SQL-injection-shaped login identifier returned 401; both frontend origins passed the CORS check and an arbitrary origin was denied.
- Routing fallback was exercised with no configured OSRM service and with a simulated unavailable provider; both returned an explicit straight-line fallback. The active OSRM network route request was not verified because no routing endpoint was configured.
- SQLite migration compatibility test passed as part of the backend suite. QA startup used a separate disposable database, not `backend/govan.db`.

### Frontends

- `admin-web`: `npm run lint` passed; `npm run build` passed on Vite 8.3.5 and React Router 7.18.5.
- `govan-app`: `npm run lint` passed; `npm run build` passed on Vite 7.3.7 and React Router 7.18.5. PWA manifest and service worker were generated.
- After the dependency updates, both Vite servers returned HTTP 200 for their root pages. Static page titles were `TravelEase Admin` and `TravelEase`.
- Browser-driven navigation, form submission, table/filter/chart actions, live API requests from the rendered app, console errors, map rendering, and responsive layout were not visually exercised. Computer-use access to Chrome was unavailable in this run.

### Demo data

- Ran `python seed.py` twice with `DATABASE_URL` directed at `backend/qa_validation.sqlite`, a QA-only database.
- First run created 5 accounts, 2 vehicles, 2 routes, 2 bookings, and 2 maintenance records. Second run reported existing users, vehicles, and routes as skipped; database counts remained `(5, 2, 2, 2, 2)` for those entity groups.
- The seed data is not the requested complete demo: it has no organizations/tenant assignments, fleet managers, guardians, schools entity, scheduled trips, attendance, notifications, SOS events, or traffic/GPS simulation. The repo has no safe demo-reset script or explicit demo-mode marker. `seed.py` uses whichever `DATABASE_URL` is active, so do not point it at real operational data.

## Security review and changes

### Fixed during this QA run

- Removed the known, hard-coded JWT signing-key fallback. Development now uses a random process-local key (sessions are invalidated on restart); `GOVAN_ENV=production` now refuses to start without `GOVAN_SECRET_KEY`.
- Restricted default CORS to the local admin/PWA origins; configurable via `GOVAN_CORS_ORIGINS`.
- Removed password-reset bearer tokens from application logs. Added regression coverage confirming tokens are not logged and remain one-time/expiring.
- Malformed JWT `sub` values now return 401 instead of raising an integer-conversion exception.
- Added minimum 8-character password validation on admin/public account creation and geographic bounds on stop/GPS coordinates.
- Added the missing direct `httpx` dependency and corrected the multipart minimum. `pip check` now passes.
- Updated direct frontend routing dependencies to React Router 7.18.5 and patched the Vite toolchains. The prior high Vite advisory was removed: admin uses Vite 8.3.5; PWA uses patched Vite 7.3.7.

### Dependency audit

- Full `npm audit` after upgrades: admin has **10 moderate, 0 high, 0 critical** findings; PWA has **16 moderate, 3 low, 0 high, 0 critical** findings. Remaining reports are development/build-tool dependency chains (including ESLint/glob/minimatch and, in the PWA build chain, Workbox-related packages); npm's suggested `--force` remedies require major changes or downgrade direct tooling, so they were not applied blindly.
- `npm audit --omit=dev --audit-level=low`: **0 production dependency vulnerabilities** for both frontends.
- Vite 7.3.7 was selected because the live audit identified it as the compatible patch for the remaining PWA high-severity Vite advisory. [Vite security advisory](https://github.com/advisories/GHSA-67mh-4wv8-2f99). React Router was upgraded past the affected range in the router advisories. [React Router advisory 1](https://github.com/advisories/GHSA-wrjc-x8rr-h8h6) [React Router advisory 2](https://github.com/advisories/GHSA-337j-9hxr-rhxg).

### Findings not fully resolved

- **Rate limiting:** no login, password-reset, geocoding, or general API rate limiter exists. Add a shared production-ready limiter (e.g. Redis-backed) before public deployment; a per-process counter is not sufficient for multiple workers.
- **Password-reset delivery:** token handling is hashed, expiring, and one-time, and no longer leaks via logs. However, the backend has no configured email/SMS delivery provider, so users cannot receive reset links end-to-end. Configure a provider and test delivery before claiming password recovery works.
- **Known demo credentials:** `backend/seed.py` contains and prints a shared demo password. Keep those accounts/data in an isolated demo database and change/remove credentials in any deployed environment.
- **CORS allowlist:** production must set exact trusted origins; the example values are for local development.
- **SQL injection:** tested a malformed login identifier and reviewed ORM query construction; this is not a substitute for a broader dynamic/API fuzz test.
- **XSS:** React escapes rendered strings by default; no `dangerouslySetInnerHTML`/raw `innerHTML` sink was found in app source. No full browser payload test was run.
- **Production operations:** no rate limiting, HTTPS/deployment validation, backup/restore test, or multi-worker database test was performed. SQLite compatibility migration is implemented; production schema migration management remains missing.

## Feature areas requested but absent or not verifiable

| Area | QA result |
|---|---|
| Authentication / invalid / expired token | Tested; covered in passing suite and smoke checks |
| Platform admin and tenant access | Tested at API level; cross-tenant tests pass |
| Vehicles, drivers, passengers, routes/stops | Core APIs and tests exist; route stop CRUD is nested under route operations |
| Schedules | Route pickup/drop times and days exist; there is no separate schedule API/model or conflict solver |
| Trips, GPS updates, notifications, SOS | Core API paths and regression tests exist |
| Route optimization API | No endpoint or solver found |
| Passenger clustering API | No endpoint or clustering implementation found |
| Smart scheduling | No optimization/constraint engine found |
| ML ETA/model loading | No trained model or inference API found; current ETA uses routing/fallback duration |
| Demo GPS movement/status progression | No simulator found |
| Demo reset/data isolation | No reset command or explicit demo-mode boundary found |
| Real road routing | OSRM adapter/fallback exist; only fallback tested. No OSRM endpoint configured during smoke run |
| Map display/markers/polylines | Components and route geometry mapping exist; visual browser check not completed |

## Manual browser checks

From the repository root, use three terminals:

```powershell
# Terminal 1: backend
cd backend
python -m pip install -r requirements.txt
$env:GOVAN_ENV = "development"
$env:GOVAN_SECRET_KEY = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
$env:GOVAN_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
python -m uvicorn app.main:app --reload
```

```powershell
# Terminal 2: admin website
cd admin-web
npm ci
npm run dev
```

```powershell
# Terminal 3: driver/passenger PWA
cd govan-app
npm ci
npm run dev
```

Open `http://localhost:5173` for admin and `http://localhost:5174` for the PWA. If you need demo records, point `DATABASE_URL` at a disposable SQLite file first, then run `python seed.py` from `backend/`. The seed creates `admin@govan.dev`, `dave@govan.dev`, `sana@govan.dev`, `pat@govan.dev`, and `ali@govan.dev`, all with the printed demo password. Do not run it against real fleet data.

Check in the browser:

1. Sign in as platform admin; verify organization, user, vehicle, route, report, and audit pages load and platform actions work.
2. Create two organizations and organization-scoped manager accounts; sign in as each and attempt to access the other tenant's records through UI links and direct API IDs.
3. Exercise vehicle, driver assignment, passenger/guardian link, route/ordered stop, booking capacity, trip schedule/start/end, GPS updates, notification read, and SOS flows.
4. Use the browser Network and Console panels to verify API origins, response statuses, and absence of client errors. Check the denied-CORS case from a non-allowlisted origin.
5. Resize desktop/tablet/mobile widths. Check tables/forms/navigation, map visibility, and no horizontal overflow.
6. For road routing, set `ROUTING_BASE_URL` to a reachable OSRM-compatible endpoint and restart the API. Confirm the route source is `osrm`, the polyline follows roads, and distance/duration change. With the setting empty/unavailable, confirm the UI/API clearly shows fallback estimates.
7. Set `TRAFFIC_SCENARIO=low`, `moderate`, then `heavy`; restart the backend and confirm the ETA multiplier changes while the scenario remains identified as simulated.

## Issues for the next engineering pass

1. Add production-grade rate limiting and a real reset-link delivery provider.
2. Complete the explicit demo mode and safe reset, with seeded tenant relationships, guardian/manager accounts, trips, alerts, and a labeled GPS simulator.
3. Implement (or remove from acceptance criteria) clustering, capacity/time-window optimization, conflict-free smart scheduling, and an experimentally trained ETA model with measured baseline metrics.
4. Add route deviation and stale-GPS alerts, then run those tests against simulated tracks.
5. Resolve remaining development dependency advisories without destabilizing build tooling; rerun `npm audit`, lint, and build after upgrades.
6. Complete browser-based role, form, map, responsiveness, and console/network checks.
