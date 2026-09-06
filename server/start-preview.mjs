import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { closeSync, openSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { previewId } from './preview-identity.mjs';

const here = fileURLToPath(new URL('.', import.meta.url));

async function probe(url) {
  try {
    const response = await fetch(url + '/api/health', {signal: AbortSignal.timeout(1200), redirect: 'error'});
    if (!response.ok || response.redirected || response.headers.get('x-doctrine-preview-id') !== previewId) {
      await response.body?.cancel();
      return {ready: false};
    }
    const result = await response.json();
    const pid = Number(response.headers.get('x-doctrine-preview-pid'));
    return {ready: result.ok === true && result.service === 'doctrine-atlas-api' && Number.isInteger(pid) && pid > 0, pid};
  } catch (error) {
    // A timeout or a different HTTP service is not a free port.
    return error.cause?.code === 'ECONNREFUSED' ? null : {ready: false};
  }
}

export async function startPreview(port = 8918) {
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Port must be an integer from 1024 to 65535.');
  const url = 'http://127.0.0.1:' + port;
  const existing = await probe(url);
  if (existing?.ready) return {status: 'already-running', url, process_id: existing.pid};
  if (existing) throw new Error(`Port ${port} is occupied or unresponsive. No process was stopped.`);

  const logDir = path.join(here, '.preview');
  await mkdir(logDir, {recursive: true});
  const run = new Date().toISOString().replace(/[:.]/g, '-') + '-' + randomUUID().slice(0, 8);
  const stdout = path.join(logDir, run + '.stdout.log');
  const stderr = path.join(logDir, run + '.stderr.log');
  const out = openSync(stdout, 'wx');
  let err, child;
  try {
    err = openSync(stderr, 'wx');
    child = spawn(process.execPath, [path.join(here, 'devserver.mjs'), String(port)], {
      cwd: path.dirname(here.replace(/[\\/]$/, '')), detached: true, windowsHide: true,
      stdio: ['ignore', out, err], shell: false,
    });
  } finally {
    closeSync(out);
    if (err !== undefined) closeSync(err);
  }
  let launchError;
  child.on('error', error => { launchError = error; });
  child.unref();
  const assertRunning = () => {
    if (launchError || child.exitCode !== null || child.signalCode !== null) {
      throw new Error('Preview exited before becoming ready. See ' + stderr);
    }
  };
  const deadline = Date.now() + 12000;
  while (Date.now() < deadline) {
    assertRunning();
    const health = await probe(url);
    if (health?.ready) {
      if (health.pid !== child.pid) throw new Error('Another preview acquired this port. No process was stopped.');
      assertRunning();
      const state = {status: 'started', url, process_id: child.pid, started_utc: new Date().toISOString(), stdout, stderr};
      await writeFile(path.join(logDir, 'latest.json'), JSON.stringify(state, null, 2) + '\n');
      assertRunning();
      return state;
    }
    await delay(150);
  }
  throw new Error('Preview did not become ready within 12 seconds. See ' + stderr + '. No process was stopped.');
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const args = process.argv.slice(2);
  if (args.length === 1 && ['--help', '-h'].includes(args[0])) {
    console.log('Usage: node server/start-preview.mjs [port]\nDefault: 8918. Starts/reuses this checkout only; no build, deployment or process termination.');
  } else {
    try {
      if (args.length > 1 || (args[0] !== undefined && !/^\d+$/.test(args[0]))) throw new Error('Expected a single numeric port, or --help.');
      console.log(JSON.stringify(await startPreview(args[0] === undefined ? 8918 : Number(args[0])), null, 2));
    } catch (error) { console.error(error.message); process.exitCode = 1; }
  }
}
