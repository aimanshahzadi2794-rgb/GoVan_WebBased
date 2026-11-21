# GoVan Lahore Demo Fleet

This is an isolated, explicitly named demo organization that uses GoVan's existing users, organizations, vehicles, routes, stops, bookings, trips, locations, notifications, and stop-event models. It does not clear the database or modify other organizations.

## Setup

From the repository root, install backend and frontend dependencies if needed:

```powershell
cd backend
python -m pip install -r requirements.txt
cd ..\admin-web
npm install
```

Configure optional road routing before starting the backend. GoVan calls an OSRM-compatible endpoint when configured and otherwise labels route metrics as straight-line estimates:

```powershell
cd ..\backend
$env:ROUTING_BASE_URL = "https://router.project-osrm.org"
python -m uvicorn app.main:app --reload
```

The public OSRM demo server is a best-effort shared service. It may rate-limit, time out, or change availability. For reliable repeated demonstrations, run a local OSRM instance or use another OSRM-compatible service. Do not present the traffic multiplier as live traffic data.

In a second terminal:

```powershell
cd admin-web
$env:VITE_API_URL = "http://localhost:8000"
npm run dev
```

Open `http://localhost:5173` and sign in as an existing platform administrator.

## Initialize and log in

1. Open **Demo Control Center** in the Admin Portal.
2. Select **Initialize Lahore demo dataset**. This action is restricted to a platform administrator and is idempotent.
3. Sign out and log in as the demo Fleet Manager.

All demo accounts use the test-only password `GoVanDemo2026!`:

| Role | Email |
|---|---|
| Fleet Manager | `fleet.manager@demo-govan.com` |
| Driver 1–3 | `driver1@demo-govan.com` through `driver3@demo-govan.com` |
| Student 1–30 | `user1@demo-govan.com` through `user30@demo-govan.com` |
| Guardian 1–10 | `guardian1@demo-govan.com` through `guardian10@demo-govan.com` |

These are fictional accounts for local demonstrations only. Change or remove them before exposing a demo server outside a trusted environment.

## Demo controls

- **Initialize / verify dataset** checks that the named demo organization is present.
- **Start GPS** begins simulated movement for the seeded active trip. While the Fleet Manager Demo Control Center is open, the browser calls the tick endpoint every three seconds. Pause/resume/stop affect this simulator; stop does not delete trips.
- Vehicle coordinates move along the route geometry returned by configured OSRM. When OSRM is unavailable, GoVan returns a clearly labeled straight-line fallback geometry; movement then follows that fallback.
- **Run passenger clustering** executes deterministic K-means on the seeded pickup coordinates.
- **Compare / optimize routes** compares the seeded order with a nearest-neighbor stop ordering per already-assigned vehicle and computes distance/duration through GoVan's routing service. It preserves each assignment and checks capacity; it does not perform a global vehicle reassignment or OR-Tools solve.
- **Run smart scheduling** reports shared driver/vehicle pickup-time conflicts and capacity checks against the current route assignments.
- **Low / moderate / heavy traffic** changes a demo-only ETA multiplier (1.0× / 1.2× / 1.5×). This is illustrative and is not measured traffic.
- The map labels each route's routing source. Route distance, duration, ETA, and fallback limitations are shown in the dashboard.

The demo simulation state is held in the backend process memory. Run a single Uvicorn worker for the demo, and keep the dashboard open while demonstrating movement. Restarting the backend resets the simulator control state but leaves demo database records intact.

## Reset safely

Use **Reset demo data** in the Demo Control Center and confirm the prompt. The endpoint deletes only records under the exact `GoVan Lahore Demo Fleet` organization, then recreates the original 30-student scenario and keeps the Fleet Manager account. The operation does not drop tables, reset the database, or delete records belonging to other organizations.

## Geographic and routing notes

The destination label follows Riphah's official QIE Campus address: 28-M, Quaid-e-Azam Industrial Estate, Kot Lakhpat, Lahore ([Riphah QIE contact page](https://riphah.edu.pk/lahore/qie/contact/)). The campus-name query did not resolve in Nominatim or Photon during implementation. The static coordinate is the center returned by PIEDMC's official QIE location map (31.444989, 74.306340), so it is an estate-level anchor and **not independently verified as the 28-M building entrance** ([PIEDMC QIE location map](https://pie.com.pk/projects/quaid-e-azam-industrial-estate/)). Do not treat it as a surveyed entrance coordinate.

Pickup markers are locality/POI anchors rather than private home addresses. The fixture uses mapped or published coordinates for Bahria/QS Galleria ([Punjab Transport Authority](https://pta.punjab.gov.pk/cm-QS-lhr)), Canal Gardens ([Yandex Maps](https://yandex.com/maps/10616/lahore/geo/5103556805/)), Adda Plot ([DistancesFrom](https://www.distancesfrom.com/pk/ADDA-PLOT-RAIWIND-ROAD-LAHORE-latitude-longitude-ADDA-PLOT-RAIWIND-ROAD-LAHORE-latitude-ADDA-PLOT-RA/LatLongHistory/3150458.aspx)), Jubilee Town entrance ([Jubilee Town location map](https://jubileetown.com/map/)), LDA Avenue ([coordinate listing](https://www.findlatitudeandlongitude.com/l/LDA%2BAvenue%2C%2BLahore%2C%2BPakistan/29079/)), Dream Gardens ([locality coordinate description](https://lahoregifthub.com/gifts-flower-delivery-in-dream-gardens-lahore/)), a Punjab Society mosque area ([Jamia Masjid map point](https://esalah.com/sq/mosques/pakistan/lahore-district/lahore/jamia-masjid-punjab-society/?method=jafari)), PCSIR Main Boulevard ([Yandex Maps](https://yandex.com/maps/10616/lahore/house/Y00YdAFlSUIFQF1rfXh0cH1kbQ%3D%3D/)), WAPDA Town ([OpenStreetMap-derived Mapcarta entry](https://mapcarta.com/N304242090)), UCP ([Higher Education Commission campus map](https://www.hec.gov.pk/english/universities/Pages/Punjab/University-of-Central-Punjab.aspx)), and a Marghzar Colony area point ([mapped photo location](https://commons.wikimedia.org/wiki/File:Maraghzar_Colony,_Lahore,_Pakistan_-_panoramio_(9).jpg)). Use these only for a non-operational demo. OpenStreetMap public Nominatim is rate-limited and should not be queried in bulk or on every page load; this demo therefore uses a cached static fixture instead of runtime geocoding.

The demo uses the existing OpenStreetMap-backed Leaflet tiles. Map tile and public routing services have their own usage policies and uptime limits. No live traffic feed or paid API key is required for the fallback demo.
