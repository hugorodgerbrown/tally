// Vitest: the JavaScript unit tests in tests/js (see docs/testing.md).
// jsdom plays the page; fake-indexeddb (tests/js/setup.js) plays IndexedDB.
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/js/setup.js'],
    include: ['tests/js/**/test_*.js'],
  },
});
