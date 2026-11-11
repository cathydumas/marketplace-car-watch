// Paste into a Facebook Marketplace item page or an AutoTrader.ca listing page.
// Saves the main photo, shrunk to 480 px wide, as a JPEG data URL in IndexedDB
// ('cwphotos', store 'kv', key = listing key). Returns the key and size.
// Run photo_dump.js on the same site afterwards to read them all back.
(async () => {
  await new Promise((r) => setTimeout(r, 1500));
  const u = location.href;
  let key = null;
  let m = u.match(/marketplace\/item\/(\d+)/);
  if (m) key = 'facebook-' + m[1];
  m = u.match(/autotrader\.ca\/offers\/.*-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/);
  if (m) key = 'autotrader-' + m[1];
  if (!key) return 'not a listing page';
  const big = [...document.querySelectorAll('img')].filter((i) => i.naturalWidth >= 300 && i.naturalHeight >= 200);
  const img = big.find((i) => /^Product photo of/i.test(i.alt)) || big[0];
  if (!img) return key + ': no photo found';
  let bmp;
  try {
    const blob = await fetch(img.currentSrc || img.src, { mode: 'cors' }).then((r) => r.blob());
    bmp = await createImageBitmap(blob);
  } catch (e) { return key + ': fetch blocked (' + e.message + ')'; }
  const w = Math.min(480, bmp.width), h = Math.round(bmp.height * w / bmp.width);
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  c.getContext('2d').drawImage(bmp, 0, 0, w, h);
  const url = c.toDataURL('image/jpeg', 0.72);
  const db = await new Promise((res, rej) => { const q = indexedDB.open('cwphotos', 1); q.onupgradeneeded = () => q.result.createObjectStore('kv'); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); });
  await new Promise((res, rej) => { const t = db.transaction('kv', 'readwrite'); t.objectStore('kv').put(url, key); t.oncomplete = res; t.onerror = () => rej(t.error); });
  return key + ': saved ' + Math.round(url.length / 1024) + ' KB';
})();
