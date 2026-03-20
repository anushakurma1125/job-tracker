let allJobs = [];
let allResumes = [];
let activeFilter = "";
let sortCol = "applied_date";
let sortAsc = false;
let searchQuery = "";
let dateFrom = "";
let dateTo = "";

document.addEventListener("DOMContentLoaded", () => {
    // Clean up any stale modal backdrops
    document.querySelectorAll(".modal-backdrop").forEach(el => el.remove());
    document.body.classList.remove("modal-open");
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("padding-right");

    loadJobs();
    loadResumes();
    checkEmailConnection();

    // Handle OAuth redirect hash
    if (window.location.hash === "#settings-connected") {
        window.location.hash = "";
        setTimeout(() => {
            switchSection("settings", document.querySelector('.sidebar-link[data-section="settings"]'));
        }, 300);
    }

    // Stat card filters
    document.querySelectorAll(".stat-card").forEach(card => {
        card.style.cursor = "pointer";
        card.addEventListener("click", () => {
            const filter = card.dataset.filter;
            activeFilter = activeFilter === filter ? "" : filter;
            document.querySelectorAll(".stat-card").forEach(c => c.classList.remove("border-primary"));
            if (activeFilter) card.classList.add("border-primary");
            renderJobs();
        });
    });

    // Search input
    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            searchQuery = e.target.value.toLowerCase();
            renderJobs();
        });
    }

    // Date range filter
    const dateFromInput = document.getElementById("dateFrom");
    const dateToInput = document.getElementById("dateTo");
    if (dateFromInput) {
        dateFromInput.addEventListener("change", (e) => {
            dateFrom = e.target.value;
            toggleClearDateBtn();
            renderJobs();
        });
    }
    if (dateToInput) {
        dateToInput.addEventListener("change", (e) => {
            dateTo = e.target.value;
            toggleClearDateBtn();
            renderJobs();
        });
    }

    // Sortable headers
    document.querySelectorAll("th[data-sort]").forEach(th => {
        th.style.cursor = "pointer";
        th.addEventListener("click", () => {
            const col = th.dataset.sort;
            if (sortCol === col) {
                sortAsc = !sortAsc;
            } else {
                sortCol = col;
                sortAsc = true;
            }
            updateSortIcons();
            renderJobs();
        });
    });
});

// ── Sidebar Toggle ──

function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    sidebar.classList.toggle("collapsed");
    // Persist preference
    localStorage.setItem("sidebarCollapsed", sidebar.classList.contains("collapsed"));
}

// Restore sidebar state on load
(function restoreSidebar() {
    if (localStorage.getItem("sidebarCollapsed") === "true") {
        const sidebar = document.getElementById("sidebar");
        if (sidebar) sidebar.classList.add("collapsed");
    }
})();

// ── Section Navigation ──

function switchSection(section, linkEl) {
    // Update sidebar active state
    document.querySelectorAll(".sidebar-link[data-section]").forEach(link => {
        link.classList.remove("active");
    });
    if (linkEl) linkEl.classList.add("active");

    // Show/hide content sections
    document.querySelectorAll(".content-section").forEach(sec => {
        sec.classList.remove("active");
    });
    const target = document.getElementById("section-" + section);
    if (target) target.classList.add("active");

    // Load data for the section
    if (section === "resumes") {
        loadResumes();
    } else if (section === "settings") {
        loadSettings();
        loadScanLogs();
    }
}

function updateSortIcons() {
    document.querySelectorAll("th[data-sort]").forEach(th => {
        const icon = th.querySelector(".sort-icon");
        if (!icon) return;
        if (th.dataset.sort === sortCol) {
            icon.className = sortAsc ? "bi bi-caret-up-fill sort-icon ms-1" : "bi bi-caret-down-fill sort-icon ms-1";
        } else {
            icon.className = "bi bi-caret-up-fill sort-icon ms-1 text-muted opacity-25";
        }
    });
}

async function loadJobs() {
    const res = await fetch("/api/jobs");
    allJobs = await res.json();
    updateStats();
    renderJobs();
    updateSortIcons();
    // Update sidebar badge
    const badge = document.getElementById("sidebarJobCount");
    if (badge) badge.textContent = allJobs.length;
}

