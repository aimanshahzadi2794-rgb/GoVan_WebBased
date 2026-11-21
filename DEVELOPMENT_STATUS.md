# GoVan development status

**Updated:** 2026-11-01  
**Baseline:** `Smart_Fleet_Coordination_System_v2.docx` plus the implementation-continuation request in the attached text file.

## Current state

GoVan is a working web MVP with a React admin portal, a React progressive web app, a FastAPI backend, and SQLite persistence. The current implementation is materially short of the full Version 2.0 requirement document and the AI/demo continuation request. This status is evidence-based: a passing backend suite confirms tested API behavior, not untested product requirements.

### Implemented or substantially present

- Role-aware accounts for legacy `admin`, `super_admin`, `organization_admin`, `fleet_manager`, driver, passenger, and guardian. First-user bootstrap supports a platform super admin.
- Organization records can be activated or suspended by platform admins; login for a suspended tenant is blocked.
- Backend tenant scoping and direct-ID authorization checks have been added across organization, user, vehicle, driver, route, booking, trip, maintenance, alert, report, guardian, and audit endpoints. New tests exercise cross-tenant reads/writes, public tenant assignment, suspended tenants, and audit/report isolation.
- Fleet managers and organization admins can use the admin portal with role-sensitive navigation and user creation. Platform administrators can manage organizations and see audit logs.
- Vehicle, driver, route, booking, trip lifecycle, location history, notifications, SOS, maintenance, reports, guardian links, and route-stop events have existing API/UI support to varying degrees.
- Route responses now support an OSRM-compatible road-routing adapter, including GeoJSON route geometry, road distance and duration. `ROUTING_BASE_URL` configures an endpoint; when omitted or unavailable, the API returns a straight-line estimate with an explicit source label.
- The fleet trip map draws assigned route geometry and stops alongside active vehicle locations. Route lines distinguish road routes from fallback estimates in their label.
- Optional `TRAFFIC_SCENARIO=low|moderate|heavy` applies documented demo multipliers and returns the selected scenario. The feature does not claim these values model actual Lahore traffic.
- Backend configuration example added at `backend/.env.example`.

### Still missing or incomplete against the requirements

| Requirement | Current status | Remaining work |
|---|---|---|
| Super Admin / tenant isolation | Implemented in API and partially in UI; backend tests pass | Review every new endpoint as one is added; move from ad-hoc schema additions to managed migrations; stronger permission distinction between organization admins and fleet managers |
| Internal vs external fleet relationships | Vehicle has `ownership_type` and one organization FK | No FleetCompany/VehicleAssignment/contract model; external vehicle sharing across client organizations is unsupported |
| Org Admin vs Fleet Manager responsibilities | Both map to manager behavior in several endpoints | Enforce separate role policies; Fleet Manager should manage provider fleet while Organization Admin manages client routes/passengers/contracts |
| Road routing and maps | Configurable OSRM adapter and route geometry in API; map draws active routes | Configure a service for demos/deployment, persist/cache route results durably, improve route editing preview, show GPS source/staleness, and verify real server responses in the target network |
| ETA and traffic | Route-list ETA uses OSRM duration when configured; passenger ETA from the latest vehicle location to the booked boarding stop also uses the routing adapter; fixed-speed fallback and optional synthetic multipliers are labeled | No reliable free Lahore traffic feed has been established; traffic multipliers are illustrative only; request-volume/latency behavior should be validated against the chosen routing host |
| GPS tracking and route verification | Trip location updates and path history exist; stop arrivals/dwell events exist | No GPS signal-loss/stale alert, no route-deviation alert, no geofence tuning, no outbound/return route validation, no clear real-vs-simulated data marker |
| ML ETA | Not implemented | Create reproducible synthetic trip data, train/evaluate a regressor against a naive baseline, report actual MAE/RMSE, persist model/version and allow later retraining from real trip history |
| Passenger clustering | Not implemented | Cluster actual geocoded passenger locations using Haversine-aware algorithms, capacity/destination constraints, and explain cluster assignments |
| Route optimization / smart scheduling | Not implemented | OR-Tools capacity/time-window solver, driver/vehicle shift availability, schedule conflict constraints, baseline comparison, explainable objective and feasibility output |
| Demo mode and seed data | `backend/seed.py` exists but does not provide the requested complete isolated demonstration | Reproducible Lahore demo organizations/fleets/users/schools/stops/trips/attendance/alerts/maintenance; explicit synthetic-data labeling; dashboard stats verified against seed records; route-following GPS and status/ETA simulation |
| Mobile application | `govan-app` is React/Vite PWA | Requirement document specifies Flutter; no Flutter app is present. Decide whether the PWA is an approved FYP substitute or plan Flutter port |
| Identity, database, notifications | FastAPI JWT/custom auth, SQLite default, in-app notifications | Requirement document names Firebase Auth/Firestore/FCM. Current stack differs; either document and defend the substitution or implement provider adapters. Current push notifications are not FCM delivery |
| Billing/payments | Not implemented | Medium priority in SRS; choose payment gateway only after a secure hosted checkout design. RFID, rentals and ride sharing are explicitly future scope |
| Operations analytics | Basic reports exist | Fleet utilization, route efficiency comparisons, delay prediction, client-org rollups, admin filtering and richer dashboard metrics |
| Security/deployment | Password hashing, JWT, backend tenant checks | HTTPS deployment, rate limiting, audit retention, production DB, migrations, secrets management, backups, load/performance checks, security review |

