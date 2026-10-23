import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

// Exercise the actual TypeScript client without adding a test framework.
const source = await readFile(new URL('../src/services/api.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText;
const originalFetch = globalThis.fetch;
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
const { api } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
after(() => { globalThis.fetch = originalFetch; delete globalThis.localStorage; });

test('validation errors show a short message without echoing submitted input', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({detail:[{msg:'Question is too long', input:'private draft'}]}), {status:422});
  await assert.rejects(api.directQuery({question:'private draft'}), {message:'Question is too long'});
});

test('malformed validation entries never become object strings', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({detail:[{msg:{private:'payload'}}]}), {status:422});
  await assert.rejects(api.directQuery({question:'test'}), error => error.message === 'Request failed with status 422');
});

test('timeout stays active while receiving a slow response body', async () => {
  globalThis.fetch = async (_url, {signal}) => ({ok:true, json:() => new Promise((_resolve,reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted','AbortError')), {once:true});
  })});
  await assert.rejects(api.request('/health', {}, 15), /timed out/);
});

test('external cancellation does not disable the request timeout', async () => {
  globalThis.fetch = (_url, {signal}) => new Promise((_resolve,reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted','AbortError')), {once:true});
  });
  const caller = new AbortController();
  await assert.rejects(api.request('/documents', {signal:caller.signal}, 15), /timed out/);
});

test('caller abort is identifiable and cancels an in-flight read', async () => {
  globalThis.fetch = (_url, {signal}) => new Promise((_resolve,reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted','AbortError')), {once:true});
  });
  const caller = new AbortController();
  const request = api.listDocuments('Java', caller.signal);
  caller.abort();
  await assert.rejects(request, {name:'AbortError'});
});

test('failed conversation writes are never silently retried', async () => {
  let calls = 0;
  globalThis.fetch = async () => { calls++; return new Response('upstream unavailable', {status:503}); };
  await assert.rejects(api.sendMessage(1, {question:'Explain Java interfaces'}), /503/);
  assert.equal(calls, 1);
});

test('large PDF uploads allow five minutes and never retry an uncertain save', async () => {
  const request = api.request;
  let calls = 0;
  api.request = async (path, options, timeout) => {
    calls++;
    assert.equal(path, '/documents/upload');
    assert.equal(timeout, 300000);
    assert.ok(options.body instanceof FormData);
    assert.equal(options.body.get('subject'), 'Java');
    throw new Error('Request timed out. Refresh before retrying.');
  };
  try {
    await assert.rejects(api.uploadDocument(new File(['%PDF-synthetic'], 'sample.pdf'), 'Sample', 'Java'), /Refresh/);
    assert.equal(calls, 1);
  } finally { api.request = request; }
});

test('subject deletion encodes personal names and never retries a failed deletion', async () => {
  let calls = 0;
  globalThis.fetch = async (url, options) => {
    calls++;
    assert.equal(url, '/api/v1/subjects?name=Art%20%2F%20Design%20%26%20Theory');
    assert.equal(options.method, 'DELETE');
    return new Response(JSON.stringify({ detail: 'Wait for processing to finish.' }), { status: 409 });
  };
  await assert.rejects(api.deleteSubject('Art / Design & Theory'), /processing/);
  assert.equal(calls, 1);
});

test('private PDFs use an authorization header and preserve the requested page', async (context) => {
  context.mock.timers.enable({ apis: ['setTimeout'] });
  let openedUrl;
  let revokedUrl;
  const viewer = { opener: {}, close() {}, location: { replace(url) { openedUrl = url; } } };
  globalThis.window = { open: () => viewer };
  context.mock.method(URL, 'createObjectURL', () => 'blob:private-reference');
  context.mock.method(URL, 'revokeObjectURL', url => { revokedUrl = url; });
  api.setToken('test-account-token');
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/v1/documents/12/download');
    assert.equal(options.headers.get('Authorization'), 'Bearer test-account-token');
    assert.equal(options.cache, 'no-store');
    return new Response(new Blob(['%PDF-test'], { type: 'application/pdf' }));
  };
  try {
    await api.openPdf(12, 42);
    assert.equal(openedUrl, 'blob:private-reference#page=42');
    assert.equal(viewer.opener, null);
    context.mock.timers.tick(300000);
    assert.equal(revokedUrl, 'blob:private-reference');
  } finally {
    api.setToken(null);
    delete globalThis.window;
  }
});

test('denied PDF requests close the reserved tab without opening a document', async () => {
  let closed = false;
  globalThis.window = { open: () => ({ close() { closed = true; }, location: { replace() { assert.fail('Must not open a denied PDF'); } } }) };
  globalThis.fetch = async () => new Response('Document not found', { status: 404 });
  try {
    await assert.rejects(api.openPdf(999), /account that owns it/);
    assert.equal(closed, true);
  } finally {
    delete globalThis.window;
  }
});
