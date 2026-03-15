// ── ATS Analyzer (vanilla JS port) ──

const ATS_HISTORY_KEY = "ats_history_v1";
let atsHistory = [];
let atsResult = null;
let atsRewrites = null;
let atsTab = "verdict";

// Load history from localStorage
try { atsHistory = JSON.parse(localStorage.getItem(ATS_HISTORY_KEY) || "[]"); } catch { atsHistory = []; }

function saveAtsHistory() {
    localStorage.setItem(ATS_HISTORY_KEY, JSON.stringify(atsHistory));
}

// ── Color helpers (matching the original) ──
function atsScoreColor(s) {
    if (s >= 80) return { bg: "#e8f5e9", t: "#2e7d32", b: "#a5d6a7" };
    if (s >= 60) return { bg: "#fff8e1", t: "#f57f17", b: "#ffe082" };
    if (s >= 40) return { bg: "#fff3e0", t: "#e65100", b: "#ffcc80" };
    return { bg: "#ffebee", t: "#b71c1c", b: "#ef9a9a" };
}

const applyStyles = {
    "STRONG YES":   { color: "#14532d", bg: "#dcfce7", bdr: "#86efac", icon: "&#128640;" },
    "YES":          { color: "#166534", bg: "#d1fae5", bdr: "#6ee7b7", icon: "&#10003;" },
    "WORTH A SHOT": { color: "#92400e", bg: "#fef3c7", bdr: "#fcd34d", icon: "~" },
    "RISKY":        { color: "#9a3412", bg: "#ffedd5", bdr: "#fdba74", icon: "&#9888;" },
    "DON'T BOTHER": { color: "#7f1d1d", bg: "#fee2e2", bdr: "#fca5a5", icon: "&#10007;" },
};
const verdictStyles = {
    "PASS":          { color: "#14532d", bg: "#dcfce7" },
    "LIKELY PASS":   { color: "#166534", bg: "#d1fae5" },
    "BORDERLINE":    { color: "#92400e", bg: "#fef3c7" },
    "LIKELY REJECT": { color: "#9a3412", bg: "#ffedd5" },
    "REJECT":        { color: "#7f1d1d", bg: "#fee2e2" },
};

// ── SVG Ring ──
function atsRing(score, size) {
    size = size || 70;
    const c = atsScoreColor(score);
    const r = (size / 2) - 5;
    const circ = 2 * Math.PI * r;
    const dash = (score / 100) * circ;
    return `<div style="position:relative;width:${size}px;height:${size}px;display:inline-block">
        <svg width="${size}" height="${size}" style="transform:rotate(-90deg)">
            <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="#e5e7eb" stroke-width="5"/>
            <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${c.t}" stroke-width="5" stroke-dasharray="${dash} ${circ}" stroke-linecap="round"/>
        </svg>
        <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center">
            <span style="font-size:${size<65?12:16}px;font-weight:700;color:${c.t};font-family:monospace">${score}</span>
        </div>
    </div>`;
}

function atsChip(text, type) {
    const s = type === "g" ? { bg: "#e8f5e9", c: "#2e7d32", b: "#a5d6a7" }
            : type === "r" ? { bg: "#ffebee", c: "#b71c1c", b: "#ef9a9a" }
            : type === "y" ? { bg: "#fff8e1", c: "#f57f17", b: "#ffe082" }
            : { bg: "#f3f4f6", c: "#374151", b: "#d1d5db" };
    return `<span style="display:inline-block;padding:3px 9px;border-radius:20px;font-size:12px;font-weight:500;background:${s.bg};color:${s.c};border:1px solid ${s.b};margin:2px 3px">${escapeHtml(text)}</span>`;
}

function atsBar(label, score) {
    const c = atsScoreColor(score);
    return `<div style="margin-bottom:9px">
        <div style="display:flex;justify-content:space-between;margin-bottom:3px">
            <span style="font-size:13px;color:#374151">${escapeHtml(label)}</span>
            <span style="font-size:12px;font-weight:600;color:${c.t};font-family:monospace">${score}</span>
        </div>
        <div style="height:5px;background:#f3f4f6;border-radius:3px;overflow:hidden">
            <div style="height:100%;width:${score}%;background:${c.t};border-radius:3px"></div>
        </div>
    </div>`;
}

