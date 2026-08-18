// Mailer — osobna podstrona (patrz frontend/mailer.html). Wszystkie sekcje
// wysyłkowe, dawniej stłoczone w jednym modalu na głównej stronie, żyją tu
// teraz jako zakładki tej samej strony (bez routera/builda — zwykłe
// przełączanie widoczności sekcji w jednym pliku JS).

const toast = document.getElementById("toast");
let toastTimer = null;

function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 4000);
}

function parseRecipients(value) {
  return value.split(",").map((r) => r.trim()).filter(Boolean);
}

// Domyślnie poprzedni miesiąc — to najczęstszy przypadek użycia (raport za
// miesiąc, który się właśnie zamknął).
function defaultMonthValue() {
  const now = new Date();
  now.setDate(1);
  now.setMonth(now.getMonth() - 1);
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

// Zakładki Dział/Kontrahent domyślnie sięgają do BIEŻĄCEGO miesiąca (nie
// poprzedniego jak Pełna paczka/Raport właściciela) — to zapytania typu
// "od kiedyś do dziś", więc "Do" ustawione na miesiąc, który się właśnie
// zamknął, myląco pomijałoby świeże pozycje z bieżącego miesiąca.
function defaultCurrentMonthValue() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function parseMonthInput(inputEl) {
  const value = inputEl.value;
  if (!value) return null;
  const [year, month] = value.split("-").map(Number);
  return { year, month };
}

// Okno "Od"-"Do" (raporty wg działu/kontrahenta) — dwa osobne <input type="month">
// zamiast jednego, żeby dało się objąć więcej niż jeden kalendarzowy
// miesiąc (i przełom roku). Jeden miesiąc to po prostu okno, gdzie "Od" i
// "Do" są takie same.
function parseMonthRange(fromEl, toEl) {
  const from = parseMonthInput(fromEl);
  const to = parseMonthInput(toEl);
  if (!from || !to) return null;
  return { year_from: from.year, month_from: from.month, year_to: to.year, month_to: to.month };
}

function rangeLabel(range) {
  const from = `${range.year_from}-${String(range.month_from).padStart(2, "0")}`;
  const to = `${range.year_to}-${String(range.month_to).padStart(2, "0")}`;
  return from === to ? from : `${from} – ${to}`;
}

// --- Zakładki ---

document.querySelectorAll(".mailer-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".mailer-tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".mailer-tab-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === `tab-${btn.dataset.tab}`);
    });
  });
});

// --- Ustawienia: polityka (okno dni, odbiorcy, odbiorcy właściciela) ---
// Ładowana raz przy starcie strony i współdzielona (currentPolicy) przez
// zakładki Przypomnienia/Pełna paczka/Raport właściciela, które same nie
// edytują odbiorców — tylko z nich korzystają.

let currentPolicy = { days_window: 7, recipients: [], owner_recipients: [] };

const mailerDaysWindow = document.getElementById("mailer-days-window");
const mailerRecipients = document.getElementById("mailer-recipients");
const mailerOwnerRecipients = document.getElementById("mailer-owner-recipients");
const settingsStatus = document.getElementById("settings-status");

async function loadPolicy() {
  const res = await fetch("/api/mailer/policy");
  currentPolicy = await res.json();
  mailerDaysWindow.value = currentPolicy.days_window;
  mailerRecipients.value = currentPolicy.recipients.join(", ");
  mailerOwnerRecipients.value = (currentPolicy.owner_recipients || []).join(", ");
}

async function savePolicy() {
  const days_window = parseInt(mailerDaysWindow.value, 10) || 0;
  const recipients = parseRecipients(mailerRecipients.value);
  const owner_recipients = parseRecipients(mailerOwnerRecipients.value);
  const res = await fetch("/api/mailer/policy", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ days_window, recipients, owner_recipients }),
  });
  if (!res.ok) {
    settingsStatus.textContent = "Błąd zapisu: " + (await res.text());
    return;
  }
  currentPolicy = await res.json();
  settingsStatus.textContent = "Zapisano.";
  showToast("Zapisano ustawienia mailera.");
  await refreshMailerPending();
}

document.getElementById("btn-mailer-save-policy").addEventListener("click", savePolicy);

