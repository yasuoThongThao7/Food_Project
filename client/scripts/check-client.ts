import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '../../');
const contractPath = path.join(root, 'Backend/docs/CONTRACT.md');
const endpointsPath = path.join(root, 'client/src/api/endpoints.ts');

const contract = fs.readFileSync(contractPath, 'utf8');
const endpointBlock = contract.split('# Endpoints')[1]?.split('\n#', 1)[0] ?? '';
const contractEndpoints = new Set(
  endpointBlock.split(/\r?\n/)
    .map((line) => line.trim().match(/^(GET|POST|PUT|PATCH|DELETE)\s+(\S+)/))
    .filter((match): match is RegExpMatchArray => Boolean(match))
    .map((match) => {
      const route = match[2]
        .replace(/:([A-Za-z0-9_]+)/g, '{}')
        .replace(/\$\{[^}]+\}/g, '{}')
        .replace(/\{[^}]+\}/g, '{}')
        .split('?')[0];
      return `${match[1]} ${route}`;
    })
);

const endpointsSource = fs.readFileSync(endpointsPath, 'utf8');
const clientEndpoints = new Set<string>();
for (const match of endpointsSource.matchAll(/(['"`])(GET|POST|PUT|PATCH|DELETE) ([^'"`]+)\1/g)) {
  let route = match[3].split('?')[0];
  route = route
    .replace(/:([A-Za-z0-9_]+)/g, '{}')
    .replace(/\$\{[^}]+\}/g, '{}')
    .replace(/\{[^}]+\}/g, '{}');
  clientEndpoints.add(`${match[2]} ${route}`);
}

const missing = [...contractEndpoints].filter((route) => !clientEndpoints.has(route));
const extra = [...clientEndpoints].filter((route) => !contractEndpoints.has(route));
if (missing.length || extra.length) {
  console.error({ missing, extra });
  process.exit(1);
}
console.log(`Client matches CONTRACT (${contractEndpoints.size} endpoints).`);
