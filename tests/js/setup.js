// Runs before every Vitest file: a fresh in-memory IndexedDB for each test.
import 'fake-indexeddb/auto';
import { IDBFactory } from 'fake-indexeddb';
import { beforeEach } from 'vitest';

beforeEach(() => {
  globalThis.indexedDB = new IDBFactory();
  if (globalThis.AppDB) globalThis.AppDB._reset();
});