function updateStats(jobs) {
    // If no jobs passed, use allJobs (initial load)
    const dataset = jobs || allJobs;
    document.getElementById("statTotal").textContent = dataset.length;
    const counts = { Applied: 0, Interviewing: 0, Offer: 0, Rejected: 0 };
    dataset.forEach(j => { if (counts[j.status] !== undefined) counts[j.status]++; });
    document.getElementById("statApplied").textContent = counts.Applied;
    document.getElementById("statInterviewing").textContent = counts.Interviewing;
    document.getElementById("statOffer").textContent = counts.Offer;
    document.getElementById("statRejected").textContent = counts.Rejected;
}

function getOrdinalSuffix(n) {
    if (n > 3 && n < 21) return "th";
    switch (n % 10) {
        case 1: return "st";
        case 2: return "nd";
        case 3: return "rd";
        default: return "th";
    }
}

function formatDate(d) {
    if (!d) return "";
    // Parse dates in either "YYYY-MM-DD" or "DD-MM-YYYY" format → "13th Mar, 2026"
    const dateStr = d.toString().split(" ")[0];
    // Support both "/" and "-" separators
    const parts = dateStr.split(/[-\/]/);
    if (parts.length !== 3) return dateStr;

    let day, monthIdx, year;
    if (parts[0].length === 4) {
        // YYYY-MM-DD format
        year = parts[0];
        monthIdx = parseInt(parts[1], 10) - 1;
        day = parseInt(parts[2], 10);
    } else {
        // DD-MM-YYYY format
        day = parseInt(parts[0], 10);
        monthIdx = parseInt(parts[1], 10) - 1;
        year = parts[2];
    }

    if (isNaN(day) || isNaN(monthIdx) || monthIdx < 0 || monthIdx > 11) return dateStr;
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${day}${getOrdinalSuffix(day)} ${months[monthIdx]}, ${year}`;
}

function clearDateFilter() {
    dateFrom = "";
    dateTo = "";
    const fromEl = document.getElementById("dateFrom");
    const toEl = document.getElementById("dateTo");
    if (fromEl) fromEl.value = "";
    if (toEl) toEl.value = "";
    toggleClearDateBtn();
    renderJobs();
}

function toggleClearDateBtn() {
    const btn = document.getElementById("clearDateFilter");
    if (btn) {
        btn.style.display = (dateFrom || dateTo) ? "inline-block" : "none";
    }
}

function normalizeDate(d) {
    // Convert "DD-MM-YYYY" or "YYYY-MM-DD" to "YYYY-MM-DD" for comparison
    if (!d) return "";
    const s = d.toString().split(" ")[0];
    const parts = s.split(/[-\/]/);
    if (parts.length !== 3) return s;
    if (parts[0].length === 4) return s; // Already YYYY-MM-DD
    // DD-MM-YYYY → YYYY-MM-DD
    return `${parts[2]}-${parts[1].padStart(2, "0")}-${parts[0].padStart(2, "0")}`;
}

function getBaseFilteredJobs() {
    // Apply search + date filters (but NOT status filter).
    // Used for dynamic stat card counts.
    let jobs = allJobs;

    // Search filter
    if (searchQuery) {
        jobs = jobs.filter(j => {
            const text = [
                j.applied_date, j.company, j.role, j.posted_on,
                j.status, j.comment, j.visa_answer, j.link
            ].filter(Boolean).join(" ").toLowerCase();
            return text.includes(searchQuery);
        });
    }

    // Date range filter (applied_date)
    if (dateFrom || dateTo) {
        jobs = jobs.filter(j => {
            const jobDate = normalizeDate(j.applied_date);
            if (!jobDate) return false;
            if (dateFrom && jobDate < dateFrom) return false;
            if (dateTo && jobDate > dateTo) return false;
            return true;
        });
    }

    return jobs;
}

function getFilteredSortedJobs() {
    // Start from base-filtered jobs (search + date), then add status + sort
    let jobs = getBaseFilteredJobs();

    // Status filter (stat cards)
    if (activeFilter) {
        jobs = jobs.filter(j => j.status === activeFilter);
    }

    // Sort
    if (sortCol) {
        jobs = [...jobs].sort((a, b) => {
            let va = (a[sortCol] || "").toString().toLowerCase();
            let vb = (b[sortCol] || "").toString().toLowerCase();
            if (va < vb) return sortAsc ? -1 : 1;
            if (va > vb) return sortAsc ? 1 : -1;
            return 0;
        });
    }

    return jobs;
}

function renderJobs() {
    const tbody = document.getElementById("jobsTableBody");

    // Recompute stats from base-filtered jobs (search + date, no status)
    const baseJobs = getBaseFilteredJobs();
    updateStats(baseJobs);

    const filtered = getFilteredSortedJobs();

    // Update count badge
    const countEl = document.getElementById("filteredCount");
    const hasFilters = searchQuery || activeFilter || dateFrom || dateTo;
    if (countEl) {
        countEl.textContent = hasFilters
            ? `Showing ${filtered.length} of ${allJobs.length}`
            : `${allJobs.length} jobs`;
    }

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center py-5 text-muted">
                    <i class="bi bi-briefcase" style="font-size: 2rem;"></i>
                    <p class="mt-2 mb-0">${(activeFilter || searchQuery) ? 'No matching jobs found.' : 'No jobs tracked yet. Click "Add Job" to get started.'}</p>
                </td>
            </tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(job => `
        <tr>
            <td class="editable-cell" data-id="${job.id}" data-field="applied_date" data-type="date">${formatDate(job.applied_date) || "\u2014"}</td>
            <td class="editable-cell fw-semibold" data-id="${job.id}" data-field="company">${escapeHtml(job.company) || "\u2014"}</td>
            <td class="editable-cell" data-id="${job.id}" data-field="role">${escapeHtml(job.role) || "\u2014"}</td>
            <td class="editable-cell" data-id="${job.id}" data-field="posted_on" data-type="date">${formatDate(job.posted_on) || "\u2014"}</td>
            <td>
                <select class="form-select form-select-sm status-select ${statusClass(job.status)}"
                        onchange="updateStatus(${job.id}, this.value)">
                    ${["Applied", "Waiting for Referral", "Interviewing", "Offer", "Rejected", "Withdrawn", "Saved"]
                        .map(s => `<option value="${s}" ${s === job.status ? "selected" : ""}>${s}</option>`)
                        .join("")}
                </select>
            </td>
            <td>
                <input type="text" class="form-control form-control-sm comment-input"
                       value="${escapeHtml(job.comment || '')}"
                       placeholder="Add comment..."
                       onchange="updateField(${job.id}, 'comment', this.value)">
            </td>
            <td>
                <select class="form-select form-select-sm visa-select"
                        onchange="updateField(${job.id}, 'visa_answer', this.value)">
                    ${["", "Yes", "No", "Other"]
                        .map(v => `<option value="${v}" ${v === (job.visa_answer || '') ? "selected" : ""}>${v || "\u2014"}</option>`)
                        .join("")}
                </select>
            </td>
            <td>
                ${job.link ? `<a href="${escapeHtml(job.link)}" target="_blank" rel="noopener" class="text-decoration-none small">
                    <i class="bi bi-box-arrow-up-right me-1"></i>View
                </a>` : "\u2014"}
            </td>
            <td class="text-end text-nowrap">
                <button class="btn btn-sm btn-outline-secondary me-1" onclick="showDetails(${job.id})" title="Details">
                    <i class="bi bi-eye"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteJob(${job.id})" title="Delete">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>
    `).join("");

    // Attach click-to-edit handlers
    tbody.querySelectorAll(".editable-cell").forEach(cell => {
        cell.addEventListener("click", startEditing);
    });
}

function startEditing(e) {
    const cell = e.currentTarget;
    if (cell.querySelector("input")) return; // Already editing

    const id = cell.dataset.id;
    const field = cell.dataset.field;
    const type = cell.dataset.type || "text";
    const currentVal = cell.textContent.trim() === "\u2014" ? "" : cell.textContent.trim();

    const input = document.createElement("input");
    input.type = type;
    input.value = currentVal;
    input.className = "form-control form-control-sm edit-inline";

    cell.textContent = "";
    cell.appendChild(input);
    input.focus();
    input.select();

    const save = async () => {
        const newVal = input.value.trim();
        await updateField(id, field, newVal);
        // Update local data so we don't refetch
        const job = allJobs.find(j => j.id == id);
        if (job) job[field] = newVal;
        cell.textContent = (field === "applied_date" || field === "posted_on") ? (formatDate(newVal) || "\u2014") : (newVal || "\u2014");
    };

    input.addEventListener("blur", save);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { input.blur(); }
        if (e.key === "Escape") {
            cell.textContent = currentVal || "\u2014";
        }
    });
}

function statusClass(status) {
    const map = {
        Applied: "status-applied",
        Interviewing: "status-interviewing",
        Offer: "status-offer",
        Rejected: "status-rejected",
        "Waiting for Referral": "status-referral",
        Withdrawn: "status-withdrawn",
        Saved: "status-saved",
    };
    return map[status] || "";
}

async function addJob() {
    const linkInput = document.getElementById("jobLink");
    const link = linkInput.value.trim();
    if (!link) return;

    const btn = document.getElementById("submitJobBtn");
    const statusEl = document.getElementById("extractionStatus");
    const errorEl = document.getElementById("extractionError");

    btn.disabled = true;
    statusEl.classList.remove("d-none");
    errorEl.classList.add("d-none");

    try {
        const res = await fetch("/api/jobs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ link }),
        });
        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.error || "Failed to extract job details");
        }

        linkInput.value = "";
        bootstrap.Modal.getInstance(document.getElementById("addJobModal")).hide();
        loadJobs();
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove("d-none");
    } finally {
        btn.disabled = false;
        statusEl.classList.add("d-none");
    }
}

async function updateStatus(id, status) {
    await fetch(`/api/jobs/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
    });
    loadJobs();
}

