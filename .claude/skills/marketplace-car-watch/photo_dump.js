// Reads the photos photo_grab.js saved on this site and returns "key|dataurl"
// lines, padded to at least 110,000 characters so the tool saves the result
// to a file. The device bridge cuts results off at about 250,000 characters, so
// this returns at most about 160,000 characters per call, re-shrinking any
// photo bigger than 60 KB. Set start to the "next" number the last call gave
// and call again until it says done. Set reset = true on the last call to
// clear the store. Feed each saved result file to photo_save.py.
(async () => {
  const start = 0, reset = false;
  const db = await new Promise((res, rej) => { const q = indexedDB.open('cwphotos', 1); q.onupgradeneeded = () => q.result.createObjectStore('kv'); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); });
  const all = await new Promise((res) => { const out = []; const t = db.transaction('kv', 'readonly'); const cur = t.objectStore('kv').openCursor(); cur.onsuccess = () => { const c = cur.result; if (c) { out.push([c.key, c.value]); c.continue(); } else res(out); }; });
  const shrink = async (url) => {
    if (url.length <= 60000) return url;
    const bmp = await new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = url; });
    const w = Math.min(480, bmp.width), h = Math.round(bmp.height * w / bmp.width);
    const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(bmp, 0, 0, w, h);
    for (const q of [0.7, 0.55, 0.4]) { const u = c.toDataURL('image/jpeg', q); if (u.length <= 60000) return u; }
    return c.toDataURL('image/jpeg', 0.3);
  };
  const lines = []; let size = 0, i = start;
  for (; i < all.length; i++) {
    const line = all[i][0] + '|' + await shrink(all[i][1]);
    if (lines.length && size + line.length > 150000) break;
    lines.push(line); size += line.length;
  }
  const done = i >= all.length;
  if (done && reset) await new Promise((res) => { const t = db.transaction('kv', 'readwrite'); t.objectStore('kv').clear(); t.oncomplete = res; });
  return all.length + ' photos, ' + (done ? 'done' : 'next ' + i) + '\n' + lines.join('\n') + '\n---END---' + ' '.repeat(Math.max(0, 110000 - size));
})();
