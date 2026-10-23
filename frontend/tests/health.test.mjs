import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/healthSnapshot.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ES2022}}).outputText;
const { healthForAccount } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

test('an account change hides private counts even when refresh has not succeeded', () => {
  const alice = {accountId: 1, health: {database: {total_documents: 9, total_indexed_chunks: 42}}};
  assert.equal(healthForAccount(alice, 1).database.total_documents, 9);
  assert.equal(healthForAccount(alice, 2), null);
  assert.equal(healthForAccount(alice, null), null);
  assert.equal(healthForAccount(null, 2), null);
  const bob = {accountId: 2, health: {database: {total_documents: 4}}};
  assert.equal(healthForAccount(bob, 2).database.total_documents, 4);
  assert.equal(healthForAccount(bob, 1), null);
});

test('a guest response cannot replace authenticated account health', () => {
  const guest = {accountId: null, health: {database: {total_documents: 4}}};
  assert.equal(healthForAccount(guest, null), guest.health);
  assert.equal(healthForAccount(guest, 3), null);
});