async function updateField(id, field, value) {
    await fetch(`/api/jobs/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: value }),
    });
}

async function deleteJob(id) {
    if (!confirm("Delete this job application?")) return;
    await fetch(`/api/jobs/${id}`, { method: "DELETE" });
    loadJobs();
}

async function showDetails(id) {
    const res = await fetch(`/api/jobs/${id}`);
    const job = await res.json();

    document.getElementById("detailsTitle").textContent = `${job.company} \u2014 ${job.role}`;
    document.getElementById("detailCompany").textContent = job.company || "\u2014";
    document.getElementById("detailRole").textContent = job.role || "\u2014";
    document.getElementById("detailAppliedDate").textContent = formatDate(job.applied_date) || "\u2014";
    document.getElementById("detailPostedOn").textContent = formatDate(job.posted_on) || "\u2014";
    document.getElementById("detailStatus").innerHTML = `<span class="badge ${statusBadge(job.status)}">${job.status}</span>`;
    document.getElementById("detailComment").textContent = job.comment || "\u2014";
    document.getElementById("detailVisaAnswer").textContent = job.visa_answer || "\u2014";
    document.getElementById("detailLink").innerHTML = job.link
        ? `<a href="${escapeHtml(job.link)}" target="_blank" rel="noopener">${escapeHtml(job.link)}</a>`
        : "\u2014";
    document.getElementById("detailDescription").textContent = job.job_description || "No description available.";

    new bootstrap.Modal(document.getElementById("detailsModal")).show();
}

function statusBadge(status) {
    const map = {
        Applied: "bg-primary",
        Interviewing: "bg-warning text-dark",
        Offer: "bg-success",
        Rejected: "bg-danger",
        "Waiting for Referral": "bg-purple",
        Withdrawn: "bg-secondary",
        Saved: "bg-info",
    };
    return map[status] || "bg-secondary";
}

async function bulkUpload() {
    const fileInput = document.getElementById("bulkFile");
    const file = fileInput.files[0];
    if (!file) return;

    const btn = document.getElementById("bulkSubmitBtn");
    const statusEl = document.getElementById("bulkStatus");
    const resultEl = document.getElementById("bulkResult");
    const errorEl = document.getElementById("bulkError");

    btn.disabled = true;
    statusEl.classList.remove("d-none");
    resultEl.classList.add("d-none");
    errorEl.classList.add("d-none");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch("/api/jobs/bulk", {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.error || "Upload failed");
        }

        let html = `<div class="alert alert-success py-2">
            <strong>${data.added}</strong> jobs imported`;
        if (data.skipped > 0) html += `, <strong>${data.skipped}</strong> duplicates skipped`;
        html += `.</div>`;
        if (data.errors && data.errors.length > 0) {
            html += `<div class="alert alert-warning py-2 small">${data.errors.join("<br>")}</div>`;
        }
        resultEl.innerHTML = html;
        resultEl.classList.remove("d-none");
        fileInput.value = "";
        loadJobs();
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove("d-none");
    } finally {
        btn.disabled = false;
        statusEl.classList.add("d-none");
    }
}

function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ── Resume Management ──

async function loadResumes() {
    try {
        const res = await fetch("/api/resumes");
        allResumes = await res.json();
        renderResumeCards();
        // Update sidebar badge
        const badge = document.getElementById("sidebarResumeCount");
        if (badge) badge.textContent = allResumes.length;
    } catch (err) {
        const grid = document.getElementById("resumeCardsGrid");
        if (grid) {
            grid.innerHTML = '<div class="col-12"><div class="alert alert-danger py-2 small">Failed to load resumes.</div></div>';
        }
    }
}

function renderResumeCards() {
    const grid = document.getElementById("resumeCardsGrid");
    if (!grid) return;

    if (allResumes.length === 0) {
        grid.innerHTML = `
            <div class="col-12 text-center py-5 text-muted" id="resumeEmptyState">
                <i class="bi bi-file-earmark-pdf" style="font-size: 3rem;"></i>
                <p class="mt-3 mb-0 fs-5">No resumes uploaded yet</p>
                <p class="text-muted small">Upload your first resume to get started</p>
            </div>`;
        return;
    }

    grid.innerHTML = allResumes.map(r => `
        <div class="col-sm-6 col-md-4 col-lg-3">
            <div class="resume-card">
                <div class="resume-card-body">
                    <div class="resume-card-icon">
                        <i class="bi bi-file-earmark-pdf-fill"></i>
                    </div>
                    <div class="resume-card-label ${r.label ? '' : 'no-label'}">
                        ${escapeHtml(r.label) || 'No Label'}
                    </div>
                    <div class="resume-card-filename" title="${escapeHtml(r.filename)}">
                        ${escapeHtml(r.filename)}
                    </div>
                    <div class="resume-card-meta">
                        ${formatFileSize(r.file_size)} &middot; ${formatDate(r.uploaded_at)}
                    </div>
                </div>
                <div class="resume-card-footer">
                    <a href="/api/resumes/${r.id}/download" class="card-action action-download" title="Download">
                        <i class="bi bi-download"></i> Download
                    </a>
                    <button class="card-action action-edit" onclick="editResumeLabel(${r.id}, '${escapeHtml(r.label || '')}')" title="Edit Label">
                        <i class="bi bi-pencil"></i> Edit
                    </button>
                    <button class="card-action action-delete" onclick="deleteResume(${r.id})" title="Delete">
                        <i class="bi bi-trash"></i> Delete
                    </button>
                </div>
            </div>
        </div>
    `).join("");
}

function formatFileSize(bytes) {
    if (!bytes) return "0 B";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

async function uploadResume() {
    const fileInput = document.getElementById("resumeFile");
    const labelInput = document.getElementById("resumeLabel");
    const file = fileInput.files[0];
    if (!file) return;

    const btn = document.getElementById("uploadResumeBtn");
    const statusEl = document.getElementById("resumeUploadStatus");
    const errorEl = document.getElementById("resumeUploadError");

    btn.disabled = true;
    statusEl.classList.remove("d-none");
    errorEl.classList.add("d-none");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("label", labelInput.value.trim());

    try {
        const res = await fetch("/api/resumes", {
            method: "POST",
            body: formData,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Upload failed");

        fileInput.value = "";
        labelInput.value = "";
        bootstrap.Modal.getInstance(document.getElementById("uploadResumeModal")).hide();
        loadResumes();
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove("d-none");
    } finally {
        btn.disabled = false;
        statusEl.classList.add("d-none");
    }
}

function editResumeLabel(id, currentLabel) {
    document.getElementById("editLabelResumeId").value = id;
    document.getElementById("editLabelInput").value = currentLabel;
    new bootstrap.Modal(document.getElementById("editResumeLabelModal")).show();
}

async function saveResumeLabel() {
    const id = document.getElementById("editLabelResumeId").value;
    const label = document.getElementById("editLabelInput").value.trim();

    try {
        const res = await fetch(`/api/resumes/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ label }),
        });
        if (!res.ok) throw new Error("Failed to update label");

        bootstrap.Modal.getInstance(document.getElementById("editResumeLabelModal")).hide();
        loadResumes();
    } catch (err) {
        alert(err.message);
    }
}

