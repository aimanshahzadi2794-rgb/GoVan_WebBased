import { useEffect, useState } from "react";
import { reverseGeocode } from "../geocode";

export function useAddress(lat, lng) {
  const [address, setAddress] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (lat == null || lng == null) {
      setAddress(null);
      return;
    }
    setAddress(null);
    reverseGeocode(lat, lng).then((label) => {
      if (!cancelled) setAddress(label);
    });
    return () => { cancelled = true; };
  }, [lat, lng]);

  return address;
}