// Run this in the browser on an AutoTrader.ca search results page.
// It prints one line per used listing in the pipe format carwatch reads:
// year|model|subtitle|price|km|transmission|P or D|province
// It reads only what is on the page. It does not click or submit anything.
(() => {
  const text = (document.querySelector('main') || document.body).innerText;
  const blocks = text.split('Open listing details').slice(1);
  const rows = [];
  for (const block of blocks) {
    const L = block.split('\n').map(s => s.trim()).filter(Boolean);
    const ti = L.findIndex(s => /^(19|20)\d\d [A-Z]/.test(s));
    if (ti < 0) continue;
    if (L.includes('New') && L.includes('vehicle')) continue;
    const title = L[ti];
    const sub = L[ti + 1] && !/^\$/.test(L[ti + 1]) ? L[ti + 1] : '';
    const prices = L.filter(s => /^\$ ?[\d,]+$/.test(s)).map(s => +s.replace(/[^\d]/g, ''));
    const kmLine = L.find(s => /^[\d,]+ km$/.test(s));
    const ki = L.indexOf(kmLine);
    const trans = ki >= 0 ? L[ki + 1] : '';
    const loc = [...L].reverse().find(s => /, ?[A-Z]{2}$/.test(s)) || '';
    const seller = L.includes('Private seller') ? 'P' : 'D';
    rows.push([
      title.slice(0, 4), title.slice(5), sub.slice(0, 40).replace(/\|/g, '/'),
      prices.length ? Math.min(...prices) : '', kmLine ? kmLine.replace(/[^\d]/g, '') : '',
      trans, seller, loc.slice(-2),
    ].join('|'));
  }
  const header = text.split('\n')[0];
  return `# ${header}\n` + rows.join('\n');
})();