async function deleteResume(id) {
    if (!confirm("Delete this resume version?")) return;
    await fetch(`/api/resumes/${id}`, { method: "DELETE" });
    loadResumes();
}

// ── Column Resizing ──
function initColumnResize() {
    const table = document.querySelector("#section-jobs table");
    if (!table) return;

    const headerRow = table.querySelector("thead tr");
    const ths = headerRow.querySelectorAll("th");

    // Set initial widths from rendered sizes, then fix the table layout
    ths.forEach(th => {
        th.style.width = th.offsetWidth + "px";
    });
    table.style.tableLayout = "fixed";

    // Remove old handles
    table.querySelectorAll(".col-resize-handle").forEach(h => h.remove());

    // Add resize handles
    ths.forEach(th => {
        const handle = document.createElement("div");
        handle.className = "col-resize-handle";
        th.appendChild(handle);

        let startX, startW;

        handle.addEventListener("mousedown", (e) => {
            e.preventDefault();
            e.stopPropagation(); // Don't trigger sort
            startX = e.pageX;
            startW = th.offsetWidth;
            handle.classList.add("active");
            table.classList.add("resizing");

            const onMouseMove = (e) => {
                const newWidth = Math.max(50, startW + (e.pageX - startX));
                th.style.width = newWidth + "px";
            };

            const onMouseUp = () => {
                handle.classList.remove("active");
                table.classList.remove("resizing");
                document.removeEventListener("mousemove", onMouseMove);
                document.removeEventListener("mouseup", onMouseUp);
            };

            document.addEventListener("mousemove", onMouseMove);
            document.addEventListener("mouseup", onMouseUp);
        });
    });
}