// --- Przypomnienia o płatnościach ---

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
  const params = new URLSearchParams({ days_window: currentPolicy.days_window });
  const res = await fetch(`/api/mailer/pending?${params}`);
  if (!res.ok) {
    mailerStatus.textContent = "Błąd: " + (await res.text());
    return;
  }
  mailerPendingData = await res.json();
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

document.getElementById("btn-mailer-refresh").addEventListener("click", refreshMailerPending);
btnMailerSend.addEventListener("click", sendSelectedPayments);

// --- Pełna paczka (księgowość) ---

const packageMonth = document.getElementById("package-month");
const packageStatus = document.getElementById("package-status");
const packagePreviewEl = document.getElementById("package-preview");
const btnPackagePreview = document.getElementById("btn-package-preview");
const btnPackageSend = document.getElementById("btn-package-send");
packageMonth.value = defaultMonthValue();

function renderAttachmentsList(container, attachments) {
  if (!attachments.length) return;
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = `Lista załączników PDF (${attachments.length})`;
  details.appendChild(summary);
  const ul = document.createElement("ul");
  for (const name of attachments) {
    const li = document.createElement("li");
    li.textContent = name;
    ul.appendChild(li);
  }
  details.appendChild(ul);
  container.appendChild(details);
}

async function previewPackage() {
  const parsed = parseMonthInput(packageMonth);
  if (!parsed) {
    packageStatus.textContent = "Wybierz miesiąc.";
    return;
  }
  packageStatus.textContent = "Wczytywanie podglądu...";
  btnPackageSend.disabled = true;
  packagePreviewEl.innerHTML = "";

  const params = new URLSearchParams(parsed);
  const res = await fetch(`/api/mailer/monthly/preview?${params}`);
  if (!res.ok) {
    packageStatus.textContent = "Błąd: " + (await res.text());
    return;
  }
  const data = await res.json();

  const p = document.createElement("p");
  p.innerHTML = `Pozycji w podsumowaniu: <strong>${data.invoice_count}</strong> · `
    + `Suma brutto: <strong>${data.total_brutto.toFixed(2)} zł</strong> · `
    + `Załączników PDF: <strong>${data.attachment_count}</strong>`;
  packagePreviewEl.appendChild(p);
  renderAttachmentsList(packagePreviewEl, data.attachments);

  packageStatus.textContent = "";
  btnPackageSend.disabled = data.invoice_count === 0 && data.attachment_count === 0;
}

async function sendPackage() {
  const parsed = parseMonthInput(packageMonth);
  if (!parsed) return;
  const label = `${parsed.year}-${String(parsed.month).padStart(2, "0")}`;
  if (!confirm(`Wysłać pełną paczkę faktur za ${label} do: ${currentPolicy.recipients.join(", ")}?`)) return;

  packageStatus.textContent = "Wysyłanie...";
  btnPackageSend.disabled = true;
  const res = await fetch("/api/mailer/monthly/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parsed),
  });
  const result = await res.json();
  if (!res.ok || !result.sent) {
    packageStatus.textContent = "Błąd wysyłki: " + (result.error || (await res.text()));
    btnPackageSend.disabled = false;
    return;
  }
  packageStatus.textContent = `Wysłano paczkę (${result.count} pozycji w Excelu, ${result.attachment_count} załączników PDF) do: ${result.recipients.join(", ")}.`
    + (result.missing_files.length ? ` Uwaga — brakujące pliki: ${result.missing_files.length}.` : "");
}

btnPackagePreview.addEventListener("click", previewPackage);
btnPackageSend.addEventListener("click", sendPackage);

// --- Raport właściciela ---

const ownerMonth = document.getElementById("owner-month");
const ownerStatus = document.getElementById("owner-status");
const ownerPreviewEl = document.getElementById("owner-preview");
const btnOwnerPreview = document.getElementById("btn-owner-preview");
const btnOwnerSend = document.getElementById("btn-owner-send");
ownerMonth.value = defaultMonthValue();

