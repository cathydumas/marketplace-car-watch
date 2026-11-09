// Run on one AutoTrader.ca listing page. Returns the VIN and, when the
// dealer pays for it, a free CARFAX report link, as one JSON line:
//   {"vin": "...", "carfax_url": "...", "carfax_mode": "..."}
// carfax_url is left empty when the report is buy-only. Read only.
(() => {
  const h = document.documentElement.innerHTML.replace(/\\u0026/g, '&').replace(/\\"/g, '"');
  const mode = (h.match(/"carfaxMode"\s*:\s*"([^"]*)"/) || [])[1] || '';
  const url = (h.match(/"reportUrlEn"\s*:\s*"([^"]*)"/) || [])[1] || '';
  let vin = (url.match(/[?&]vin=([A-HJ-NPR-Z0-9]{17})/i) || [])[1] || '';
  if (!vin) vin = (h.match(/"vin"\s*:\s*"([A-HJ-NPR-Z0-9]{17})"/i) || [])[1] || '';
  const free = url && !/buy/i.test(mode);
  return JSON.stringify({ vin: vin.toUpperCase(), carfax_url: free ? url : '', carfax_mode: mode });
})();