// Re-init resize handles after each render
const origRenderJobs = renderJobs;
renderJobs = function() {
    origRenderJobs();
    initColumnResize();
};

// ── Email Settings & Scan ──

let emailConnected = false;

async function checkEmailConnection() {
    try {
        const res = await fetch("/api/settings/email");
        const data = await res.json();
        emailConnected = data.connected;
    } catch (e) {
        emailConnected = false;
    }
}

async function loadSettings() {
    try {
        const res = await fetch("/api/settings/email");
        const data = await res.json();

        const notConfigured = document.getElementById("emailNotConfigured");
        const connectBtn = document.getElementById("connectGmailBtn");
        const accountsList = document.getElementById("emailAccountsList");
        const scanAllRow = document.getElementById("emailScanAllRow");

        const accounts = data.accounts || [];
        emailConnected = accounts.length > 0;

        // Render accounts list
        if (accounts.length > 0) {
            accountsList.innerHTML = accounts.map(acct => `
                <div class="d-flex align-items-center gap-3 p-3 bg-light rounded-3 mb-2">
                    <div class="settings-status-dot bg-success"></div>
                    <div class="flex-grow-1">
                        <div class="fw-semibold">${escapeHtml(acct.email)}</div>
                        <div class="text-muted small">
                            Last scanned: ${acct.last_scanned_at ? formatDateTime(acct.last_scanned_at) : "Never"}
                        </div>
                    </div>
                    <button class="btn btn-outline-danger btn-sm" onclick="disconnectGmail(${acct.id})">
                        <i class="bi bi-x-circle me-1"></i> Disconnect
                    </button>
                </div>
            `).join("");
            scanAllRow.classList.remove("d-none");
        } else {
            accountsList.innerHTML = "";
            scanAllRow.classList.add("d-none");
        }

        // Show/hide not-configured warning
        if (!data.configured) {
            notConfigured.classList.remove("d-none");
            connectBtn.disabled = true;
        } else {
            notConfigured.classList.add("d-none");
            connectBtn.disabled = false;
        }

        // Update scan button on jobs page
        const scanBtn = document.getElementById("scanEmailBtn");
        if (scanBtn) {
            if (emailConnected) scanBtn.classList.remove("d-none");
            else scanBtn.classList.add("d-none");
        }
    } catch (e) {
        console.error("Failed to load settings:", e);
    }
}

