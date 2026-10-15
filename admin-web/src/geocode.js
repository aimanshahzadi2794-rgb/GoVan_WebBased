import { api } from "./api";

const cache = new Map();

function cacheKey(lat, lng) {
  return `${lat.toFixed(4)},${lng.toFixed(4)}`;
}

export async function reverseGeocode(lat, lng) {
  const key = cacheKey(lat, lng);
  if (cache.has(key)) return cache.get(key);

  const fallback = `${lat.toFixed(3)}, ${lng.toFixed(3)}`;

  try {
    const data = await api.get(`/geocode/reverse?lat=${lat}&lng=${lng}`);
    const label = data.label || fallback;
    cache.set(key, label);
    return label;
  } catch (err) {
    return fallback;
  }
}