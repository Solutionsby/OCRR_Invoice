const listEl = document.getElementById("invoice-list");
const emptyState = document.getElementById("empty-state");
const review = document.getElementById("review");
const form = document.getElementById("review-form");
const pdfFrame = document.getElementById("pdf-frame");
const ambiguousBadge = document.getElementById("ambiguous-badge");
const statusMsg = document.getElementById("status-msg");
const toast = document.getElementById("toast");
const paymentDateLabel = document.getElementById("payment-date-label");
const duplicateWarning = document.getElementById("duplicate-warning");

let currentFlow = "ksef";
let currentId = null;
let toastTimer = null;

function field(name) {
  return form.elements.namedItem(name);
}

function apiUrl(path) {
  return `/api/${currentFlow}${path}`;
}

// Osobny, chwilowy komunikat (a nie #status-msg) — bo status-msg jest
// czyszczony przy przełączeniu na kolejną fakturę (patrz selectInvoice),
// a wynik zapisu ma być widoczny nawet po tym przejściu.
function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 4000);
}

// Ostrzeżenie o możliwym duplikacie — analyze_* (core/ksef.py, core/inne.py,
// core/euro.py) sprawdza numer faktury w obu tabelach SQL przy każdym
// wczytaniu propozycji, żeby złapać przypadek ponownego przetworzenia tej
// samej faktury (np. powtórnie ściągniętej z KSeF) zanim dojdzie do zapisu.
function showDuplicateWarning(matches) {
  if (!matches.length) {
    duplicateWarning.classList.add("hidden");
    duplicateWarning.textContent = "";
    return;
  }
  duplicateWarning.innerHTML = "";
  const title = document.createElement("strong");
  title.textContent = "⚠️ Możliwy duplikat — numer faktury już jest w bazie:";
  duplicateWarning.appendChild(title);
  for (const m of matches) {
    const line = document.createElement("div");
    line.textContent = `${m.tabela}: ${m.kontrahent}` + (m.plik ? ` — ${m.plik.split("/").pop()}` : "");
    duplicateWarning.appendChild(line);
  }
  duplicateWarning.classList.remove("hidden");
}

function applyFlowVisibility() {
  document.querySelectorAll("[data-flow]").forEach((el) => {
    const flows = el.dataset.flow.split(" ");
    el.classList.toggle("hidden", !flows.includes(currentFlow));
  });
  paymentDateLabel.classList.remove("hidden");
}

async function loadList() {
  const res = await fetch(apiUrl("/invoices"));
  const items = await res.json();

  listEl.innerHTML = "";
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = item.file_name;
    li.dataset.id = item.id;
    li.className = item.id === currentId ? "active" : "";
    li.addEventListener("click", () => selectInvoice(item.id));
    listEl.appendChild(li);
  }

  if (items.length === 0) {
    currentId = null;
    review.classList.add("hidden");
    emptyState.textContent = "Brak faktur do przetworzenia w tym przepływie.";
    emptyState.classList.remove("hidden");
  }

  return items;
}

