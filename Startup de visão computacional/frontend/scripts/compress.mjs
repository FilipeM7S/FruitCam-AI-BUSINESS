import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const root = path.resolve(process.argv[2] || "dist");
const types = /\.(js|css|html|svg|json|webmanifest|vtt|txt|map)$/;
let raw = 0;
let br = 0;
let count = 0;

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(file);
    else if (types.test(entry.name) && fs.statSync(file).size >= 1024) compress(file);
  }
}

function compress(file) {
  const data = fs.readFileSync(file);
  const brotli = zlib.brotliCompressSync(data, { params: { [zlib.constants.BROTLI_PARAM_QUALITY]: 11, [zlib.constants.BROTLI_PARAM_SIZE_HINT]: data.length } });
  fs.writeFileSync(`${file}.br`, brotli);
  fs.writeFileSync(`${file}.gz`, zlib.gzipSync(data, { level: 9 }));
  raw += data.length;
  br += brotli.length;
  count += 1;
}

walk(root);
console.log(`precompressed ${count} files: ${raw} B -> ${br} B brotli (${((100 * br) / Math.max(raw, 1)).toFixed(1)}%)`);
