// Tests for static/js/webauthn_json.js: WebAuthn JSON <-> ArrayBuffers, by hand.
import { afterEach, describe, expect, it } from 'vitest';

import '../../static/js/webauthn_json.js';

const codec = self.WebAuthnJSON;
const bytes = (buffer) => Array.from(new Uint8Array(buffer));

afterEach(() => {
  delete globalThis.PublicKeyCredential;
});

describe('base64url', () => {
  it('round-trips bytes, unpadded and URL-safe', () => {
    const data = new Uint8Array([0, 251, 255, 62, 63, 1]);
    const text = codec.toBase64url(data.buffer);
    expect(text).not.toMatch(/[+/=]/);
    expect(bytes(codec.toBuffer(text))).toEqual(Array.from(data));
  });

  it('reads a typed-array view, not its whole buffer', () => {
    const whole = new Uint8Array([9, 1, 2, 3, 9]);
    expect(codec.toBase64url(whole.subarray(1, 4))).toBe('AQID');
  });
});

describe('options', () => {
  it('turns creation options into buffers', () => {
    const options = codec.creationOptions({
      challenge: 'AQID',
      rp: { id: 'example.test', name: 'Example' },
      user: { id: 'BAU', name: 'a@example.test', displayName: 'a@example.test' },
      excludeCredentials: [{ id: 'Bgc', type: 'public-key' }],
    });
    expect(bytes(options.challenge)).toEqual([1, 2, 3]);
    expect(bytes(options.user.id)).toEqual([4, 5]);
    expect(options.user.name).toBe('a@example.test');
    expect(bytes(options.excludeCredentials[0].id)).toEqual([6, 7]);
  });

  it('turns request options into buffers', () => {
    const options = codec.requestOptions({ challenge: 'AQID', rpId: 'example.test' });
    expect(bytes(options.challenge)).toEqual([1, 2, 3]);
    expect(options.allowCredentials).toEqual([]);
  });

  it('uses the browser\'s own parser when there is one', () => {
    globalThis.PublicKeyCredential = {
      parseCreationOptionsFromJSON: (json) => ({ parsed: json.challenge }),
      parseRequestOptionsFromJSON: (json) => ({ parsed: json.challenge }),
    };
    expect(codec.creationOptions({ challenge: 'x' })).toEqual({ parsed: 'x' });
    expect(codec.requestOptions({ challenge: 'y' })).toEqual({ parsed: 'y' });
  });
});

describe('credentialToJSON', () => {
  const buf = (...values) => new Uint8Array(values).buffer;

  it('encodes a new credential (attestation)', () => {
    const json = codec.credentialToJSON({
      id: 'AQ',
      rawId: buf(1),
      type: 'public-key',
      authenticatorAttachment: 'platform',
      response: { clientDataJSON: buf(2), attestationObject: buf(3), getTransports: () => ['internal'] },
      getClientExtensionResults: () => ({}),
    });
    expect(json).toEqual({
      id: 'AQ',
      rawId: 'AQ',
      type: 'public-key',
      authenticatorAttachment: 'platform',
      response: { clientDataJSON: 'Ag', attestationObject: 'Aw', transports: ['internal'] },
      clientExtensionResults: {},
    });
  });

  it('encodes a sign-in (assertion)', () => {
    const json = codec.credentialToJSON({
      id: 'AQ',
      rawId: buf(1),
      type: 'public-key',
      response: { clientDataJSON: buf(2), authenticatorData: buf(4), signature: buf(5), userHandle: buf(6) },
    });
    expect(json.response).toEqual({ clientDataJSON: 'Ag', authenticatorData: 'BA', signature: 'BQ', userHandle: 'Bg' });
    expect(json.clientExtensionResults).toEqual({});
  });

  it('prefers the credential\'s own toJSON', () => {
    expect(codec.credentialToJSON({ toJSON: () => ({ native: true }) })).toEqual({ native: true });
  });
});
