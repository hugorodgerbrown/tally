/*
 * static/js/sw_core.js — the service worker's decisions, as pure functions.
 *
 * Which strategy a request gets, what the caches are called, and whether a
 * response may be stored. Unit-tested in tests/js/test_sw_core.js;
 * sw_worker.js does the caching.
 */
(function () {
  'use strict';

  /** Cache Storage names for this worker version. */
  function cacheNames(config) {
    return {
      static: config.prefix + '-static-' + config.version,
      pages: config.prefix + '-pages-' + config.version,
    };
  }

  /** True for a cache this app owns but this version doesn't use. */
  function isStaleCache(name, config) {
    const current = Object.values(cacheNames(config));
    return name.startsWith(config.prefix + '-') && !current.includes(name);
  }

  /**
   * How to answer a request.
   *   'bypass'  let the browser handle it (writes, other origins, the worker itself,
   *             anything outside the app's scope, never-cache paths)
   *   'static'  cache-first (hashed, immutable file names); network-first in DEBUG
   *   'page'    network-first with a timeout, then the cached copy, then the offline page
   * @param {{method: string}} request
   * @param {URL} url
   */
  function route(request, url, origin, config) {
    if (request.method !== 'GET') return 'bypass';
    if (url.origin !== origin) return 'bypass';
    if (url.pathname === config.workerUrl) return 'bypass';
    if (url.pathname.startsWith(config.staticUrl)) return 'static';
    // Public pages, sign-in, admin, OAuth: a controlled page can still fetch
    // them, but they are never the app's to cache.
    if (!url.pathname.startsWith(config.scope)) return 'bypass';
    if (config.neverCache.some((prefix) => url.pathname.startsWith(prefix))) return 'bypass';
    return 'page';
  }

  /** True when a response can be stored and served later. */
  function isStorable(response) {
    if (!response || !response.ok || response.redirected || response.type !== 'basic') return false;
    const cacheControl = response.headers.get('Cache-Control') || '';
    return !/no-store/i.test(cacheControl);
  }

  self.SwCore = Object.freeze({ cacheNames, isStaleCache, route, isStorable });
})();