async function selectInvoice(id) {
  currentId = id;
  statusMsg.textContent = "";
  showDuplicateWarning([]);
  emptyState.classList.add("hidden");
  review.classList.remove("hidden");
  [...listEl.children].forEach((li) => li.classList.toggle("active", li.dataset.id === id));

  pdfFrame.src = apiUrl(`/invoices/${encodeURIComponent(id)}/file`);

  const res = await fetch(apiUrl(`/invoices/${encodeURIComponent(id)}`));

  // Odczyt OCR trwa różnie długo dla różnych faktur, więc odpowiedzi mogą
  // wrócić w innej kolejności niż kliknięcia na liście. Jeśli w międzyczasie
  // wybrano już inną fakturę (albo zmieniono zakładkę), ta (nieaktualna)
  // odpowiedź jest ignorowana.
  if (currentId !== id) return;

  if (!res.ok) {
    statusMsg.textContent = "Błąd odczytu faktury: " + (await res.text());
    return;
  }
  const data = await res.json();
  if (currentId !== id) return;

  showDuplicateWarning(data.duplicate_matches || []);

  field("firm_name").value = data.firm_name;
  field("invoice_number").value = data.invoice_number;
  field("invoice_date").value = data.invoice_date;
  field("payment_date").value = data.payment_date;
  field("kategoria").value = data.kategoria || "";
  paymentDateLabel.classList.remove("hidden");

  if (currentFlow === "ksef") {
    field("payment_status").value = data.payment_status;
    field("payment_form").value = data.payment_form;
    field("brutto").value = data.brutto;
    field("scanned_firm").value = data.scanned_firm;
    ambiguousBadge.classList.toggle("hidden", !data.payment_status_ambiguous);
    return;
  }

  field("dzial").value = data.dzial || "";
  // "Opłacona" nie ma tu żadnej sensownej podpowiedzi (te faktury nie mają
  // etykiety statusu płatności) — operator musi wybrać jawnie, tak jak
  // dawny main_inne.py/main_euro.py zawsze pytał wprost.
  field("oplacona").value = "";

  if (currentFlow === "euro") {
    field("eur_netto_display").value = data.eur_netto;
    field("eur_vat_display").value = data.eur_vat;
    // suggested_rate bywa null, gdy NBP nie odpowiedziało — wtedy pole
    // zostaje puste i operator musi wpisać kurs ręcznie (required w HTML).
    field("kurs_eur").value = data.suggested_rate ?? "";
    recomputeFromRate();
  } else {
    field("netto").value = data.netto;
    field("vat").value = data.vat;
    field("brutto_display").value = data.brutto;
  }
}

function collectFormData(action) {
  const base = {
    firm_name: field("firm_name").value.trim(),
    invoice_number: field("invoice_number").value.trim(),
    invoice_date: field("invoice_date").value.trim(),
    kategoria: field("kategoria").value.trim(),
    action,
  };

  if (currentFlow === "ksef") {
    return {
      ...base,
      payment_date: field("payment_date").value.trim() || "brak",
      payment_status: field("payment_status").value.trim(),
      payment_form: field("payment_form").value.trim(),
      brutto: parseFloat(String(field("brutto").value).replace(",", ".")) || 0,
      scanned_firm: field("scanned_firm").value,
    };
  }

  const oplacona = field("oplacona").value === "tak";
  const shared = {
    ...base,
    dzial: field("dzial").value.trim(),
    oplacona,
    // Termin jest bez znaczenia dla opłaconej faktury — tak jak w dawnym
    // main_inne.py/main_euro.py, gdzie pole "pay_date" było wtedy pomijane.
    payment_date: oplacona ? "brak" : (field("payment_date").value.trim() || "brak"),
  };

  if (currentFlow === "euro") {
    return {
      ...shared,
      netto: parseFloat(String(field("netto").value).replace(",", ".")) || 0,
      vat: parseFloat(String(field("vat").value).replace(",", ".")) || 0,
      eur_netto: parseFloat(String(field("eur_netto_display").value).replace(",", ".")) || 0,
      eur_vat: parseFloat(String(field("eur_vat_display").value).replace(",", ".")) || 0,
      kurs_eur: parseFloat(String(field("kurs_eur").value).replace(",", ".")) || 0,
    };
  }

  return {
    ...shared,
    netto: parseFloat(String(field("netto").value).replace(",", ".")) || 0,
    vat: parseFloat(String(field("vat").value).replace(",", ".")) || 0,
  };
}

async function selectNextAfter(processedId) {
  const items = await loadList();
  const next = items.find((i) => i.id !== processedId) || items[0];
  if (next) {
    await selectInvoice(next.id);
  }
}

