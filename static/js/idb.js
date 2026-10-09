/*
 * static/js/idb.js — the app's one IndexedDB database, as promises.
 *
 * Two stores:
 *   outbox  writes waiting to be sent (see outbox.js), keyPath `id`
 *   meta    small key/value facts shared with the service worker, such as
 *           the signed-in user and the current CSRF token
 *
 * A classic script, loaded by pages and by the service worker
 * (importScripts), so it publishes `self.AppDB` rather than exporting.
 * Bump VERSION and extend `upgrade` to add a store; never edit a store
 * in place.
 */
(function () {
  'use strict';

  const DB_NAME = 'app';
  const VERSION = 1;
  let opening = null;

  function upgrade(db) {
    if (!db.objectStoreNames.contains('outbox')) {
      db.createObjectStore('outbox', { keyPath: 'id', autoIncrement: true });
    }
    if (!db.objectStoreNames.contains('meta')) {
      db.createObjectStore('meta', { keyPath: 'key' });
    }
  }

  function open() {
    if (!opening) {
      opening = new Promise(function (resolve, reject) {
        const request = indexedDB.open(DB_NAME, VERSION);
        request.onupgradeneeded = function () {
          upgrade(request.result);
        };
        request.onsuccess = function () {
          const db = request.result;
          // Another tab is upgrading: close so it isn't blocked forever.
          db.onversionchange = function () {
            db.close();
            opening = null;
          };
          resolve(db);
        };
        request.onerror = function () {
          opening = null;
          reject(request.error);
        };
      });
    }
    return opening;
  }

  function run(storeName, mode, operation) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        const tx = db.transaction(storeName, mode);
        const request = operation(tx.objectStore(storeName));
        tx.oncomplete = function () {
          resolve(request.result);
        };
        tx.onerror = function () {
          reject(tx.error);
        };
        tx.onabort = function () {
          reject(tx.error);
        };
      });
    });
  }

  self.AppDB = Object.freeze({
    add: function (store, value) {
      return run(store, 'readwrite', function (s) {
        return s.add(value);
      });
    },
    put: function (store, value) {
      return run(store, 'readwrite', function (s) {
        return s.put(value);
      });
    },
    get: function (store, key) {
      return run(store, 'readonly', function (s) {
        return s.get(key);
      });
    },
    getAll: function (store) {
      return run(store, 'readonly', function (s) {
        return s.getAll();
      });
    },
    delete: function (store, key) {
      return run(store, 'readwrite', function (s) {
        return s.delete(key);
      });
    },
    getMeta: function (key) {
      return run('meta', 'readonly', function (s) {
        return s.get(key);
      }).then(function (row) {
        return row ? row.value : undefined;
      });
    },
    setMeta: function (key, value) {
      return run('meta', 'readwrite', function (s) {
        return s.put({ key: key, value: value });
      });
    },
    /** Forget the open connection (tests replace indexedDB between cases). */
    _reset: function () {
      if (opening) {
        opening.then(function (db) {
          db.close();
        });
      }
      opening = null;
    },
  });
})();
