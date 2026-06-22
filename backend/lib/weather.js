// Hong Kong weather via HKO Open Data. Network-gated and HONEST: if the fetch
// fails or no network is available, returns available:false — never fabricated
// weather. The HKO endpoint is the official current-weather ("rhrread") feed.

const HKO_URL = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=en";

function pickHKTemp(data) {
  const recs = (data.temperature && data.temperature.data) || [];
  // Prefer Hong Kong Observatory station, else the first record.
  const hko = recs.find((r) => /observatory/i.test(r.place)) || recs[0];
  return hko ? hko.value : null;
}

export async function getHongKongWeather({ fetchImpl } = {}) {
  const f = fetchImpl || (typeof fetch !== "undefined" ? fetch : null);
  const base = { source: "Hong Kong Observatory (rhrread)", available: false, updatedAt: new Date().toISOString() };
  if (!f) return { ...base, error: "no network fetcher available in this environment" };
  try {
    const resp = await f(HKO_URL, { signal: AbortSignal.timeout ? AbortSignal.timeout(5000) : undefined });
    if (!resp.ok) return { ...base, error: `HKO responded ${resp.status}` };
    const data = await resp.json();
    const rainfallMax = Math.max(0, ...((data.rainfall && data.rainfall.data) || []).map((r) => r.max || 0));
    return {
      source: base.source,
      available: true,
      temperature_c: pickHKTemp(data),
      humidity_percent: (data.humidity && data.humidity.data && data.humidity.data[0] && data.humidity.data[0].value) || null,
      rainfall_mm_max: rainfallMax,
      warnings: data.warningMessage || [],
      icon: (data.icon && data.icon[0]) || null,
      observed: data.updateTime || null,
      updatedAt: new Date().toISOString(),
    };
  } catch (err) {
    return { ...base, error: `weather fetch failed: ${String(err && err.message)}` };
  }
}

export async function getRainfall(opts) {
  const w = await getHongKongWeather(opts);
  return w.available ? { available: true, rainfall_mm_max: w.rainfall_mm_max, observed: w.observed } : w;
}
export async function getAlerts(opts) {
  const w = await getHongKongWeather(opts);
  return w.available ? { available: true, warnings: w.warnings } : w;
}
