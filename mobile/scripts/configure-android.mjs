import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const serverUrl = process.env.MOBILE_SERVER_URL;

if (!serverUrl) {
  throw new Error("Set MOBILE_SERVER_URL before configuring Android.");
}

const parsedServerUrl = new URL(serverUrl);
const usesCleartextTraffic = parsedServerUrl.protocol === "http:";
const manifestPath = resolve("android/app/src/main/AndroidManifest.xml");
const manifest = await readFile(manifestPath, "utf8");
let applicationFound = false;

const configuredManifest = manifest.replace(
  /<application\b([^>]*)>/,
  (_match, attributes) => {
    applicationFound = true;
    const cleanAttributes = attributes.replace(
      /\s+android:usesCleartextTraffic="[^"]*"/,
      "",
    );
    const cleartextAttribute = usesCleartextTraffic
      ? ' android:usesCleartextTraffic="true"'
      : "";

    return `<application${cleanAttributes}${cleartextAttribute}>`;
  },
);

if (!applicationFound) {
  throw new Error(`Could not find the application element in ${manifestPath}.`);
}

await writeFile(manifestPath, configuredManifest);
