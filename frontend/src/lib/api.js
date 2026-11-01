// Tiny fetch wrapper. HTTP errors resolve as { ok: false, status, json }; only network failures throw.
async function request(method, url, body) {
  const res = await fetch(url, {
    method,
    credentials: 'same-origin',
    headers: body === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let json;
  try {
    json = await res.json();
  } catch {
    json = { error: 'Unexpected response from the server.' };
  }
  return { ok: res.ok, status: res.status, json };
}

export const api = {
  get: (url) => request('GET', url),
  post: (url, body) => request('POST', url, body ?? {}),
};
