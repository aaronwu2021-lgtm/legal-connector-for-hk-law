// Local preview without the Netlify CLI.
//
// `npx netlify dev` is the documented way to run this, but it needs the Netlify
// CLI and a network install. This does the same job with nothing but Node:
// serves public/ statically and routes /api/* through the same handler the
// deployed function exports, against whatever is currently in data/ (via the
// generated _*.mjs modules). Useful for seeing the effect of a builder change
// before deciding whether to deploy.
//
//   node server/devserver.mjs [port]      default 8899
//
// It is a preview server: no HTTPS, no caching, single process, binds
// localhost only. Do not put it in front of anything.

import http from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(HERE, 'public');
const FUNCTION = path.join(HERE, 'netlify', 'functions', 'api.mjs');
const PORT = Number(process.argv[2]) || 8899;

const handler = (await import(pathToFileURL(FUNCTION).href)).default;

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
};

http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');

    if (url.pathname === '/api' || url.pathname.startsWith('/api/')) {
      let body;
      if (req.method !== 'GET' && req.method !== 'HEAD') {
        const chunks = [];
        for await (const chunk of req) chunks.push(chunk);
        body = Buffer.concat(chunks).toString('utf8');
      }
      const response = await handler(
        new Request('https://localhost' + req.url, { method: req.method, headers: req.headers, body }),
        {},
      );
      const text = await response.text();
      res.writeHead(response.status, {
        'content-type': response.headers.get('content-type') || 'application/json',
        'access-control-allow-origin': '*',
      });
      return res.end(text);
    }

    const rel = url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname).slice(1);
    const file = path.resolve(PUBLIC, rel);
    if (!file.startsWith(PUBLIC)) {          // no traversal out of public/
      res.writeHead(403, { 'content-type': 'text/plain' });
      return res.end('forbidden');
    }
    const buf = await readFile(file);
    res.writeHead(200, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream' });
    res.end(buf);
  } catch (err) {
    const code = err && err.code === 'ENOENT' ? 404 : 500;
    res.writeHead(code, { 'content-type': 'text/plain; charset=utf-8' });
    res.end(code === 404 ? 'not found' : String((err && err.message) || err));
  }
}).listen(PORT, '127.0.0.1', () => {
  console.log(`doctrine connector preview -> http://localhost:${PORT}`);
  console.log('serving the CURRENT contents of data/ via netlify/functions/_*.mjs');
});
