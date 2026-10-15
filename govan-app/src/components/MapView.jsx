import { useEffect } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

function FitRouteBounds({ points }) {
  const map = useMap();
  const pointsKey = JSON.stringify(points);

  useEffect(() => {
    if (points.length > 1) {
      map.fitBounds(points, { padding: [24, 24], maxZoom: 15 });
    } else if (points.length === 1) {
      map.setView(points[0], 14);
    }
  }, [map, pointsKey]);

  return null;
}

export default function MapView({ markers = [], stops = [], height = 300 }) {
  const stopPoints = stops.map((stop) => [stop.lat, stop.lng]);
  const points = [
    ...stopPoints,
    ...markers.map((marker) => [marker.lat, marker.lng]),
  ];
  if (points.length === 0) return null;
  const fitPoints = stopPoints.length > 0 ? stopPoints : points;

  return (
    <div className="live-map" style={{ height }}>
      <MapContainer center={fitPoints[0]} zoom={13} style={{ height: "100%", width: "100%" }}>
        <FitRouteBounds points={fitPoints} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {stops.map((stop, index) => (
          <Marker key={stop.id} position={[stop.lat, stop.lng]}>
            <Popup>{index + 1}. {stop.name}</Popup>
          </Marker>
        ))}
        {stopPoints.length > 1 && (
          <Polyline positions={stopPoints} pathOptions={{ color: "#0093e0", weight: 4, dashArray: "8 7" }} />
        )}
        {markers.map((marker) => (
          <Marker key={`${marker.lat}-${marker.lng}`} position={[marker.lat, marker.lng]}>
            {marker.label && <Popup>{marker.label}</Popup>}
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
