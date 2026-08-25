import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const root = 'dist';
const htmlPaths = [];

function collectHtmlPaths(directory) {
  for (const name of readdirSync(directory)) {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) {
      collectHtmlPaths(path);
      continue;
    }
    if (path.endsWith('.html')) htmlPaths.push(path);
  }
}

collectHtmlPaths(root);

const missing = new Set();
const attributePattern = /(?:href|src)=["']([^"']+)["']/g;

for (const htmlPath of htmlPaths) {
  const html = readFileSync(htmlPath, 'utf8');
  for (const match of html.matchAll(attributePattern)) {
    const value = match[1];
    const url = new URL(value, 'https://skiller.run');
    if (url.origin !== 'https://skiller.run' || !value.startsWith('/')) continue;

    const relativePath = url.pathname.slice(1);
    const candidates = [join(root, relativePath)];
    if (url.pathname.endsWith('/')) {
      candidates.push(join(root, relativePath, 'index.html'));
    } else if (!relativePath.split('/').at(-1).includes('.')) {
      candidates.push(join(root, `${relativePath}.html`));
      candidates.push(join(root, relativePath, 'index.html'));
    }

    if (!candidates.some(existsSync)) {
      missing.add(`${relative(root, htmlPath)}: ${value}`);
    }
  }
}

if (missing.size > 0) {
  for (const entry of [...missing].sort()) console.error(entry);
  console.error(`${missing.size} missing internal links or assets`);
  process.exit(1);
}

console.log('Built-site internal links and assets: OK');
