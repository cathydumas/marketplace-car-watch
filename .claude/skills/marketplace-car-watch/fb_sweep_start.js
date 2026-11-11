// Facebook sweep, part 1 of 3. Run right after the search page loads.
// Checks the radius chip and starts recording every listing card the page
// shows, every 0.4 s, into window.__seen. Returns the chip text.
// Works when the browser pane is hidden. Read only.
(async () => {
  await new Promise((r) => setTimeout(r, 3000));
  window.__chip = (document.body.innerText.match(/Within \d+ ?(km|mi)/i) || ['NO CHIP'])[0];
  window.__seen = new Map();
  const grab = () => document.querySelectorAll('a[href*="/marketplace/item/"]').forEach((a) => {
    const m = a.href.match(/marketplace\/item\/(\d+)/);
    if (m && !window.__seen.has(m[1])) window.__seen.set(m[1], a.innerText.replace(/\s*\n\s*/g, ' | ').slice(0, 160));
  });
  grab();
  clearInterval(window.__gi);
  window.__gi = setInterval(grab, 400);
  return window.__chip;
})();