function renderDzialBreakdown(breakdown) {
  const table = document.createElement("table");
  table.className = "dzial-breakdown-table";
  table.innerHTML = "<thead><tr><th>Dział</th><th>Liczba faktur</th><th>Suma brutto</th></tr></thead>";
  const tbody = document.createElement("tbody");
  for (const row of breakdown) {
    const tr = document.createElement("tr");
    const cells = [row.dzial, String(row.count), row.brutto.toFixed(2) + " zł"];
    cells.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

async function previewOwner() {
  const parsed = parseMonthInput(ownerMonth);
  if (!parsed) {
    ownerStatus.textContent = "Wybierz miesiąc.";
    return;
  }
  ownerStatus.textContent = "Wczytywanie podglądu...";
  btnOwnerSend.disabled = true;
  ownerPreviewEl.innerHTML = "";

  const params = new URLSearchParams(parsed);
  const res = await fetch(`/api/mailer/monthly/owner-preview?${params}`);
  if (!res.ok) {
    ownerStatus.textContent = "Błąd: " + (await res.text());
    return;
  }
  const data = await res.json();

  const p = document.createElement("p");
  p.innerHTML = `Pozycji łącznie: <strong>${data.invoice_count}</strong> · `
    + `Suma brutto: <strong>${data.total_brutto.toFixed(2)} zł</strong>`;
  ownerPreviewEl.appendChild(p);
  if (data.breakdown.length) {
    ownerPreviewEl.appendChild(renderDzialBreakdown(data.breakdown));
  }

  ownerStatus.textContent = "";
  btnOwnerSend.disabled = data.invoice_count === 0;
}

async function sendOwner() {
  const parsed = parseMonthInput(ownerMonth);
  if (!parsed) return;
  const label = `${parsed.year}-${String(parsed.month).padStart(2, "0")}`;
  if (!confirm(`Wysłać raport właściciela (sam Excel) za ${label} do: ${(currentPolicy.owner_recipients || []).join(", ")}?`)) return;

  ownerStatus.textContent = "Wysyłanie...";
  btnOwnerSend.disabled = true;
  const res = await fetch("/api/mailer/monthly/owner-send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parsed),
  });
  const result = await res.json();
  if (!res.ok || !result.sent) {
    ownerStatus.textContent = "Błąd wysyłki: " + (result.error || (await res.text()));
    btnOwnerSend.disabled = false;
    return;
  }
  ownerStatus.textContent = `Wysłano raport właściciela (${result.count} pozycji) do: ${result.recipients.join(", ")}.`;
}

btnOwnerPreview.addEventListener("click", previewOwner);
btnOwnerSend.addEventListener("click", sendOwner);

// --- Raport wg działu ---

const dzialMonthFrom = document.getElementById("dzial-month-from");
const dzialMonthTo = document.getElementById("dzial-month-to");
const dzialSelect = document.getElementById("dzial-select");
const dzialWithPdfs = document.getElementById("dzial-with-pdfs");
const dzialRecipients = document.getElementById("dzial-recipients");
const dzialStatus = document.getElementById("dzial-status");
const dzialPreviewEl = document.getElementById("dzial-preview");
const btnDzialPreview = document.getElementById("btn-dzial-preview");
const btnDzialSend = document.getElementById("btn-dzial-send");
dzialMonthFrom.value = defaultCurrentMonthValue();
dzialMonthTo.value = defaultCurrentMonthValue();

async function loadDzialOptions() {
  const range = parseMonthRange(dzialMonthFrom, dzialMonthTo);
  dzialSelect.innerHTML = "";
  btnDzialSend.disabled = true;
  if (!range) return;
  const params = new URLSearchParams(range);
  const res = await fetch(`/api/mailer/monthly/dzialy?${params}`);
  if (!res.ok) {
    dzialStatus.textContent = "Błąd: " + (await res.text());
    return;
  }
  const dzialy = await res.json();
  if (dzialy.length === 0) {
    dzialSelect.innerHTML = '<option value="">— brak danych za to okno —</option>';
    return;
  }
  for (const d of dzialy) {
    const opt = document.createElement("option");
    opt.value = d;
    opt.textContent = d;
    dzialSelect.appendChild(opt);
  }
}

async function previewDzial() {
  const range = parseMonthRange(dzialMonthFrom, dzialMonthTo);
  const dzial = dzialSelect.value;
  if (!range || !dzial) {
    dzialStatus.textContent = "Wybierz okno i dział.";
    return;
  }
  dzialStatus.textContent = "Wczytywanie podglądu...";
  btnDzialSend.disabled = true;
  dzialPreviewEl.innerHTML = "";

  const params = new URLSearchParams({ ...range, dzial, with_pdfs: dzialWithPdfs.checked });
  const res = await fetch(`/api/mailer/monthly/dzial-preview?${params}`);
  if (!res.ok) {
    dzialStatus.textContent = "Błąd: " + (await res.text());
    return;
  }
  const data = await res.json();

  const p = document.createElement("p");
  p.innerHTML = `Pozycji: <strong>${data.invoice_count}</strong> · `
    + `Suma brutto: <strong>${data.total_brutto.toFixed(2)} zł</strong> · `
    + `Załączników PDF: <strong>${data.attachment_count}</strong>`;
  dzialPreviewEl.appendChild(p);
  renderAttachmentsList(dzialPreviewEl, data.attachments);

  dzialStatus.textContent = "";
  btnDzialSend.disabled = data.invoice_count === 0;
}

async function sendDzial() {
  const range = parseMonthRange(dzialMonthFrom, dzialMonthTo);
  const dzial = dzialSelect.value;
  const recipients = parseRecipients(dzialRecipients.value);
  if (!range || !dzial) return;
  if (recipients.length === 0) {
    dzialStatus.textContent = "Podaj przynajmniej jednego odbiorcę.";
    return;
  }
  const withPdfs = dzialWithPdfs.checked;
  if (!confirm(`Wysłać raport działu „${dzial}” za ${rangeLabel(range)} (${withPdfs ? "z PDF-ami" : "bez PDF-ów"}) do: ${recipients.join(", ")}?`)) return;

  dzialStatus.textContent = "Wysyłanie...";
  btnDzialSend.disabled = true;
  const res = await fetch("/api/mailer/monthly/dzial-send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...range, dzial, recipients, with_pdfs: withPdfs }),
  });
  const result = await res.json();
  if (!res.ok || !result.sent) {
    dzialStatus.textContent = "Błąd wysyłki: " + (result.error || (await res.text()));
    btnDzialSend.disabled = false;
    return;
  }
  dzialStatus.textContent = `Wysłano raport działu (${result.count} pozycji, ${result.attachment_count} załączników PDF) do: ${result.recipients.join(", ")}.`;
}