function formatDateTime(dt) {
    if (!dt) return "Never";
    try {
        const d = new Date(dt);
        return d.toLocaleDateString("en-US", {
            month: "short", day: "numeric", year: "numeric",
            hour: "numeric", minute: "2-digit"
        });
    } catch (e) {
        return dt;
    }
}

async function connectGmail() {
    try {
        const res = await fetch("/api/settings/email/auth-url");
        const data = await res.json();
        if (data.error) {
            alert(data.error);
            return;
        }
        // Open Google OAuth in same window
        window.location.href = data.auth_url;
    } catch (e) {
        alert("Failed to start Gmail connection. Please try again.");
    }
}

async function disconnectGmail(accountId) {
    if (!confirm("Disconnect this Gmail account?")) return;

    try {
        await fetch("/api/settings/email/disconnect", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ account_id: accountId }),
        });
        loadSettings();
    } catch (e) {
        alert("Failed to disconnect. Please try again.");
    }
}

let origScanBtnHtml = "";
let origSettingsBtnHtml = "";
let scanPollInterval = null;

async function triggerEmailScan() {
    // If email not connected, redirect to Settings
    if (!emailConnected) {
        switchSection("settings", document.querySelector('.sidebar-link[data-section="settings"]'));
        return;
    }

    setScanButtonsLoading(true);

    try {
        const res = await fetch("/api/settings/email/scan", { method: "POST" });
        const data = await res.json();

        if (data.error) {
            showScanResult(data);
            setScanButtonsLoading(false);
            return;
        }

        if (data.status === "scanning") {
            // Scan started in background — show progress and start polling
            showScanProgress(data.progress || "Starting scan...");
            startScanPolling();
            return;
        }

        if (data.status === "done") {
            // Immediate result (e.g. no jobs)
            showScanResult(data.result || data);
            if (data.result && data.result.rejections_found > 0) loadJobs();
            loadSettings();
            loadScanLogs();
            setScanButtonsLoading(false);
        }

    } catch (e) {
        showScanResult({ error: "Failed to start scan. Please try again." });
        setScanButtonsLoading(false);
    }
}

