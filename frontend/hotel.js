// Hotel — osobna podstrona (patrz frontend/hotel.html). Wydzielona z
// analityka.js, bo to inne źródło danych (MongoDB, nie SQL Server) i inny
// właściciel tematu. Wykresy przez Chart.js (CDN, patrz <head> hotel.html).
// Self-contained JS bez buildu, tak jak analityka.js/mailer.js.

const toast = document.getElementById("toast");
let toastTimer = null;

function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 4000);
}

const PALETTE = [
  "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
  "#0891b2", "#db2777", "#65a30d", "#ea580c", "#4338ca",
  "#0d9488", "#be123c", "#a16207",
];

function fmtMoney(v) {
  return `${v.toLocaleString("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} zł`;
}

function monthValue(year, month) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function defaultRange() {
  const now = new Date();
  const toYear = now.getFullYear();
  const toMonth = now.getMonth() + 1;
  const idx = toYear * 12 + (toMonth - 1) - 23;
  const fromYear = Math.floor(idx / 12);
  const fromMonth = (idx % 12) + 1;
  return { fromYear, fromMonth, toYear, toMonth };
}

function parseMonthInput(inputEl) {
  const value = inputEl.value;
  if (!value) return null;
  const [year, month] = value.split("-").map(Number);
  return { year, month };
}

function parseMonthRange(fromEl, toEl) {
  const from = parseMonthInput(fromEl);
  const to = parseMonthInput(toEl);
  if (!from || !to) return null;
  return { year_from: from.year, month_from: from.month, year_to: to.year, month_to: to.month };
}

function monthLabel(year, month) {
  return `${String(month).padStart(2, "0")}/${year}`;
}

function qs(params) {
  return Object.entries(params)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");
}

// --- Zakładki ---
// Hotel (domyślna aktywna zakładka) ładuje się eagerly w sekcji Start;
// Płatności/Rekordy leniwie, przy pierwszym kliknięciu — tak samo jak w
// analityka.js.
const TAB_LOADERS = {
  platnosci: () => loadPlatnosci(),
  rekordy: () => loadRekordy(),
};
const loadedTabs = new Set();

document.querySelectorAll(".mailer-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".mailer-tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".mailer-tab-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === `tab-${btn.dataset.tab}`);
    });
    const tab = btn.dataset.tab;
    if (!loadedTabs.has(tab) && TAB_LOADERS[tab]) {
      loadedTabs.add(tab);
      TAB_LOADERS[tab]();
    }
  });
});

// --- Hotel (sprzedaż wg pozycji, źródło: MongoDB/system hotelowy) ---

const hotelFromEl = document.getElementById("hotel-month-from");
const hotelToEl = document.getElementById("hotel-month-to");
const hotelStatus = document.getElementById("hotel-status");
const hotelKategoriaSelect = document.getElementById("hotel-kategoria-select");
const hotelCategoryTableEl = document.getElementById("hotel-category-table");
const hotelBreakdownTableEl = document.getElementById("hotel-breakdown-table");
let hotelTrendChart = null;
let hotelBreakdownChart = null;
let hotelBreakdownData = null; // ostatnia odpowiedź /sales-breakdown, do filtrowania po kategorii bez ponownego zapytania

// Dane w MongoDB sięgają dopiero od 2026-01 (cała historia, jaka jest) —
// domyślny "Od" ustawiony wprost na to, zamiast generycznych "ostatnich 24
// miesięcy" (które w większości byłyby puste, sprzed początku tych danych).
const HOTEL_DATA_START_YEAR = 2026, HOTEL_DATA_START_MONTH = 1;