dzialMonthFrom.addEventListener("change", loadDzialOptions);
dzialMonthTo.addEventListener("change", loadDzialOptions);
btnDzialPreview.addEventListener("click", previewDzial);
btnDzialSend.addEventListener("click", sendDzial);

// --- Raport wg kontrahenta ---

const kontrahentMonthFrom = document.getElementById("kontrahent-month-from");
const kontrahentMonthTo = document.getElementById("kontrahent-month-to");
const kontrahentFilter = document.getElementById("kontrahent-filter");
const kontrahentSelect = document.getElementById("kontrahent-select");
const kontrahentWithPdfs = document.getElementById("kontrahent-with-pdfs");
const kontrahentRecipients = document.getElementById("kontrahent-recipients");
const kontrahentStatus = document.getElementById("kontrahent-status");
const kontrahentPreviewEl = document.getElementById("kontrahent-preview");
const btnKontrahentPreview = document.getElementById("btn-kontrahent-preview");
const btnKontrahentSend = document.getElementById("btn-kontrahent-send");
kontrahentMonthFrom.value = defaultCurrentMonthValue();
kontrahentMonthTo.value = defaultCurrentMonthValue();

let kontrahenciAll = [];

function renderKontrahentOptions() {
  const filter = kontrahentFilter.value.trim().toLowerCase();
  const filtered = filter ? kontrahenciAll.filter((k) => k.toLowerCase().includes(filter)) : kontrahenciAll;
  kontrahentSelect.innerHTML = "";
  if (filtered.length === 0) {
    kontrahentSelect.innerHTML = '<option value="">— brak dopasowań —</option>';
    return;
  }
  for (const k of filtered) {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = k;
    kontrahentSelect.appendChild(opt);
  }
}

