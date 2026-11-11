// Facebook sweep, part 2 of 3. Run after scrolling a search page.
// Stops recording and adds this run's cards to the union kept in the page's
// IndexedDB ("cwstore"), with "search: <query>" in each card's found_by.
// Refuses to merge if the radius chip did not say 500 km. Read only on
// Facebook: it writes only to this browser's own storage.
(async () => {
  clearInterval(window.__gi);
  const db = await new Promise((res) => { const r = indexedDB.open('cwstore', 1); r.onupgradeneeded = () => r.result.createObjectStore('kv'); r.onsuccess = () => res(r.result); });
  const st = (await new Promise((res) => { const g = db.transaction('kv').objectStore('kv').get('state'); g.onsuccess = () => res(g.result); })) || { all: {}, runs: [] };
  const q = new URLSearchParams(location.search).get('query');
  let msg;
  if (!/500 km/.test(window.__chip)) {
    st.runs.push('BAD CHIP ' + window.__chip + ' ' + q);
    msg = 'BAD CHIP ' + window.__chip + ', not merged';
  } else {
    let nw = 0;
    for (const [id, t] of window.__seen) {
      if (!st.all[id]) { st.all[id] = { t, f: [] }; nw++; }
      if (!st.all[id].f.includes('search: ' + q)) st.all[id].f.push('search: ' + q);
    }
    st.runs.push(q + ' ' + window.__chip + ' n=' + window.__seen.size + ' new=' + nw);
    msg = st.runs[st.runs.length - 1] + ' total=' + Object.keys(st.all).length;
  }
  await new Promise((res) => { const tx = db.transaction('kv', 'readwrite'); tx.objectStore('kv').put(st, 'state'); tx.oncomplete = res; });
  return msg;
})();