## Work completed in this implementation continuation

1. Added tenant boundary helpers and applied them across the identified organization-owned API surfaces; added organization suspension and activity logging.
2. Added audit log endpoint and role-aware admin portal support.
3. Added explicit cross-organization API tests and corrected a test that used `POST` for a `PATCH` endpoint.
4. Added an OSRM-compatible route provider with a safe fallback, returned route geometry/road duration/source in route data, displayed active routes and stops, and introduced explicitly labeled demo traffic multipliers.

## Test and build evidence

- `python -m pytest tests -q` (backend): **62 passed**, 291 deprecation warnings, 124.94 seconds. The suite completed before the newest routing unit tests were added, so those are also run separately.
- `python -m pytest tests/test_tenant_access.py -q`: **3 passed**.
- After the routing/ETA changes: `python -m pytest tests/test_routing.py tests/test_passenger_live_tracking.py tests/test_tenant_access.py -q`: **8 passed**.
- `npm run lint` in `admin-web`: could not start because the local npm dependencies are not installed (`eslint` command not found). No dependency installation was attempted.
- Frontend production build remains unverified for the same missing local dependencies.

## Recommended next milestones (3–4 week student schedule)

1. **Finish routing and monitoring (2–3 days):** run routing against a chosen OSRM-compatible endpoint; persist/cache results; add route editor previews; add GPS freshness and route-deviation alerts with thresholds; test actual API payloads.
2. **Reproducible demo environment (2–3 days):** resettable seed dataset, synthetic-data banner, deterministic trip/GPS simulator, edge cases, and dashboard data reconciliation.
3. **ETA prototype (2–3 days):** synthetic dataset generator, train/test split, naive baseline and RandomForest/GradientBoosting evaluation, record real MAE/RMSE, model metadata and inference adapter. Current ETA is routing-based, not ML-predicted.
4. **Optimization + clustering (4–6 days):** OR-Tools VRP with vehicle capacity/time windows and feasibility explanations; geospatial passenger clustering with destination/capacity constraints; compare against a simple baseline.
5. **Role distinction + fleet contracts (3–5 days):** separate fleet-company and client-organization ownership/assignments; prohibit inappropriate cross-tenant mutations; contract approval model.
6. **Final integration and delivery (3–5 days):** UI for optimization/ETA/alerts, automated regression and authorization tests, clean demo run, architecture/ER/use-case/sequence diagrams and deployment guide.

Billing/payments should be prioritized only after the core operational demo is stable. RFID, rentals, and ride sharing are explicitly marked future/out of scope in Version 2.0.

## Technology notes and sources checked

- OSRM provides route distance, duration and GeoJSON geometry. The public demo server is best-effort and unsuitable as a production SLA; use a configured/self-hosted compatible service for a dependable demo: [OSRM API](https://project-osrm.org/docs/v5.6.4/api/), [OSRM usage policy](https://github-wiki-see.page/m/Project-OSRM/osrm-backend/wiki/Api-usage-policy).
- OpenStreetMap public tiles require attribution and policy-compliant caching; do not bulk download/prefetch tiles: [OSMF tile usage policy](https://operations.osmfoundation.org/policies/tiles/).
- Public Nominatim has a strict usage policy including an identifying User-Agent and a maximum of one request per second; keep provider switching and caching: [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/).
- OR-Tools is a practical open-source option for capacity and time-window routing constraints: [Google OR-Tools routing documentation](https://developers.google.com/optimization/routing?hl=en).
- Scikit-learn offers standard regression and clustering methods suitable for an experimental locally trained baseline: [scikit-learn user guide](https://scikit-learn.org/stable/).
- SUMO is a candidate open traffic simulator, but any scenario generated from it must be labeled simulated and must not be presented as observed Lahore traffic: [SUMO documentation](https://eclipse.dev/sumo/docs/).
- Google Routes is an optional paid upgrade, not a free dependency. Verify live SKU pricing and billing requirements before enabling it: [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing), [Routes API usage and billing](https://developers.google.com/maps/documentation/routes/usage-and-billing).
