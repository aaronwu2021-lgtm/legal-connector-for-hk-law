import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, copyFile, writeFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { pathToFileURL } from 'node:url';

const execute = promisify(execFile);
const source = new URL('../', import.meta.url);
const fixtureServer = `import http from 'node:http';
import {previewId} from './preview-identity.mjs';
http.createServer((req,res)=>{res.setHeader('x-doctrine-preview-id',previewId);
res.setHeader('x-doctrine-preview-pid',String(process.pid));res.setHeader('content-type','application/json');
res.end(JSON.stringify({ok:true,service:'doctrine-atlas-api'}));}).listen(Number(process.argv[2]),'127.0.0.1');`;

async function fixture(t) {
  const dir = await mkdtemp(path.join(tmpdir(), 'doctrine preview fixture '));
  assert.ok(path.resolve(dir).startsWith(path.resolve(tmpdir()) + path.sep));
  t.after(async () => { await rm(dir, {recursive: true, force: true, maxRetries: 5, retryDelay: 100}); });
  for (const name of ['start-preview.mjs', 'preview-identity.mjs']) await copyFile(new URL(name, source), path.join(dir, name));
  await writeFile(path.join(dir, 'devserver.mjs'), fixtureServer);
  return dir;
}
const command = (dir, args = []) => execute(process.execPath, [path.join(dir, 'start-preview.mjs'), ...args],
  {cwd: tmpdir(), timeout: 8000, windowsHide: true});
async function listen(server) {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return server.address().port;
}
async function close(server) {
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}

test('import, help and invalid arguments do not create preview logs or a process', async t => {
  const dir = await fixture(t), before = await readdir(dir);
  await import(pathToFileURL(path.join(dir, 'start-preview.mjs')).href);
  assert.match((await command(dir, ['--help'])).stdout, /Usage:/);
  for (const args of [['--unknown'], ['0'], ['65536'], ['8918', 'extra']]) {
    await assert.rejects(command(dir, args));
  }
  assert.deepEqual(await readdir(dir), before);
});

test('preview outlives the launcher and an exact healthy checkout is reused without new logs', async t => {
  const dir = await fixture(t);
  const reservation = http.createServer(), port = await listen(reservation);
  await close(reservation);
  let owned;
  t.after(async () => {
    if (owned) {
      // The PID comes from the child started by this temporary-fixture launcher.
      try { process.kill(owned); } catch (error) { if (error.code !== 'ESRCH') throw error; }
      await new Promise(resolve => setTimeout(resolve, 120));
    }
  });
  const first = JSON.parse((await command(dir, [String(port)])).stdout);
  owned = first.process_id;
  assert.equal(first.status, 'started');
  assert.ok(owned > 0);
  const health = await fetch(first.url + '/api/health');
  assert.equal((await health.json()).ok, true);
  assert.equal(health.headers.get('x-doctrine-preview-pid'), String(owned));
  const logs = await readdir(path.join(dir, '.preview'));
  const second = JSON.parse((await command(dir, [String(port)])).stdout);
  assert.equal(second.status, 'already-running');
  assert.equal(second.process_id, owned);
  assert.deepEqual(await readdir(path.join(dir, '.preview')), logs);
});

test('another HTTP service is refused even with a matching service name', async t => {
  const dir = await fixture(t);
  const server = http.createServer((req, res) => {
    res.setHeader('content-type', 'application/json');
    res.end(JSON.stringify({ok: true, service: 'doctrine-atlas-api'}));
  });
  const port = await listen(server);
  t.after(() => close(server));
  await assert.rejects(command(dir, [String(port)]), error => /occupied or unresponsive/.test(error.stderr));
  assert.equal((await (await fetch('http://127.0.0.1:' + port)).json()).ok, true);
  assert.ok(!(await readdir(dir)).includes('.preview'));
});

test('an unresponsive occupied port times out without launching or terminating it', async t => {
  const dir = await fixture(t), server = http.createServer(() => {});
  const port = await listen(server);
  t.after(() => close(server));
  await assert.rejects(command(dir, [String(port)]), error => /occupied or unresponsive/.test(error.stderr));
  assert.equal(server.listening, true);
  assert.ok(!(await readdir(dir)).includes('.preview'));
});

test('an occupied redirect cannot borrow the identity of a preview on another port', async t => {
  const dir = await fixture(t);
  const {previewId} = await import(pathToFileURL(path.join(dir, 'preview-identity.mjs')).href);
  let targetRequests = 0;
  const target = http.createServer((req, res) => {
    targetRequests++;
    res.setHeader('x-doctrine-preview-id', previewId);
    res.setHeader('x-doctrine-preview-pid', String(process.pid));
    res.setHeader('content-type', 'application/json');
    res.end(JSON.stringify({ok: true, service: 'doctrine-atlas-api'}));
  });
  const targetPort = await listen(target);
  const occupied = http.createServer((req, res) => {
    res.writeHead(302, {location: 'http://127.0.0.1:' + targetPort + '/api/health'});
    res.end();
  });
  const occupiedPort = await listen(occupied);
  t.after(async () => { await close(occupied); await close(target); });
  await assert.rejects(command(dir, [String(occupiedPort)]), error => /occupied or unresponsive/.test(error.stderr));
  assert.equal(targetRequests, 0);
  assert.ok(!(await readdir(dir)).includes('.preview'));
});