async function finalizeInvoice(action) {
  if (!currentId) return;
  const processedId = currentId;
  statusMsg.textContent = "Zapisywanie...";

  const res = await fetch(apiUrl(`/invoices/${encodeURIComponent(processedId)}/finalize`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectFormData(action)),
  });

  if (!res.ok) {
    const detail = await res.text();
    statusMsg.textContent = "Błąd: " + detail;
    showToast("Błąd zapisu: " + detail, true);
    return;
  }

  const result = await res.json();
  const suffix = result.saved_to_payments
    ? " — dodano do bazy płatności SQL"
    : " — bez zapisu do bazy płatności (opłacona albo brak terminu)";
  showToast(`Zapisano: ${result.target_path}${suffix}`);

  await selectNextAfter(processedId);
}

function skipInvoice() {
  if (!currentId) return;
  const items = [...listEl.children];
  const idx = items.findIndex((li) => li.dataset.id === currentId);
  const next = items[idx + 1] || items[idx - 1];
  if (next) {
    selectInvoice(next.dataset.id);
  } else {
    currentId = null;
    review.classList.add("hidden");
    emptyState.textContent = "Brak faktur do przetworzenia w tym przepływie.";
    emptyState.classList.remove("hidden");
  }
}

async function setFlow(flow) {
  if (flow === currentFlow) return;
  currentFlow = flow;
  currentId = null;
  document.querySelectorAll(".flow-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.flowTab === flow);
  });
  applyFlowVisibility();
  statusMsg.textContent = "";
  review.classList.add("hidden");

  const items = await loadList();
  if (items.length > 0) selectInvoice(items[0].id);
}

document.querySelectorAll(".flow-tab").forEach((btn) => {
  btn.addEventListener("click", () => setFlow(btn.dataset.flowTab));
});

function recomputeBruttoDisplay() {
  const netto = parseFloat(String(field("netto").value).replace(",", ".")) || 0;
  const vat = parseFloat(String(field("vat").value).replace(",", ".")) || 0;
  field("brutto_display").value = Math.round((netto + vat) * 100) / 100;
}
field("netto").addEventListener("input", recomputeBruttoDisplay);
field("vat").addEventListener("input", recomputeBruttoDisplay);

// Tylko dla EURO: przelicza netto/VAT PLN z kwot EUR i kursu. Operator może
// potem i tak ręcznie poprawić netto/VAT PLN bezpośrednio (tak jak w dawnym
// main_euro.py przy korekcie) — to tylko wygodny punkt startowy.
function recomputeFromRate() {
  const rate = parseFloat(String(field("kurs_eur").value).replace(",", ".")) || 0;
  const eurNetto = parseFloat(String(field("eur_netto_display").value).replace(",", ".")) || 0;
  const eurVat = parseFloat(String(field("eur_vat_display").value).replace(",", ".")) || 0;
  field("netto").value = Math.round(eurNetto * rate * 100) / 100;
  field("vat").value = Math.round(eurVat * rate * 100) / 100;
  recomputeBruttoDisplay();
}
field("kurs_eur").addEventListener("input", recomputeFromRate);

document.getElementById("btn-skip").addEventListener("click", skipInvoice);
document.getElementById("btn-queue").addEventListener("click", () => finalizeInvoice("k"));
form.addEventListener("submit", (e) => {
  e.preventDefault();
  finalizeInvoice("t");
});

applyFlowVisibility();
loadList().then((items) => {
  if (items.length > 0) selectInvoice(items[0].id);
});

// --- Szukaj w bazie (niezależne od aktualnie przeglądanej faktury/zakładki) ---

const searchModal = document.getElementById("search-modal");
const searchResultsEl = document.getElementById("search-results");
const searchNumer = document.getElementById("search-numer");
const searchKontrahent = document.getElementById("search-kontrahent");

function openSearch() {
  searchModal.classList.remove("hidden");
  searchNumer.focus();
}

function closeSearch() {
  searchModal.classList.add("hidden");
}

