// Tests for static/js/passkeys.js: which controls show, and what a failed ceremony says.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../static/js/webauthn_json.js';

const SIGN_IN = `
  <input name="csrfmiddlewaretoken" value="token">
  <section data-passkey-sign-in data-options-url="/o" data-verify-url="/v" data-next="/app/" hidden>
    <button data-passkey-button></button>
    <p data-passkey-error hidden></p>
  </section>`;

const ACCOUNT = `
  <meta name="csrf-token" content="token">
  <section data-passkey-register data-options-url="/o" data-register-url="/r">
    <div data-passkey-controls hidden><button data-passkey-button></button><p data-passkey-error hidden></p></div>
    <p data-passkey-unsupported></p>
  </section>`;

async function load(html) {
  document.body.innerHTML = html;
  vi.resetModules();
  await import('../../static/js/passkeys.js');
}

const credential = { toJSON: () => ({ id: 'cred' }) };
function respond(status, body) {
  return Promise.resolve({ status, ok: status < 300, json: () => Promise.resolve(body) });
}
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

beforeEach(() => {
  globalThis.PublicKeyCredential = {};
  Object.defineProperty(navigator, 'credentials', {
    value: { get: vi.fn(() => Promise.resolve(credential)), create: vi.fn(() => Promise.resolve(credential)) },
    configurable: true,
  });
});

afterEach(() => {
  delete globalThis.PublicKeyCredential;
  delete globalThis.fetch;
  vi.restoreAllMocks();
});

describe('without WebAuthn', () => {
  it('leaves the passkey controls hidden', async () => {
    delete globalThis.PublicKeyCredential;
    await load(SIGN_IN + ACCOUNT);
    expect(document.querySelector('[data-passkey-sign-in]').hidden).toBe(true);
    expect(document.querySelector('[data-passkey-controls]').hidden).toBe(true);
  });
});

describe('sign in', () => {
  it('shows the button, and a removed passkey is reported and signalled', async () => {
    const signal = vi.fn(() => Promise.resolve());
    globalThis.PublicKeyCredential = { signalUnknownCredential: signal };
    globalThis.fetch = vi.fn((url) =>
      url === '/o' ? respond(200, { challenge: 'AQID' }) : respond(404, { error: 'unknown_passkey', credentialId: 'cred' })
    );
    await load(SIGN_IN);
    const section = document.querySelector('[data-passkey-sign-in]');
    expect(section.hidden).toBe(false);

    section.querySelector('[data-passkey-button]').click();
    await flush();
    await flush();
    const [, verify] = globalThis.fetch.mock.calls;
    expect(JSON.parse(verify[1].body)).toEqual({ credential: { id: 'cred' }, next: '/app/' });
    expect(verify[1].headers['X-CSRFToken']).toBe('token');
    expect(signal).toHaveBeenCalledWith({ rpId: location.hostname, credentialId: 'cred' });
    expect(section.querySelector('[data-passkey-error]').textContent).toMatch(/isn't on your account/);
  });
});

describe('autofill and the button together', () => {
  it('sends their requests one at a time', async () => {
    let release;
    const first = new Promise((resolve) => {
      release = resolve;
    });
    globalThis.PublicKeyCredential = { isConditionalMediationAvailable: () => Promise.resolve(true) };
    globalThis.fetch = vi.fn((url) => {
      if (globalThis.fetch.mock.calls.length === 1) return first.then(() => respond(200, { challenge: 'AQID' }));
      return url === '/o' ? respond(200, { challenge: 'BAUG' }) : respond(400, {});
    });
    navigator.credentials.get = vi.fn(() => new Promise(() => {})); // autofill waits for the user
    await load(SIGN_IN);
    await flush();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1); // autofill's options, still in flight

    document.querySelector('[data-passkey-button]').click();
    await flush();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1); // the button's waits its turn

    release();
    await flush();
    await flush();
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
  });
});

describe('add a passkey', () => {
  it('shows the controls and reports a failed registration', async () => {
    globalThis.fetch = vi.fn((url) => (url === '/o' ? respond(200, { challenge: 'AQID', user: { id: 'AQ' } }) : respond(400, {})));
    await load(ACCOUNT);
    const section = document.querySelector('[data-passkey-register]');
    expect(section.querySelector('[data-passkey-controls]').hidden).toBe(false);
    expect(section.querySelector('[data-passkey-unsupported]').hidden).toBe(true);

    section.querySelector('[data-passkey-button]').click();
    await flush();
    await flush();
    expect(navigator.credentials.create).toHaveBeenCalled();
    expect(section.querySelector('[data-passkey-error]').hidden).toBe(false);
    expect(section.querySelector('[data-passkey-button]').disabled).toBe(false);
  });
});

describe('describe', () => {
  it('stays quiet when the user cancels, and names the common failures', async () => {
    await load(ACCOUNT);
    const { describe: say } = self.Passkeys;
    expect(say({ name: 'NotAllowedError' })).toBe('');
    expect(say({ name: 'AbortError' })).toBe('');
    expect(say({ name: 'InvalidStateError' })).toMatch(/already has a passkey/);
    expect(say(new Error('x'))).toMatch(/didn't work/);
  });
});