function atsCard(title, icon, content, accent) {
    const borderColor = accent || "#e5e7eb";
    const headerBg = accent ? accent + "15" : "transparent";
    return `<div style="margin-bottom:14px;background:#fff;border:1px solid ${borderColor};border-radius:11px;overflow:hidden">
        <div style="padding:10px 15px;border-bottom:1px solid #f3f4f6;display:flex;align-items:center;gap:7px;background:${headerBg}">
            <span style="font-size:14px">${icon}</span>
            <span style="font-weight:600;font-size:13px;color:#111827">${escapeHtml(title)}</span>
        </div>
        <div style="padding:13px 15px">${content}</div>
    </div>`;
}

// ── Main analyze function ──
async function atsAnalyze() {
    const jd = document.getElementById("atsJd").value.trim();
    const resume = document.getElementById("atsResume").value.trim();
    const role = document.getElementById("atsRole").value.trim();
    const errorEl = document.getElementById("atsError");
    const btn = document.getElementById("atsAnalyzeBtn");

    if (!jd || !resume) {
        errorEl.textContent = "Paste both a job description and your resume.";
        errorEl.classList.remove("d-none");
        return;
    }
    errorEl.classList.add("d-none");

    // Loading state
    btn.disabled = true;
    btn.innerHTML = '<span class="scan-spinner me-1"></span> Analysing...';

    try {
        // Fast analysis call
        const res = await fetch("/api/ats/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jd, resume, role, history: atsHistory }),
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        atsResult = data;
        atsTab = "verdict";
        atsRewrites = null;

        // Save to history
        const entry = {
            role: role || "Unknown",
            score: data.ats_score,
            verdict: data.verdict,
            date: new Date().toLocaleDateString(),
            gaps: (data.missing_critical || []).slice(0, 4),
        };
        atsHistory = [...atsHistory, entry].slice(-20);
        saveAtsHistory();

        // Show results
        document.getElementById("atsInputForm").classList.add("d-none");
        document.getElementById("atsResults").classList.remove("d-none");
        renderAtsResults();

        // Background: fetch rewrites
        fetchRewrites(jd, resume, role);

    } catch (e) {
        errorEl.textContent = e.message;
        errorEl.classList.remove("d-none");
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-lightning-charge me-1"></i> Analyze';
    }
}

async function fetchRewrites(jd, resume, role) {
    try {
        const res = await fetch("/api/ats/rewrites", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jd, resume, role }),
        });
        const data = await res.json();
        atsRewrites = data.rewrites || [];
    } catch {
        atsRewrites = [];
    }
    // Re-render if on rewrites tab
    if (atsTab === "rewrites") renderAtsTabContent();
}

function atsNewAnalysis() {
    atsResult = null;
    atsRewrites = null;
    document.getElementById("atsInputForm").classList.remove("d-none");
    document.getElementById("atsResults").classList.add("d-none");
}

function switchAtsTab(tab) {
    atsTab = tab;
    renderAtsTabContent();
    // Update active tab styling
    document.querySelectorAll(".ats-tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.tab === tab);
    });
}