function setScanButtonsLoading(loading) {
    const scanBtn = document.getElementById("scanEmailBtn");
    const settingsBtn = document.querySelector("#emailScanAllRow .btn-outline-primary");

    if (loading) {
        origScanBtnHtml = scanBtn ? scanBtn.innerHTML : "";
        origSettingsBtnHtml = settingsBtn ? settingsBtn.innerHTML : "";
        if (scanBtn) {
            scanBtn.disabled = true;
            scanBtn.innerHTML = '<span class="scan-spinner me-1"></span> Scanning...';
        }
        if (settingsBtn) {
            settingsBtn.disabled = true;
            settingsBtn.innerHTML = '<span class="scan-spinner me-1"></span> Scanning...';
        }
    } else {
        if (scanBtn) {
            scanBtn.disabled = false;
            scanBtn.innerHTML = origScanBtnHtml || '<i class="bi bi-envelope-check me-1"></i> Scan Now';
        }
        if (settingsBtn) {
            settingsBtn.disabled = false;
            settingsBtn.innerHTML = origSettingsBtnHtml || '<i class="bi bi-envelope-check me-1"></i> Scan All Accounts';
        }
    }
}

function startScanPolling() {
    if (scanPollInterval) clearInterval(scanPollInterval);

    scanPollInterval = setInterval(async () => {
        try {
            const res = await fetch("/api/settings/email/scan/status");
            const data = await res.json();

            if (data.status === "scanning") {
                showScanProgress(data.progress || "Scanning...");
            } else if (data.status === "done") {
                clearInterval(scanPollInterval);
                scanPollInterval = null;
                showScanResult(data.result);
                if (data.result && data.result.rejections_found > 0) loadJobs();
                loadSettings();
                loadScanLogs();
                setScanButtonsLoading(false);
            } else if (data.status === "error") {
                clearInterval(scanPollInterval);
                scanPollInterval = null;
                showScanResult(data.result || { error: "Scan failed" });
                setScanButtonsLoading(false);
            } else {
                // idle or unknown — stop polling
                clearInterval(scanPollInterval);
                scanPollInterval = null;
                setScanButtonsLoading(false);
            }
        } catch (e) {
            clearInterval(scanPollInterval);
            scanPollInterval = null;
            showScanResult({ error: "Lost connection to server. Please refresh and try again." });
            setScanButtonsLoading(false);
        }
    }, 3000); // poll every 3 seconds
}

