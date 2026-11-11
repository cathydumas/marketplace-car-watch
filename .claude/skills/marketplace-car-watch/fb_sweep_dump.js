// Facebook sweep, part 3 of 3. Run once, after every search has run twice.
// Returns the union as lines: id | card text | found_by (comma separated),
// keeping only cards that name a GR86, 86, GT86, BRZ, FR-S or Scion.
// To clear the union for the next day, run it again with reset = true
// after the lines are saved. Read only on Facebook.
(async () => {
  const reset = false;
  const db = await new Promise((res) => { const r = indexedDB.open('cwstore', 1); r.onupgradeneeded = () => r.result.createObjectStore('kv'); r.onsuccess = () => res(r.result); });
  const st = (await new Promise((res) => { const g = db.transaction('kv').objectStore('kv').get('state'); g.onsuccess = () => res(g.result); })) || { all: {}, runs: [] };
  if (reset) { await new Promise((res) => { const tx = db.transaction('kv', 'readwrite'); tx.objectStore('kv').delete('state'); tx.oncomplete = res; }); return 'cleared'; }
  const rows = Object.entries(st.all)
    .filter(([, o]) => /(brz|\b86\b|gr ?86|gt ?86|fr-?s\b|scion)/i.test(o.t))
    .map(([id, o]) => id + ' | ' + o.t.replace(/^Just listed \| /, '') + ' | ' + o.f.map((x) => x.replace('search: ', '')).join(','));
  return st.runs.length + ' runs\n' + st.runs.join('\n') + '\n---\n' + rows.join('\n');
})();