// ── Render full results ──
function renderAtsResults() {
    const r = atsResult;
    if (!r) return;

    const ac = applyStyles[r.apply?.decision] || applyStyles["WORTH A SHOT"];
    const vc = verdictStyles[r.verdict] || verdictStyles["BORDERLINE"];
    const role = document.getElementById("atsRole").value.trim() || "Not specified";

    let html = "";

    // Top bar: role + new analysis button
    html += `<div class="d-flex justify-content-between align-items-center mb-3">
        <span style="font-size:13px;color:#6b7280">Role: <strong style="color:#111827">${escapeHtml(role)}</strong></span>
        <button class="btn btn-sm btn-outline-secondary" onclick="atsNewAnalysis()"><i class="bi bi-arrow-left me-1"></i> New Analysis</button>
    </div>`;

    // Top cards: Apply decision + ATS verdict
    html += `<div class="row g-3 mb-3">
        <div class="col-md-6">
            <div style="padding:16px;background:${ac.bg};border-radius:11px;border:1.5px solid ${ac.bdr};height:100%">
                <div style="font-size:10px;font-weight:700;color:${ac.color};letter-spacing:1.4px;text-transform:uppercase;margin-bottom:5px">Apply?</div>
                <div style="font-size:19px;font-weight:700;color:${ac.color};margin-bottom:7px">${ac.icon} ${escapeHtml(r.apply?.decision || "")}</div>
                <div style="font-size:13px;color:${ac.color};line-height:1.6;opacity:0.9;margin-bottom:9px">${escapeHtml(r.apply?.reason || "")}</div>
                <div style="display:flex;align-items:center;gap:7px">
                    <div style="flex:1;height:4px;background:${ac.bdr}66;border-radius:2px">
                        <div style="height:100%;width:${r.apply?.confidence || 0}%;background:${ac.color};border-radius:2px"></div>
                    </div>
                    <span style="font-size:11px;font-weight:700;color:${ac.color};font-family:monospace">${r.apply?.confidence || 0}%</span>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div style="padding:16px;background:${vc.bg};border-radius:11px;border:1.5px solid ${vc.color}33;height:100%">
                <div style="font-size:10px;font-weight:700;color:${vc.color};letter-spacing:1.4px;text-transform:uppercase;margin-bottom:5px">ATS Verdict</div>
                <div style="display:flex;align-items:center;justify-content:space-between">
                    <div>
                        <div style="font-size:19px;font-weight:700;color:${vc.color};margin-bottom:7px">${escapeHtml(r.verdict || "")}</div>
                        <div style="font-size:13px;color:${vc.color};opacity:0.85;line-height:1.6">${escapeHtml(r.summary || "")}</div>
                    </div>
                    ${atsRing(r.ats_score || 0, 70)}
                </div>
            </div>
        </div>
    </div>`;

    // Pattern
    if (r.pattern && r.pattern !== "First analysis") {
        html += `<div style="padding:10px 14px;background:#f0f4ff;border:1px solid #c7d2fe;border-radius:9px;margin-bottom:14px;font-size:13px;color:#3730a3;line-height:1.6">
            <strong>&#128200; Pattern:</strong> ${escapeHtml(r.pattern)}
        </div>`;
    }

    // Tabs
    const tabs = [
        { id: "verdict", label: "&#127919; Verdict" },
        { id: "keywords", label: "&#128273; Keywords" },
        { id: "rewrites", label: "&#9999;&#65039; Rewrites" },
        { id: "scores", label: "&#128202; Scores" },
    ];
    html += `<div style="display:flex;gap:3px;margin-bottom:16px;background:#f3f4f6;padding:4px;border-radius:10px">
        ${tabs.map(t => `<button class="ats-tab-btn${atsTab === t.id ? " active" : ""}" data-tab="${t.id}" onclick="switchAtsTab('${t.id}')"
            style="flex:1;padding:7px 6px;border:none;border-radius:7px;font-size:12px;cursor:pointer;font-weight:${atsTab === t.id ? 600 : 400};background:${atsTab === t.id ? "#fff" : "transparent"};color:${atsTab === t.id ? "#111827" : "#6b7280"};box-shadow:${atsTab === t.id ? "0 1px 3px rgba(0,0,0,0.1)" : "none"}">${t.label}${t.id === "rewrites" && atsRewrites === null ? " &#9203;" : ""}</button>`).join("")}
    </div>`;

    // Tab content container
    html += `<div id="atsTabContent"></div>`;

    document.getElementById("atsResults").innerHTML = html;
    renderAtsTabContent();
}

// ── Render current tab content ──
function renderAtsTabContent() {
    const r = atsResult;
    if (!r) return;
    const container = document.getElementById("atsTabContent");
    if (!container) return;

    let html = "";

    if (atsTab === "verdict") {
        // Quick score boxes
        const scoreItems = [
            ["Keywords", r.scores?.keywords],
            ["Experience", r.scores?.experience],
            ["Skills", r.scores?.skills],
            ["Impact", r.scores?.impact],
        ];
        html += `<div class="row g-2 mb-3">${scoreItems.map(([lbl, val]) => {
            const c = atsScoreColor(val || 0);
            return `<div class="col-3">
                <div style="background:${c.bg};border:1px solid ${c.b};border-radius:9px;padding:11px;text-align:center">
                    <div style="font-size:20px;font-weight:700;color:${c.t};font-family:monospace">${val || 0}</div>
                    <div style="font-size:10px;font-weight:600;color:${c.t};margin-top:2px;text-transform:uppercase;letter-spacing:0.5px">${lbl}</div>
                </div>
            </div>`;
        }).join("")}</div>`;

        // Profile Insights
        let profileContent = "";
        const profileItems = [["Level", r.profile?.level], ["Biggest Gap", r.profile?.gap]];
        profileContent += `<div class="row g-2 mb-2">${profileItems.map(([k, v]) =>
            `<div class="col-6"><div style="background:#f9fafb;border-radius:8px;padding:9px 11px;border:1px solid #e5e7eb">
                <div style="font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:0.7px">${k}</div>
                <div style="font-size:13px;color:#111827;margin-top:3px;line-height:1.5">${escapeHtml(v || "—")}</div>
            </div></div>`
        ).join("")}</div>`;
        if (r.profile?.trajectory) {
            profileContent += `<div style="background:#f9fafb;border-radius:8px;padding:9px 11px;border:1px solid #e5e7eb;margin-bottom:10px">
                <div style="font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:0.7px">Career Trajectory</div>
                <div style="font-size:13px;color:#111827;margin-top:3px;line-height:1.5">${escapeHtml(r.profile.trajectory)}</div>
            </div>`;
        }
        if (r.profile?.fit_roles?.length) {
            profileContent += `<div><div style="font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:0.7px;margin-bottom:7px">Better Fit Roles</div>
                <div style="line-height:2.2">${r.profile.fit_roles.map(x => atsChip(x)).join("")}</div></div>`;
        }
        html += atsCard("Profile Insights", "&#129504;", profileContent);

        // Strengths
        if (r.strengths?.length) {
            html += atsCard("Strengths", "&#128170;", r.strengths.map(s =>
                `<div style="display:flex;gap:9px;margin-bottom:8px;align-items:flex-start">
                    <span style="color:#16a34a;font-size:13px;flex-shrink:0;margin-top:1px">&#10003;</span>
                    <span style="font-size:13px;color:#374151;line-height:1.6">${escapeHtml(s)}</span>
                </div>`
            ).join(""));
        }

        // Critical Fixes
        if (r.fixes?.length) {
            html += atsCard("Critical Fixes", "&#128680;", r.fixes.map((f, i) =>
                `<div style="margin-bottom:9px;padding:10px 13px;background:#fff7ed;border-radius:8px;border:1px solid #fed7aa;border-left:4px solid #f97316">
                    <div style="display:flex;gap:9px;align-items:flex-start">
                        <span style="background:#f97316;color:#fff;border-radius:50%;width:19px;height:19px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;flex-shrink:0;margin-top:1px">${i + 1}</span>
                        <span style="font-size:13px;color:#374151;line-height:1.7">${escapeHtml(f)}</span>
                    </div>
                </div>`
            ).join(""), "#f97316");
        }

        // Authenticity Flags
        if (r.padding?.length || r.flags?.length || r.genuine?.length) {
            let flagContent = "";
            if (r.padding?.length) {
                flagContent += `<div style="margin-bottom:11px">
                    <div style="font-size:11px;font-weight:700;color:#7e22ce;text-transform:uppercase;letter-spacing:0.7px;margin-bottom:7px">Padding Detected</div>
                    ${r.padding.map(p => `<div style="display:flex;gap:8px;margin-bottom:7px;padding:8px 11px;background:#fdf4ff;border-radius:8px;border:1px solid #e9d5ff">
                        <span style="color:#9333ea;flex-shrink:0">&#9873;</span>
                        <span style="font-size:13px;color:#374151;line-height:1.5">${escapeHtml(p)}</span>
                    </div>`).join("")}</div>`;
            }
            if (r.flags?.length) {
                flagContent += `<div style="margin-bottom:11px">
                    <div style="font-size:11px;font-weight:700;color:#b91c1c;text-transform:uppercase;letter-spacing:0.7px;margin-bottom:7px">Recruiter Red Flags</div>
                    ${r.flags.map(f => `<div style="display:flex;gap:8px;margin-bottom:7px;padding:8px 11px;background:#fff5f5;border-radius:8px;border:1px solid #fecaca">
                        <span style="color:#ef4444;flex-shrink:0">!</span>
                        <span style="font-size:13px;color:#374151;line-height:1.5">${escapeHtml(f)}</span>
                    </div>`).join("")}</div>`;
            }
            if (r.genuine?.length) {
                flagContent += `<div>
                    <div style="font-size:11px;font-weight:700;color:#166534;text-transform:uppercase;letter-spacing:0.7px;margin-bottom:7px">Genuinely Credible</div>
                    <div style="line-height:2.2">${r.genuine.map(g => atsChip(g, "g")).join("")}</div></div>`;
            }
            html += atsCard("Authenticity Flags", "&#128269;", flagContent, "#a855f7");
        }

    } else if (atsTab === "keywords") {
        // Matched
        html += atsCard("Matched", "&#9989;",
            r.matched?.length
                ? `<div style="line-height:2.2">${r.matched.map(k => atsChip(k, "g")).join("")}</div>`
                : `<span style="font-size:13px;color:#9ca3af">None found</span>`
        );
        // Missing Critical
        html += atsCard("Critical Missing — Add If You Have the Experience", "&#10060;",
            r.missing_critical?.length
                ? `<div style="line-height:2.2">${r.missing_critical.map(k => atsChip(k, "r")).join("")}</div>`
                : `<span style="font-size:13px;color:#9ca3af">None — great!</span>`,
            "#ef4444"
        );
        // Nice to Have
        html += atsCard("Nice to Have", "&#9888;&#65039;",
            r.missing_nice?.length
                ? `<div style="line-height:2.2">${r.missing_nice.map(k => atsChip(k, "y")).join("")}</div>`
                : `<span style="font-size:13px;color:#9ca3af">None</span>`
        );

    } else if (atsTab === "rewrites") {
        if (atsRewrites === null) {
            // Still loading
            html += `<div style="display:flex;align-items:center;gap:8px;padding:10px 14px;background:#f8faff;border:1px solid #c7d2fe;border-radius:9px;margin-bottom:14px">
                <span class="scan-spinner" style="width:14px;height:14px;border-width:2px;color:#6366f1"></span>
                <span style="font-size:13px;color:#4338ca">Loading rewrite suggestions...</span>
            </div>`;
        } else if (atsRewrites.length === 0) {
            html += `<div style="text-align:center;padding:30px;color:#9ca3af;font-size:13px">No rewrites — your bullets may already be strong.</div>`;
        } else {
            html += atsRewrites.map(rw =>
                `<div style="margin-bottom:14px;border:1px solid #e5e7eb;border-radius:11px;overflow:hidden">
                    <div style="padding:8px 14px;background:#f9fafb;border-bottom:1px solid #e5e7eb;font-size:11px;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:0.6px">${escapeHtml(rw.section || "")}</div>
                    <div style="padding:13px">
                        <div style="margin-bottom:9px">
                            <div style="font-size:10px;font-weight:700;color:#ef4444;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px">Before</div>
                            <div style="padding:8px 11px;background:#fff5f5;border-radius:7px;border:1px solid #fecaca;font-size:13px;color:#374151;line-height:1.6">${escapeHtml(rw.before || "")}</div>
                        </div>
                        <div style="margin-bottom:9px">
                            <div style="font-size:10px;font-weight:700;color:#16a34a;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px">After</div>
                            <div style="padding:8px 11px;background:#f0fdf4;border-radius:7px;border:1px solid #86efac;font-size:13px;color:#374151;line-height:1.6;font-weight:500">${escapeHtml(rw.after || "")}</div>
                        </div>
                        <div style="font-size:12px;color:#6b7280;font-style:italic">&#128161; ${escapeHtml(rw.why || "")}</div>
                    </div>
                </div>`
            ).join("");
        }

    } else if (atsTab === "scores") {
        const scoreRows = [
            ["ATS Score", r.ats_score],
            ["Keywords", r.scores?.keywords],
            ["Experience", r.scores?.experience],
            ["Skills", r.scores?.skills],
            ["Formatting", r.scores?.formatting],
            ["Impact Metrics", r.scores?.impact],
        ];
        html += atsCard("Full Score Breakdown", "&#128202;",
            scoreRows.map(([lbl, val]) => atsBar(lbl, val || 0)).join("")
        );
    }

    container.innerHTML = html;
}