async function loadHotel() {
  const range = parseMonthRange(hotelFromEl, hotelToEl);
  if (!range) return;
  hotelStatus.textContent = "Ładowanie...";
  try {
    const [trend, breakdown] = await Promise.all([
      fetch(`/api/hotel/sales-trend?${qs(range)}`).then((r) => r.json()),
      fetch(`/api/hotel/sales-breakdown?${qs(range)}`).then((r) => r.json()),
    ]);
    hotelStatus.textContent = `Suma brutto: ${fmtMoney(trend.total_brutto)} · Paragonów/faktur: ${trend.total_count}`;

    const labels = trend.points.map((p) => monthLabel(p.year, p.month));
    const values = trend.points.map((p) => p.brutto);
    if (hotelTrendChart) hotelTrendChart.destroy();
    hotelTrendChart = new Chart(document.getElementById("hotel-trend-chart"), {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Sprzedaż brutto",
          data: values,
          borderColor: PALETTE[0],
          backgroundColor: PALETTE[0] + "33",
          fill: true,
          tension: 0.2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });

    hotelBreakdownData = breakdown;
    const selected = hotelKategoriaSelect.value;
    hotelKategoriaSelect.innerHTML = '<option value="">— wszystkie —</option>' + breakdown.categories
      .map((c) => `<option value="${c.kategoria}">${c.kategoria} (${fmtMoney(c.brutto)})</option>`).join("");
    hotelKategoriaSelect.value = breakdown.categories.some((c) => c.kategoria === selected) ? selected : "";

    renderHotelCategoryTable(breakdown.categories);
    renderHotelBreakdown(breakdown, hotelKategoriaSelect.value);
  } catch (e) {
    hotelStatus.textContent = "Błąd ładowania danych.";
    showToast("Nie udało się pobrać danych sprzedażowych hotelu.", true);
  }
}

