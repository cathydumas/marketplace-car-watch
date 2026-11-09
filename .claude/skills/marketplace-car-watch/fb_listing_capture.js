// Run on one Facebook Marketplace listing page. Returns the listing text
// (cut before the seller section), up to 10 photos for the photo check, and
// the main photo for the dashboard. The output is padded so the tool saves
// it to a file. Read only.
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  await sleep(3000);
  const id = location.pathname.match(/item\/(\d+)/)[1];
  const t = document.body.innerText;
  const end = Math.min(...["Today's picks", 'Related searches', 'Seller information', 'Seller details']
    .map((s) => { const i = t.indexOf(s); return i < 0 ? 1e9 : i; }));
  const text = t.slice(0, Math.min(end, 4000));
  const srcs = [...new Set([...document.querySelectorAll('img[alt^="Product photo of"]')].map((i) => i.src))].slice(0, 10);
  const shrink = async (u, W, q) => {
    const b = await (await fetch(u, { mode: 'cors' })).blob();
    const bm = await createImageBitmap(b);
    const c = document.createElement('canvas');
    c.width = W; c.height = Math.round(bm.height * W / bm.width);
    c.getContext('2d').drawImage(bm, 0, 0, c.width, c.height);
    return c.toDataURL('image/jpeg', q);
  };
  const photos = [];
  for (const u of srcs) { try { photos.push(await shrink(u, 380, 0.66)); } catch (e) {} }
  let main = '';
  if (srcs[0]) { try { main = await shrink(srcs[0], 640, 0.72); } catch (e) {} }
  return JSON.stringify({ id, text, photos, main }) + ' '.repeat(100000);
})();
