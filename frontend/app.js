async function api(url, options={}) {
  const r = await fetch(url, {headers: {"Content-Type":"application/json"}, ...options});
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function runScan() {
  setStatus("Scanning repository…");
  try {
    const d = await api("/api/scan", {method:"POST"});
    document.querySelector("#routeCount").textContent = d.count;
    document.querySelector("#status").textContent = "Scan complete";
    document.querySelector("#routes").className = "routes";
    document.querySelector("#routes").innerHTML = d.routes.map(r =>
      `<div class="route"><span class="method ${r.method.toLowerCase()}">${r.method}</span><b>${esc(r.path)}</b><small>${esc(r.file)}:${r.line} · ${esc(r.function)}</small></div>`
    ).join("") || "No routes detected.";
    loadAudit();
  } catch(e) { setStatus("Scan failed"); alert(e.message); }
}
async function compare() {
  setStatus("Comparing code with OpenAPI…");
  try {
    const d = await api("/api/compare", {method:"POST"});
    const c = d.comparison;
    document.querySelector("#newCount").textContent = c.added.length;
    document.querySelector("#changes").innerHTML =
      `<div class="change-summary"><div><b>${c.added.length}</b><small>Added</small></div><div><b>${c.removed.length}</b><small>Removed</small></div><div><b>${c.modified.length}</b><small>Modified</small></div><div><b>${c.unchanged}</b><small>Unchanged</small></div></div>` +
      `<h3>New endpoints</h3>` +
      (c.added.map(r => `<div class="change added"><b>+ ${r.method} ${esc(r.path)}</b><small>${esc(r.file)}:${r.line}</small></div>`).join("") || "<p>No new endpoints.</p>") +
      `<h3>Removed endpoints</h3>` +
      (c.removed.map(r => `<div class="change removed"><b>- ${r.method} ${esc(r.path)}</b></div>`).join("") || "<p>No removed endpoints.</p>");
    document.querySelector("#confidence").textContent = "Analysis complete";
    loadAudit();
  } catch(e) { alert(e.message); }
}
async function generate() {
  setStatus("Agent generating OpenAPI…");
  try {
    const d = await api("/api/generate", {method:"POST"});
    document.querySelector("#valid").textContent = d.validation.valid ? "PASS" : "FAIL";
    document.querySelector("#status").textContent = d.validation.valid ? "Generated + validated" : "Validation failed";
    loadAudit();
    alert("OpenAPI generated successfully. Open Swagger Docs to view it.");
  } catch(e) { document.querySelector("#valid").textContent = "FAIL"; alert(e.message); }
}
async function loadAudit() {
  const d = await api("/api/audit");
  document.querySelector("#audit").innerHTML = d.map(x =>
    `<div class="log"><span>${esc(x.time)}</span><b>${esc(x.event)}</b><code>${esc(JSON.stringify(x.details))}</code></div>`
  ).join("") || "No events yet.";
}
function setStatus(s){document.querySelector("#status").textContent=s;}
loadAudit();