function showScanProgress(message) {
    const alertEl = document.getElementById("scanResultAlert");
    const settingsEl = document.getElementById("settingsScanResult");

    const html = `<div class="alert alert-info py-2 mb-3" role="alert">
        <span class="scan-spinner me-2"></span> ${escapeHtml(message)}
        <div class="text-muted small mt-1">This may take a few minutes for the first scan. You can navigate around while it runs.</div>
    </div>`;

    if (alertEl) {
        alertEl.innerHTML = html;
        alertEl.classList.remove("d-none");
    }
    if (settingsEl) {
        settingsEl.innerHTML = html;
        settingsEl.classList.remove("d-none");
    }
}

function showScanResult(data) {
    // Show in the jobs page toast area
    const alertEl = document.getElementById("scanResultAlert");
    // Show in settings page area
    const settingsEl = document.getElementById("settingsScanResult");

    let html = "";

    if (data.error) {
        html = `<div class="alert alert-danger alert-dismissible fade show py-2 mb-3" role="alert">
            <i class="bi bi-exclamation-triangle me-1"></i> ${escapeHtml(data.error)}
            <button type="button" class="btn-close btn-close-sm" data-bs-dismiss="alert"></button>
        </div>`;
    } else if (data.rejections_found > 0) {
        const details = data.details.map(d =>
            `<li>${escapeHtml(d.job_company)} — ${escapeHtml(d.job_role)}</li>`
        ).join("");
        html = `<div class="alert alert-warning alert-dismissible fade show py-2 mb-3" role="alert">
            <strong><i class="bi bi-envelope-check me-1"></i> Found ${data.rejections_found} rejection${data.rejections_found > 1 ? 's' : ''}</strong>
            <span class="text-muted small ms-1">(${data.emails_checked} emails scanned)</span>
            <ul class="mb-0 mt-1 small">${details}</ul>
            <button type="button" class="btn-close btn-close-sm" data-bs-dismiss="alert"></button>
        </div>`;
    } else {
        html = `<div class="alert alert-success alert-dismissible fade show py-2 mb-3" role="alert">
            <i class="bi bi-check-circle me-1"></i> No new rejections found.
            <span class="text-muted small">(${data.emails_checked} emails scanned)</span>
            <button type="button" class="btn-close btn-close-sm" data-bs-dismiss="alert"></button>
        </div>`;
    }

    if (alertEl) {
        alertEl.innerHTML = html;
        alertEl.classList.remove("d-none");
    }
    if (settingsEl) {
        settingsEl.innerHTML = html;
        settingsEl.classList.remove("d-none");
    }
}

async function loadScanLogs() {
    try {
        const res = await fetch("/api/settings/email/logs");
        const logs = await res.json();

        const container = document.getElementById("scanLogsContainer");
        if (!container) return;

        if (!logs || logs.length === 0) {
            container.innerHTML = '<p class="text-muted small mb-0">No scans yet. Connect your email and run a scan to see history here.</p>';
            return;
        }

        let html = `<div class="table-responsive">
            <table class="table scan-log-table mb-0">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Emails Checked</th>
                        <th>Rejections Found</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>`;

        logs.forEach(log => {
            let detailsHtml = "—";
            try {
                const details = typeof log.details === "string" ? JSON.parse(log.details) : log.details;
                if (details && details.length > 0) {
                    detailsHtml = details.map(d =>
                        `<span class="badge bg-light text-dark me-1">${escapeHtml(d.job_company || d.company_matched || "")}</span>`
                    ).join("");
                }
            } catch (e) { /* ignore parse errors */ }

            html += `<tr>
                <td>${formatDateTime(log.scanned_at)}</td>
                <td>${log.emails_checked}</td>
                <td>${log.rejections_found > 0
                    ? `<span class="text-warning fw-semibold">${log.rejections_found}</span>`
                    : '<span class="text-success">0</span>'}</td>
                <td>${detailsHtml}</td>
            </tr>`;
        });

        html += `</tbody></table></div>`;
        container.innerHTML = html;
    } catch (e) {
        console.error("Failed to load scan logs:", e);
    }
}