const SEARCH_COLUMNS = [
  { key: "tabela", label: "Tabela" },
  { key: "numer_faktury", label: "Numer" },
  { key: "kontrahent", label: "Kontrahent" },
  { key: "data", label: "Data" },
  { key: "kwota", label: "Kwota" },
  { key: "plik", label: "Plik" },
];

let searchResultsData = [];
let searchSort = { column: null, direction: 1 };

// "plik" pokazuje/sortuje po samej nazwie pliku (nie pełnej ścieżce) — to,
// co operator faktycznie widzi w komórce.
function searchCellValue(item, column) {
  if (column === "plik") return item.plik ? item.plik.split("/").pop() : "";
  if (column === "kwota") return item.kwota != null ? item.kwota : null;
  return item[column] || "";
}

function sortedSearchResults() {
  if (!searchSort.column) return searchResultsData;
  const { column, direction } = searchSort;
  return [...searchResultsData].sort((a, b) => {
    const va = searchCellValue(a, column);
    const vb = searchCellValue(b, column);
    if (column === "kwota") {
      return ((va ?? -Infinity) - (vb ?? -Infinity)) * direction;
    }
    return String(va).localeCompare(String(vb), "pl", { sensitivity: "base", numeric: true }) * direction;
  });
}

function renderSearchResults(items) {
  searchResultsData = items;
  searchResultsEl.innerHTML = "";
  if (items.length === 0) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "Brak wyników.";
    searchResultsEl.appendChild(p);
    return;
  }

  const table = document.createElement("table");
  table.className = "search-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const col of SEARCH_COLUMNS) {
    const th = document.createElement("th");
    th.className = "sortable";
    th.dataset.column = col.key;
    let label = col.label;
    if (searchSort.column === col.key) {
      label += searchSort.direction === 1 ? " ▲" : " ▼";
    }
    th.textContent = label;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const item of sortedSearchResults()) {
    const tr = document.createElement("tr");
    for (const col of SEARCH_COLUMNS) {
      const td = document.createElement("td");
      const value = searchCellValue(item, col.key);
      td.textContent = value != null ? value : "";
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  searchResultsEl.appendChild(table);
}

// Delegacja na stały kontener zamiast podpinania listenera do każdego <th> z
// osobna — działa też po przebudowaniu tabeli przy kolejnym wyszukiwaniu.
searchResultsEl.addEventListener("click", (e) => {
  const th = e.target.closest("th[data-column]");
  if (!th) return;
  const column = th.dataset.column;
  if (searchSort.column === column) {
    searchSort.direction *= -1;
  } else {
    searchSort.column = column;
    searchSort.direction = 1;
  }
  renderSearchResults(searchResultsData);
});

async function runSearch() {
  const numer = searchNumer.value.trim();
  const kontrahent = searchKontrahent.value.trim();
  if (!numer && !kontrahent) {
    renderSearchResults([]);
    searchResultsEl.querySelector(".muted").textContent = "Podaj numer faktury lub kontrahenta.";
    return;
  }
  searchResultsEl.innerHTML = '<p class="muted">Szukam...</p>';
  const params = new URLSearchParams();
  if (numer) params.set("numer", numer);
  if (kontrahent) params.set("kontrahent", kontrahent);
  const res = await fetch(`/api/search?${params}`);
  if (!res.ok) {
    searchResultsEl.innerHTML = `<p class="muted">Błąd: ${await res.text()}</p>`;
    return;
  }
  renderSearchResults(await res.json());
}

document.getElementById("btn-search-toggle").addEventListener("click", openSearch);
document.getElementById("btn-search-close").addEventListener("click", closeSearch);
document.getElementById("search-backdrop").addEventListener("click", closeSearch);
document.getElementById("btn-search-run").addEventListener("click", runSearch);
[searchNumer, searchKontrahent].forEach((input) => {
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runSearch();
  });
});

// --- Wysyłka przypomnień o płatnościach (polityka + podgląd + trigger) ---

