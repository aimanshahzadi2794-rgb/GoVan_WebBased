import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import { useEffect } from "react";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

// Leaflet's default marker icons don't load correctly with Vite's bundler
// unless we point them at the bundled image URLs explicitly.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

function FitBounds({ markers, paths, path }) {
  const map = useMap();
  const coordinates = [
    ...markers.map((marker) => [marker.lat, marker.lng]),
    ...paths.flatMap((path) => path.positions),
    ...path,
  ];
  const boundsKey = JSON.stringify(coordinates);

  useEffect(() => {
    if (coordinates.length > 1) {
      map.fitBounds(coordinates, { padding: [24, 24], maxZoom: 15 });
    }
  }, [map, boundsKey]);

  return null;
}

export default function MapView({ markers = [], paths = [], path = [], height = 300 }) {
  if (!markers.length && !paths.some((path) => path.positions.length) && path.length === 0) return null;

  const firstPathPoint = paths.find((path) => path.positions.length)?.positions[0];
  const centerPathPoint = path[0] || firstPathPoint;
  const center = markers.length
    ? [markers[0].lat, markers[0].lng]
    : centerPathPoint;

  return (
    <div style={{ height, borderRadius: 8, overflow: "hidden" }}>
      <MapContainer center={center} zoom={13} style={{ height: "100%", width: "100%" }}>
        <FitBounds markers={markers} paths={paths} path={path} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {markers.map((m, i) => (
          <Marker key={i} position={[m.lat, m.lng]}>
            {m.label && <Popup>{m.label}</Popup>}
          </Marker>
        ))}
        {paths.map((path, i) => path.positions.length > 1 && (
          <Polyline
            key={path.id || i}
            positions={path.positions}
            pathOptions={{ color: path.color || "#0077cc", weight: 5 }}
          >
            {path.label && <Popup>{path.label}</Popup>}
          </Polyline>
        ))}
        {path.length > 1 && (
          <Polyline positions={path} pathOptions={{ color: "#0077cc", weight: 5 }} />
        )}
      </MapContainer>
    </div>
  );
}