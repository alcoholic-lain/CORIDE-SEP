import type { CapacitorConfig } from "@capacitor/cli";

const serverUrl = process.env.MOBILE_SERVER_URL;

if (!serverUrl) {
  throw new Error("Set MOBILE_SERVER_URL to a CoRide server origin, such as http://192.168.1.10:8000.");
}

const parsedServerUrl = new URL(serverUrl);

if (
  !["http:", "https:"].includes(parsedServerUrl.protocol) ||
  parsedServerUrl.pathname !== "/" ||
  parsedServerUrl.search ||
  parsedServerUrl.hash
) {
  throw new Error("MOBILE_SERVER_URL must be an HTTP(S) origin without a path, query, or fragment.");
}

const config: CapacitorConfig = {
  appId: "com.coride.app",
  appName: "CoRide",
  webDir: "www",
  server: {
    url: parsedServerUrl.origin,
  },
};

export default config;