async function loadKontrahentOptions() {
  const range = parseMonthRange(kontrahentMonthFrom, kontrahentMonthTo);
  kontrahenciAll = [];
  kontrahentSelect.innerHTML = "";
  btnKontrahentSend.disabled = true;
  if (!range) return;
  const params = new URLSearchParams(range);
  const res = await fetch(`/api/mailer/monthly/kontrahenci?${params}`);
  if (!res.ok) {
    kontrahentStatus.textContent = "Błąd: " + (await res.text());
    return;
  }
  kontrahenciAll = await res.json();
  if (kontrahenciAll.length === 0) {
    kontrahentSelect.innerHTML = '<option value="">— brak danych za to okno —</option>';
    return;
  }
  renderKontrahentOptions();
}

async function previewKontrahent() {
  const range = parseMonthRange(kontrahentMonthFrom, kontrahentMonthTo);
  const kontrahent = kontrahentSelect.value;
  if (!range || !kontrahent) {
    kontrahentStatus.textContent = "Wybierz okno i kontrahenta.";
    return;
  }
  kontrahentStatus.textContent = "Wczytywanie podglądu...";
  btnKontrahentSend.disabled = true;
  kontrahentPreviewEl.innerHTML = "";

  const params = new URLSearchParams({ ...range, kontrahent, with_pdfs: kontrahentWithPdfs.checked });
  const res = await fetch(`/api/mailer/monthly/kontrahent-preview?${params}`);
  if (!res.ok) {
    kontrahentStatus.textContent = "Błąd: " + (await res.text());
    return;
  }
  const data = await res.json();

  const p = document.createElement("p");
  p.innerHTML = `Pozycji: <strong>${data.invoice_count}</strong> · `
    + `Suma brutto: <strong>${data.total_brutto.toFixed(2)} zł</strong> · `
    + `Załączników PDF: <strong>${data.attachment_count}</strong>`;
  kontrahentPreviewEl.appendChild(p);
  renderAttachmentsList(kontrahentPreviewEl, data.attachments);

  kontrahentStatus.textContent = "";
  btnKontrahentSend.disabled = data.invoice_count === 0;
}

async function sendKontrahent() {
  const range = parseMonthRange(kontrahentMonthFrom, kontrahentMonthTo);
  const kontrahent = kontrahentSelect.value;
  const recipients = parseRecipients(kontrahentRecipients.value);
  if (!range || !kontrahent) return;
  if (recipients.length === 0) {
    kontrahentStatus.textContent = "Podaj przynajmniej jednego odbiorcę.";
    return;
  }
  const withPdfs = kontrahentWithPdfs.checked;
  if (!confirm(`Wysłać raport kontrahenta „${kontrahent}” za ${rangeLabel(range)} (${withPdfs ? "z PDF-ami" : "bez PDF-ów"}) do: ${recipients.join(", ")}?`)) return;

  kontrahentStatus.textContent = "Wysyłanie...";
  btnKontrahentSend.disabled = true;
  const res = await fetch("/api/mailer/monthly/kontrahent-send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...range, kontrahent, recipients, with_pdfs: withPdfs }),
  });
  const result = await res.json();
  if (!res.ok || !result.sent) {
    kontrahentStatus.textContent = "Błąd wysyłki: " + (result.error || (await res.text()));
    btnKontrahentSend.disabled = false;
    return;
  }
  kontrahentStatus.textContent = `Wysłano raport kontrahenta (${result.count} pozycji, ${result.attachment_count} załączników PDF) do: ${result.recipients.join(", ")}.`;
}

kontrahentMonthFrom.addEventListener("change", loadKontrahentOptions);
kontrahentMonthTo.addEventListener("change", loadKontrahentOptions);
kontrahentFilter.addEventListener("input", renderKontrahentOptions);
btnKontrahentPreview.addEventListener("click", previewKontrahent);
btnKontrahentSend.addEventListener("click", sendKontrahent);

// --- Start ---

(async function init() {
  await loadPolicy();
  await refreshMailerPending();
  await loadMailerHistory();
  await loadDzialOptions();
  await loadKontrahentOptions();
})();
