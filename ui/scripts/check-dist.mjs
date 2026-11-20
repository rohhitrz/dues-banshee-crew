// Fails the build if dist/index.mjs is missing or imports a bare specifier
// that the host does not provide (design D6).
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const allowed = new Set([
  "react",
  "react-dom",
  "react/jsx-runtime",
  "@kirocrew/app-sdk",
  "@kirocrew/app-sdk/ui",
]);

const file = join(dirname(fileURLToPath(import.meta.url)), "..", "dist", "index.mjs");

if (!existsSync(file)) {
  console.error("check-dist: dist/index.mjs is missing");
  process.exit(1);
}

const source = readFileSync(file, "utf8");
const specifiers = new Set();
const patterns = [
  /\bimport\s*(?:[^'"();]*?\bfrom\s*)?["']([^"']+)["']/g,
  /\bexport\s*[^'"();]*?\bfrom\s*["']([^"']+)["']/g,
  /\bimport\s*\(\s*["']([^"']+)["']\s*\)/g,
];
for (const pattern of patterns) {
  for (const match of source.matchAll(pattern)) specifiers.add(match[1]);
}

const isBare = (s) => !(s.startsWith(".") || s.startsWith("/") || /^[a-z][a-z0-9+.-]*:/i.test(s));
const bad = [...specifiers].filter((s) => isBare(s) && !allowed.has(s));
if (bad.length > 0) {
  console.error(`check-dist: bare specifiers outside the externals list: ${bad.join(", ")}`);
  process.exit(1);
}

console.log(`check-dist: ok (${specifiers.size} import specifier(s), all allowed)`);
