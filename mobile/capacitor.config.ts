import type { CapacitorConfig } from "@capacitor/cli";

const serverUrl = process.env.MOBILE_SERVER_URL;

if (!serverUrl) {
  throw new Error("Set MOBILE_SERVER_URL to the HTTPS origin of a CoRide test server.");
}

const parsedServerUrl = new URL(serverUrl);

if (
  parsedServerUrl.protocol !== "https:" ||
  parsedServerUrl.pathname !== "/" ||
  parsedServerUrl.search ||
  parsedServerUrl.hash
) {
  throw new Error("MOBILE_SERVER_URL must be an HTTPS origin without a path, query, or fragment.");
}

const config: CapacitorConfig = {
  appId: "com.coride.app",
  appName: "CoRide",
  webDir: "www",
  server: {
    url: parsedServerUrl.origin,
    cleartext: false,
  },
};

export default config;
