import React from "react";
import { useAddress } from "../hooks/useAddress";

export default function LocationLabel({ lat, lng }) {
  const address = useAddress(lat, lng);
  if (lat == null || lng == null) return <>—</>;
  return <>{address || "Locating..."}</>;
}