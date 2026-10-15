import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "auto",
      manifestFilename: "manifest.json",
      includeAssets: ["logo.svg", "logo.png", "pwa-192.png", "pwa-512.png"],
      manifest: {
        name: "TravelEase",
        short_name: "TravelEase",
        description: "Track your ride, share your location, stay connected.",
        theme_color: "#0093E0",
        background_color: "#0093E0",
        display: "standalone",
        start_url: "/",
        scope: "/",
        orientation: "portrait-primary",
        icons: [
          { src: "/pwa-192.png", sizes: "192x192", type: "image/png" },
          { src: "/pwa-512.png", sizes: "512x512", type: "image/png", purpose: "any maskable" },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ["**/*.{js,css,html,ico,json,png,svg,webmanifest}"],
      },
    }),
  ],
  server: { port: 5174 },
});