function renderHotelCategoryTable(categories) {
  hotelCategoryTableEl.innerHTML = "";
  const table = document.createElement("table");
  table.className = "dzial-breakdown-table";
  table.innerHTML = "<thead><tr><th>Kategoria</th><th>Paragonów/faktur</th><th>Suma brutto</th><th>%</th></tr></thead>";
  const tbody = document.createElement("tbody");
  categories.forEach((c) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${c.kategoria}</td><td>${c.count}</td><td>${fmtMoney(c.brutto)}</td><td>${c.pct}%</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  hotelCategoryTableEl.appendChild(table);
}

function renderHotelBreakdown(breakdown, kategoria) {
  const items = kategoria ? breakdown.items.filter((it) => it.kategoria === kategoria) : breakdown.items;

  const chartItems = items.slice(0, 15);
  if (hotelBreakdownChart) hotelBreakdownChart.destroy();
  hotelBreakdownChart = new Chart(document.getElementById("hotel-breakdown-chart"), {
    type: "bar",
    data: {
      labels: chartItems.map((it) => it.nazwa),
      datasets: [{ label: "Suma brutto", data: chartItems.map((it) => it.brutto), backgroundColor: PALETTE[4] }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true } },
    },
  });

  hotelBreakdownTableEl.innerHTML = "";
  const table = document.createElement("table");
  table.className = "dzial-breakdown-table";
  table.innerHTML = "<thead><tr><th>Pozycja</th><th>Kategoria</th><th>Paragonów/faktur</th><th>Suma brutto</th><th>%</th></tr></thead>";
  const tbody = document.createElement("tbody");
  items.forEach((it) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${it.nazwa}</td><td>${it.kategoria}</td><td>${it.count}</td><td>${fmtMoney(it.brutto)}</td><td>${it.pct}%</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  hotelBreakdownTableEl.appendChild(table);
}

document.getElementById("btn-hotel-refresh").addEventListener("click", loadHotel);
hotelKategoriaSelect.addEventListener("change", () => {
  if (hotelBreakdownData) renderHotelBreakdown(hotelBreakdownData, hotelKategoriaSelect.value);
});

// --- Płatności (rozbicie sprzedaży hotelu wg formy płatności) ---

const platnosciFromEl = document.getElementById("platnosci-month-from");
const platnosciToEl = document.getElementById("platnosci-month-to");
const platnosciStatus = document.getElementById("platnosci-status");
const platnosciTotalsTableEl = document.getElementById("platnosci-totals-table");
const platnosciMonthsTableEl = document.getElementById("platnosci-months-table");
let platnosciChart = null;

async function loadPlatnosci() {
  const range = parseMonthRange(platnosciFromEl, platnosciToEl);
  if (!range) return;
  platnosciStatus.textContent = "Ładowanie...";
  try {
    const data = await fetch(`/api/hotel/payment-methods?${qs(range)}`).then((r) => r.json());
    platnosciStatus.textContent = `Suma brutto w zakresie: ${fmtMoney(data.total_brutto)}`;

    // Kolejność/kolory metod ustalone wg totali (malejąco) — spójne między wykresem a tabelami.
    const methodNames = data.totals.map((t) => t.method);
    const colorOf = (i) => PALETTE[i % PALETTE.length];

    const labels = data.months.map((m) => monthLabel(m.year, m.month));
    if (platnosciChart) platnosciChart.destroy();
    platnosciChart = new Chart(document.getElementById("platnosci-chart"), {
      type: "bar",
      data: {
        labels,
        datasets: methodNames.map((method, i) => ({
          label: method,
          data: data.months.map((m) => m.methods[method]?.brutto || 0),
          backgroundColor: colorOf(i),
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
      },
    });

    renderPlatnosciTotalsTable(data.totals);
    renderPlatnosciMonthsTable(data.months, methodNames);
  } catch (e) {
    platnosciStatus.textContent = "Błąd ładowania danych.";
    showToast("Nie udało się pobrać danych o płatnościach.", true);
  }
}

function renderPlatnosciTotalsTable(totals) {
  platnosciTotalsTableEl.innerHTML = "";
  const table = document.createElement("table");
  table.className = "dzial-breakdown-table";
  table.innerHTML = "<thead><tr><th>Forma płatności</th><th>Liczba</th><th>Suma brutto</th><th>%</th></tr></thead>";
  const tbody = document.createElement("tbody");
  totals.forEach((t) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${t.method}</td><td>${t.count}</td><td>${fmtMoney(t.brutto)}</td><td>${t.pct}%</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  platnosciTotalsTableEl.appendChild(table);
}

function renderPlatnosciMonthsTable(months, methodNames) {
  platnosciMonthsTableEl.innerHTML = "";
  const table = document.createElement("table");
  table.className = "rekordy-table";
  table.innerHTML = `<thead><tr><th>Miesiąc</th>${methodNames.map((m) => `<th>${m}</th>`).join("")}<th>Razem</th></tr></thead>`;
  const tbody = document.createElement("tbody");
  months.forEach((m) => {
    const tr = document.createElement("tr");
    const cells = methodNames.map((name) => `<td>${fmtMoney(m.methods[name]?.brutto || 0)}</td>`).join("");
    tr.innerHTML = `<td>${monthLabel(m.year, m.month)}</td>${cells}<td>${fmtMoney(m.total_brutto)}</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  platnosciMonthsTableEl.appendChild(table);
}

document.getElementById("btn-platnosci-refresh").addEventListener("click", loadPlatnosci);

// --- Rekordy (przegląd surowych wierszy z MongoDB + ręczne usuwanie duplikatów) ---

const rekordyFromEl = document.getElementById("rekordy-month-from");
const rekordyToEl = document.getElementById("rekordy-month-to");
const rekordySearchEl = document.getElementById("rekordy-search");
const rekordyOnlyDuplicatesEl = document.getElementById("rekordy-only-duplicates");
const rekordyStatus = document.getElementById("rekordy-status");
const rekordyTableEl = document.getElementById("rekordy-table");
let rekordyData = null; // ostatnia odpowiedź /records, do filtrowania bez ponownego zapytania

async function loadRekordy() {
  const range = parseMonthRange(rekordyFromEl, rekordyToEl);
  if (!range) return;
  rekordyStatus.textContent = "Ładowanie...";
  try {
    rekordyData = await fetch(`/api/hotel/records?${qs(range)}`).then((r) => r.json());
    renderRekordyTable();
  } catch (e) {
    rekordyStatus.textContent = "Błąd ładowania danych.";
    showToast("Nie udało się pobrać rekordów.", true);
  }
}

function renderRekordyTable() {
  if (!rekordyData) return;
  const search = rekordySearchEl.value.trim().toLowerCase();
  const onlyDuplicates = rekordyOnlyDuplicatesEl.checked;
  const rows = rekordyData.records.filter((r) => {
    if (onlyDuplicates && !r.is_duplicate) return false;
    if (search && !r.nrParagonu.toLowerCase().includes(search) && !r.numerFaktury.toLowerCase().includes(search) && !r.nazwa.toLowerCase().includes(search)) return false;
    return true;
  });

  rekordyStatus.textContent = `Wszystkich rekordów w oknie: ${rekordyData.total_count} · Oznaczonych jako duplikat: ${rekordyData.duplicate_count} · Wyświetlonych: ${rows.length}`;

  rekordyTableEl.innerHTML = "";
  const table = document.createElement("table");
  table.className = "rekordy-table";
  table.innerHTML = "<thead><tr><th>Data wystawienia</th><th>Nr paragonu</th><th>Nr faktury</th><th>Nazwa</th><th>Brutto</th><th>Netto</th><th>Typ</th><th>Forma płatności</th><th>Zsynchronizowano</th><th>Status</th><th></th></tr></thead>";
  const tbody = document.createElement("tbody");
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    tr.className = r.is_duplicate ? "is-duplicate" : "";
    tr.innerHTML = `
      <td>${r.dataWystawienia.slice(0, 10)}</td>
      <td>${r.nrParagonu || "—"}</td>
      <td>${r.numerFaktury || "—"}</td>
      <td>${r.nazwa}</td>
      <td>${fmtMoney(r.kwotaBrutto)}</td>
      <td>${fmtMoney(r.kwotaNetto)}</td>
      <td>${r.typDokumentu}</td>
      <td>${r.formaPatnosci || "—"}</td>
      <td>${r.createdAt.slice(0, 19).replace("T", " ")}</td>
      <td>${r.is_duplicate ? '<span class="badge">Duplikat</span>' : ""}</td>
      <td><button type="button" class="btn-danger" data-id="${r.id}">Usuń</button></td>
    `;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  rekordyTableEl.appendChild(table);

  rekordyTableEl.querySelectorAll(".btn-danger").forEach((btn) => {
    btn.addEventListener("click", () => deleteRekord(btn.dataset.id));
  });
}

async function deleteRekord(id) {
  const record = rekordyData?.records.find((r) => r.id === id);
  const label = record ? `${record.dataWystawienia.slice(0, 10)} · ${record.nrParagonu || record.numerFaktury || "(bez nr)"} · ${record.nazwa} · ${fmtMoney(record.kwotaBrutto)}` : id;
  if (!confirm(`Usunąć ten rekord z bazy? Operacja jest nieodwracalna.\n\n${label}`)) return;
  try {
    const res = await fetch(`/api/hotel/records/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error();
    rekordyData.records = rekordyData.records.filter((r) => r.id !== id);
    rekordyData.total_count -= 1;
    if (record?.is_duplicate) rekordyData.duplicate_count -= 1;
    renderRekordyTable();
    showToast("Rekord usunięty.");
  } catch (e) {
    showToast("Nie udało się usunąć rekordu.", true);
  }
}

document.getElementById("btn-rekordy-refresh").addEventListener("click", loadRekordy);
rekordySearchEl.addEventListener("input", () => renderRekordyTable());
rekordyOnlyDuplicatesEl.addEventListener("change", () => renderRekordyTable());

// --- Start ---

hotelFromEl.value = monthValue(HOTEL_DATA_START_YEAR, HOTEL_DATA_START_MONTH);
hotelToEl.value = monthValue(defaultRange().toYear, defaultRange().toMonth);
platnosciFromEl.value = monthValue(HOTEL_DATA_START_YEAR, HOTEL_DATA_START_MONTH);
platnosciToEl.value = monthValue(defaultRange().toYear, defaultRange().toMonth);
rekordyFromEl.value = monthValue(HOTEL_DATA_START_YEAR, HOTEL_DATA_START_MONTH);
rekordyToEl.value = monthValue(defaultRange().toYear, defaultRange().toMonth);

// Tylko Hotel (domyślna aktywna zakładka) ładuje się od razu — Płatności i
// Rekordy leniwie, przy pierwszym kliknięciu (patrz TAB_LOADERS wyżej).
loadHotel();