const mailerModal = document.getElementById("mailer-modal");
const mailerDaysWindow = document.getElementById("mailer-days-window");
const mailerRecipients = document.getElementById("mailer-recipients");
const mailerStatus = document.getElementById("mailer-status");
const mailerPendingEl = document.getElementById("mailer-pending");
const mailerHistoryEl = document.getElementById("mailer-history");
const mailerSelectedCount = document.getElementById("mailer-selected-count");
const btnMailerSend = document.getElementById("btn-mailer-send");

const PENDING_COLUMNS = [
  { key: "payment_date", label: "Termin" },
  { key: "firm_name", label: "Kontrahent" },
  { key: "invoice_number", label: "Numer" },
  { key: "brutto", label: "Kwota", numeric: true },
];

let mailerPendingData = [];
let mailerSelectedIds = new Set();
let mailerSort = { column: "payment_date", direction: 1 };

async function openMailer() {
  mailerModal.classList.remove("hidden");
  mailerStatus.textContent = "";
  await loadMailerPolicy();
  await refreshMailerPending();
  await loadMailerHistory();
}

function closeMailer() {
  mailerModal.classList.add("hidden");
}

async function loadMailerPolicy() {
  const res = await fetch("/api/mailer/policy");
  const policy = await res.json();
  mailerDaysWindow.value = policy.days_window;
  mailerRecipients.value = policy.recipients.join(", ");
}

async function saveMailerPolicy() {
  const days_window = parseInt(mailerDaysWindow.value, 10) || 0;
  const recipients = mailerRecipients.value
    .split(",")
    .map((r) => r.trim())
    .filter(Boolean);
  const res = await fetch("/api/mailer/policy", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ days_window, recipients }),
  });
  if (!res.ok) {
    mailerStatus.textContent = "Błąd zapisu polityki: " + (await res.text());
    return;
  }
  mailerStatus.textContent = "Zapisano politykę.";
  await refreshMailerPending();
}

function updateMailerSelectedCount() {
  mailerSelectedCount.textContent = mailerSelectedIds.size;
  btnMailerSend.disabled = mailerSelectedIds.size === 0;
}

function sortedMailerPending() {
  const { column, direction } = mailerSort;
  return [...mailerPendingData].sort((a, b) => {
    const va = a[column];
    const vb = b[column];
    if (typeof va === "number" && typeof vb === "number") {
      return (va - vb) * direction;
    }
    return String(va || "").localeCompare(String(vb || ""), "pl", { sensitivity: "base", numeric: true }) * direction;
  });
}

