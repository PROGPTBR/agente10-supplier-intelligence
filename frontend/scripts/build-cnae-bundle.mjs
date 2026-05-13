// frontend/scripts/build-cnae-bundle.mjs
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = join(__dirname, "..", "..", "backend", "data", "cnae_2.3", "taxonomy_with_embeddings.json");
const dst = join(__dirname, "..", "lib", "cnae-taxonomy.json");

const raw = JSON.parse(await readFile(src, "utf-8"));
// Strip embeddings; keep only codigo + denominacao for client picker
const stripped = raw.map((entry) => ({
  codigo: entry.codigo,
  denominacao: entry.denominacao,
}));
await writeFile(dst, JSON.stringify(stripped));
console.log(`Wrote ${stripped.length} CNAEs to ${dst}`);
