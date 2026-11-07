// Run this in the browser on a Facebook Marketplace search results page.
// Facebook removes results from the page as you scroll past them, so this
// script records every listing while it scrolls, not only at the end.
// It prints one line per listing: id | card text. It only reads the page.
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  await sleep(3000);
  const seen = new Map();
  const grab = () => document.querySelectorAll('a[href*="/marketplace/item/"]').forEach((a) => {
    const m = a.href.match(/marketplace\/item\/(\d+)/);
    if (m && !seen.has(m[1])) seen.set(m[1], a.innerText.replace(/\s*\n\s*/g, ' | ').slice(0, 160));
  });
  window.scrollTo(0, 0);
  grab();
  let still = 0, last = 0;
  for (let i = 0; i < 60 && still < 4; i++) {
    window.scrollBy(0, 600);
    document.querySelectorAll('div').forEach((el) => {
      if (el.scrollHeight > el.clientHeight + 200 && /auto|scroll/.test(getComputedStyle(el).overflowY)) el.scrollTop += 600;
    });
    await sleep(900);
    grab();
    still = seen.size === last ? still + 1 : 0;
    last = seen.size;
  }
  return [...seen].map(([id, text]) => id + ' | ' + text).join('\n');
})();