function renderMailerPending() {
  mailerPendingEl.innerHTML = "";
  if (mailerPendingData.length === 0) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "Brak faktur pasujących do bieżącego okna dni.";
    mailerPendingEl.appendChild(p);
    updateMailerSelectedCount();
    return;
  }

  const table = document.createElement("table");
  table.className = "pending-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");

  const selectAllTh = document.createElement("th");
  const selectAllCb = document.createElement("input");
  selectAllCb.type = "checkbox";
  selectAllCb.checked = mailerSelectedIds.size === mailerPendingData.length;
  selectAllCb.addEventListener("change", () => {
    mailerSelectedIds = selectAllCb.checked ? new Set(mailerPendingData.map((p) => p.id)) : new Set();
    renderMailerPending();
  });
  selectAllTh.appendChild(selectAllCb);
  headRow.appendChild(selectAllTh);

  for (const col of PENDING_COLUMNS) {
    const th = document.createElement("th");
    th.className = "sortable" + (col.numeric ? " numeric" : "");
    th.dataset.column = col.key;
    let label = col.label;
    if (mailerSort.column === col.key) {
      label += mailerSort.direction === 1 ? " ▲" : " ▼";
    }
    th.textContent = label;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const item of sortedMailerPending()) {
    const tr = document.createElement("tr");

    const cbTd = document.createElement("td");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = mailerSelectedIds.has(item.id);
    cb.addEventListener("change", () => {
      if (cb.checked) mailerSelectedIds.add(item.id);
      else mailerSelectedIds.delete(item.id);
      updateMailerSelectedCount();
    });
    cbTd.appendChild(cb);
    tr.appendChild(cbTd);

    for (const col of PENDING_COLUMNS) {
      const td = document.createElement("td");
      if (col.numeric) td.classList.add("numeric");
      const value = item[col.key];
      td.textContent = col.numeric ? Number(value).toFixed(2) + " zł" : value;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  mailerPendingEl.appendChild(table);
  updateMailerSelectedCount();
}

mailerPendingEl.addEventListener("click", (e) => {
  const th = e.target.closest("th[data-column]");
  if (!th) return;
  const column = th.dataset.column;
  if (mailerSort.column === column) {
    mailerSort.direction *= -1;
  } else {
    mailerSort.column = column;
    mailerSort.direction = 1;
  }
  renderMailerPending();
});

async function refreshMailerPending() {
  const daysWindow = parseInt(mailerDaysWindow.value, 10);
  const params = new URLSearchParams();
  if (!Number.isNaN(daysWindow)) params.set("days_window", daysWindow);
  const res = await fetch(`/api/mailer/pending?${params}`);
  if (!res.ok) {
    mailerStatus.textContent = "Błąd: " + (await res.text());
    return;
  }
  mailerPendingData = await res.json();
  // Domyślnie zaznaczamy wszystko — operator odznacza to, czego NIE chce
  // wysłać teraz (najczęstszy przypadek to "wyślij wszystko z listy").
  mailerSelectedIds = new Set(mailerPendingData.map((p) => p.id));
  renderMailerPending();
}

async function loadMailerHistory() {
  const res = await fetch("/api/mailer/history?limit=20");
  const items = await res.json();
  mailerHistoryEl.innerHTML = "";
  if (items.length === 0) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "Brak historii wysyłek.";
    mailerHistoryEl.appendChild(p);
    return;
  }
  const table = document.createElement("table");
  table.className = "pending-table";
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr><th>Wysłano</th><th>Kontrahent</th><th>Numer</th><th class=\"numeric\">Kwota</th></tr>";
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  for (const item of items) {
    const tr = document.createElement("tr");
    const cells = [item.sent_at || "", item.firm_name, item.invoice_number, Number(item.brutto).toFixed(2) + " zł"];
    cells.forEach((value, i) => {
      const td = document.createElement("td");
      if (i === 3) td.classList.add("numeric");
      td.textContent = value;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  mailerHistoryEl.appendChild(table);
}

async function sendSelectedPayments() {
  if (mailerSelectedIds.size === 0) return;
  mailerStatus.textContent = "Wysyłanie...";
  btnMailerSend.disabled = true;
  const res = await fetch("/api/mailer/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [...mailerSelectedIds] }),
  });
  const result = await res.json();
  if (!res.ok || !result.sent) {
    mailerStatus.textContent = "Błąd wysyłki: " + (result.error || (await res.text()));
    updateMailerSelectedCount();
    return;
  }
  mailerStatus.textContent = `Wysłano raport z ${result.count} fakturami do: ${result.recipients.join(", ")}.`
    + (result.missing_files.length ? ` Uwaga — brakujące pliki: ${result.missing_files.length}.` : "");
  await refreshMailerPending();
  await loadMailerHistory();
}

document.getElementById("btn-mailer-toggle").addEventListener("click", openMailer);
document.getElementById("btn-mailer-close").addEventListener("click", closeMailer);
document.getElementById("mailer-backdrop").addEventListener("click", closeMailer);
document.getElementById("btn-mailer-save-policy").addEventListener("click", saveMailerPolicy);
document.getElementById("btn-mailer-refresh").addEventListener("click", refreshMailerPending);
document.getElementById("btn-mailer-send").addEventListener("click", sendSelectedPayments);
