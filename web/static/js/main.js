/**
 * DSS Maintenance Prioritization Web Demo
 * Client-side script handling interactive table, Chart.js visualizations, and REST API calls.
 */

let topsisChartInstance = null;
let donutChartInstance = null;
let radarChartInstance = null;
let currentRunResults = null;

// Initialize on document ready
document.addEventListener("DOMContentLoaded", function () {
    // Check if reloaded from history
    const reloaded = sessionStorage.getItem('reload_machines');
    if (reloaded) {
        try {
            const machines = JSON.parse(reloaded);
            populateMachineTable(machines);
            sessionStorage.removeItem('reload_machines');
            // Auto run analysis for reloaded items
            setTimeout(runDSSAnalysis, 300);
            return;
        } catch (e) {
            console.error("Failed to parse reloaded machines:", e);
        }
    }
});

/**
 * Render machine list to input table
 */
function populateMachineTable(machines) {
    const tbody = document.getElementById("machineTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    machines.forEach((m, idx) => {
        addMachineRow(m, idx + 1);
    });

    updateMachineCount();
}

/**
 * Add a single machine row
 */
function addMachineRow(m = null, stt = null) {
    const tbody = document.getElementById("machineTableBody");
    if (!tbody) return;

    const rowCount = tbody.rows.length + 1;
    const itemStt = stt || rowCount;
    const mid = m && m.machine_id ? m.machine_id : `M${String(itemStt).padStart(3, '0')}`;
    const mType = m && m.type ? m.type.toUpperCase() : "L";
    const airT = m && m.air_temperature !== undefined ? m.air_temperature : 300.0;
    const procT = m && m.process_temperature !== undefined ? m.process_temperature : 310.0;
    const speed = m && m.rotational_speed !== undefined ? m.rotational_speed : 1538;
    const torque = m && m.torque !== undefined ? m.torque : 40.0;
    const wear = m && m.tool_wear !== undefined ? m.tool_wear : 0.0;

    const tr = document.createElement("tr");
    tr.className = "machine-row";
    tr.innerHTML = `
        <td class="text-muted fw-bold stt-cell">${itemStt}</td>
        <td>
            <input type="text" class="form-control form-control-sm table-input-compact fw-bold text-primary field-id" value="${mid}" required>
        </td>
        <td>
            <select class="form-select form-select-sm table-input-compact field-type">
                <option value="L" ${mType === 'L' ? 'selected' : ''}>L (Low)</option>
                <option value="M" ${mType === 'M' ? 'selected' : ''}>M (Med)</option>
                <option value="H" ${mType === 'H' ? 'selected' : ''}>H (High)</option>
            </select>
        </td>
        <td>
            <input type="number" step="0.1" class="form-control form-control-sm table-input-compact field-air-temp" value="${airT}" required>
        </td>
        <td>
            <input type="number" step="0.1" class="form-control form-control-sm table-input-compact field-proc-temp" value="${procT}" required>
        </td>
        <td>
            <input type="number" step="1" class="form-control form-control-sm table-input-compact field-speed" value="${speed}" required>
        </td>
        <td>
            <input type="number" step="0.1" class="form-control form-control-sm table-input-compact field-torque" value="${torque}" required>
        </td>
        <td>
            <input type="number" step="1" class="form-control form-control-sm table-input-compact field-wear" value="${wear}" required>
        </td>
        <td>
            <button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="removeMachineRow(this)" title="Xóa máy này">
                <i class="fa-solid fa-xmark"></i>
            </button>
        </td>
    `;

    tbody.appendChild(tr);
    updateMachineCount();
}

/**
 * Add new empty/default machine row
 */
function addNewMachineRow() {
    addMachineRow();
}

/**
 * Remove specific row
 */
function removeMachineRow(btn) {
    const row = btn.closest("tr");
    if (row) {
        row.remove();
        reindexRows();
        updateMachineCount();
    }
}

/**
 * Re-number STT column
 */
function reindexRows() {
    const tbody = document.getElementById("machineTableBody");
    if (!tbody) return;
    Array.from(tbody.rows).forEach((r, idx) => {
        const sttCell = r.querySelector(".stt-cell");
        if (sttCell) sttCell.textContent = idx + 1;
    });
}

/**
 * Clear all machine rows
 */
function clearAllMachines() {
    if (!confirm("Bạn có chắc muốn xóa toàn bộ danh sách máy?")) return;
    const tbody = document.getElementById("machineTableBody");
    if (tbody) tbody.innerHTML = "";
    updateMachineCount();
}

/**
 * Update machine count counter badge
 */
function updateMachineCount() {
    const tbody = document.getElementById("machineTableBody");
    const countDisplay = document.getElementById("machineCountDisplay");
    if (tbody && countDisplay) {
        countDisplay.textContent = tbody.rows.length;
    }
}

/**
 * Collect table data to list of machine objects
 */
function getMachinesFromTable() {
    const tbody = document.getElementById("machineTableBody");
    if (!tbody) return [];

    const machines = [];
    for (let r of tbody.rows) {
        const id = r.querySelector(".field-id")?.value.trim() || `M${machines.length + 1}`;
        const type = r.querySelector(".field-type")?.value || "L";
        const airT = parseFloat(r.querySelector(".field-air-temp")?.value) || 300.0;
        const procT = parseFloat(r.querySelector(".field-proc-temp")?.value) || 310.0;
        const speed = parseFloat(r.querySelector(".field-speed")?.value) || 1500.0;
        const torque = parseFloat(r.querySelector(".field-torque")?.value) || 40.0;
        const wear = parseFloat(r.querySelector(".field-wear")?.value) || 0.0;

        machines.push({
            machine_id: id,
            type: type,
            air_temperature: airT,
            process_temperature: procT,
            rotational_speed: speed,
            torque: torque,
            tool_wear: wear
        });
    }
    return machines;
}

/**
 * Call API to generate N random machines
 */
async function generateRandomMachines(n = 10) {
    const btn = document.getElementById("btnRandom10");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin me-1"></i> Đang tạo...`;
    }

    try {
        const res = await fetch(`/api/random-machines?n=${n}`);
        const data = await res.json();
        if (data.success && data.machines) {
            populateMachineTable(data.machines);
        } else {
            alert("Lỗi khi sinh máy ngẫu nhiên: " + (data.error || "Không rõ"));
        }
    } catch (e) {
        alert("Lỗi kết nối máy chủ: " + e.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-dice me-1"></i> Tạo ngẫu nhiên 10 máy`;
        }
    }
}

/**
 * Preset Scenarios
 */
function loadScenario(type) {
    let machines = [];
    if (type === 'mixed') {
        generateRandomMachines(10);
        return;
    } else if (type === 'high_risk') {
        machines = [
            { machine_id: "M001", type: "H", air_temperature: 301.2, process_temperature: 311.5, rotational_speed: 1390, torque: 68.5, tool_wear: 235 },
            { machine_id: "M002", type: "L", air_temperature: 299.8, process_temperature: 307.2, rotational_speed: 1250, torque: 58.0, tool_wear: 215 },
            { machine_id: "M003", type: "M", air_temperature: 302.5, process_temperature: 312.8, rotational_speed: 2100, torque: 72.0, tool_wear: 195 },
            { machine_id: "M004", type: "L", air_temperature: 300.1, process_temperature: 310.2, rotational_speed: 1510, torque: 42.0, tool_wear: 180 },
            { machine_id: "M005", type: "M", air_temperature: 298.5, process_temperature: 308.6, rotational_speed: 1480, torque: 38.0, tool_wear: 45 }
        ];
    } else if (type === 'safe') {
        machines = [
            { machine_id: "M001", type: "L", air_temperature: 298.2, process_temperature: 308.5, rotational_speed: 1530, torque: 38.5, tool_wear: 25 },
            { machine_id: "M002", type: "M", air_temperature: 299.0, process_temperature: 309.2, rotational_speed: 1500, torque: 39.0, tool_wear: 40 },
            { machine_id: "M003", type: "H", air_temperature: 300.1, process_temperature: 310.3, rotational_speed: 1520, torque: 41.2, tool_wear: 15 },
            { machine_id: "M004", type: "L", air_temperature: 297.8, process_temperature: 308.0, rotational_speed: 1490, torque: 36.5, tool_wear: 50 },
            { machine_id: "M005", type: "L", air_temperature: 299.5, process_temperature: 309.7, rotational_speed: 1540, torque: 40.0, tool_wear: 30 }
        ];
    }
    populateMachineTable(machines);
}

/**
 * Execute DSS Analysis via REST API
 */
async function runDSSAnalysis() {
    const machines = getMachinesFromTable();
    if (!machines || machines.length === 0) {
        alert("Vui lòng nhập ít nhất một máy hoặc bấm 'Tạo ngẫu nhiên 10 máy'!");
        return;
    }

    const btn = document.getElementById("btnRunDSS");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin me-2"></i> ĐANG PHÂN TÍCH...`;
    }

    try {
        const res = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ machines: machines })
        });

        const data = await res.json();
        if (data.success && data.data) {
            currentRunResults = data.data;
            renderResults(data.data);
            
            // Scroll to results
            document.getElementById("resultsSection").scrollIntoView({ behavior: 'smooth' });
        } else {
            alert("Lỗi khi chạy DSS: " + (data.error || "Không rõ"));
        }
    } catch (e) {
        alert("Lỗi kết nối máy chủ: " + e.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-bolt me-2"></i> CHẠY PHÂN TÍCH ƯU TIÊN BẢO TRÌ`;
        }
    }
}

/**
 * Render complete results
 */
function renderResults(results) {
    const section = document.getElementById("resultsSection");
    if (!section) return;
    section.style.display = "block";

    // 1. KPI Cards
    document.getElementById("kpiTotal").textContent = results.total_machines || 0;
    document.getElementById("kpiCritical").textContent = results.counts.CRITICAL || 0;
    document.getElementById("kpiHigh").textContent = results.counts.HIGH || 0;
    document.getElementById("kpiMedium").textContent = results.counts.MEDIUM || 0;
    document.getElementById("kpiNormal").textContent = results.counts.NORMAL || 0;
    document.getElementById("kpiTopMachine").textContent = results.top_priority_machine || "-";
    
    if (results.top_machine_details) {
        document.getElementById("kpiTopAction").textContent = results.top_machine_details.action_vi;
    }

    document.getElementById("rankingBadgeInfo").textContent = `${results.total_machines} máy đã xếp hạng`;

    // 2. Ranking Table
    renderRankingTable(results.ranking);

    // 3. Charts
    renderTopsisBarChart(results.ranking);
    renderRiskDonutChart(results.counts);

    // 4. Inspect Top Machine by Default
    if (results.ranking && results.ranking.length > 0) {
        inspectMachine(results.ranking[0].machine_id);
    }
}

/**
 * Render Ranking Table
 */
function renderRankingTable(ranking) {
    const tbody = document.getElementById("rankingTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    ranking.forEach(r => {
        const tr = document.createElement("tr");
        
        let rankBadge = `<span class="badge bg-secondary">#${r.priority_rank}</span>`;
        if (r.priority_rank === 1) rankBadge = `<span class="badge bg-danger shadow-sm">👑 #1</span>`;
        else if (r.priority_rank === 2) rankBadge = `<span class="badge bg-warning text-dark">#2</span>`;
        else if (r.priority_rank === 3) rankBadge = `<span class="badge bg-info text-dark">#3</span>`;

        // Factors badges
        const factorTags = r.contributing_factors.map(f => 
            `<span class="badge bg-light text-dark border me-1 fs-8" title="Trọng số đóng góp: ${f.contribution_score}">${f.criterion.replace('_', ' ')}</span>`
        ).join('');

        tr.innerHTML = `
            <td>${rankBadge}</td>
            <td class="fw-bold text-primary">${r.machine_id}</td>
            <td><span class="badge bg-light text-dark border">${r.type}</span></td>
            <td class="fw-bold ${r.failure_probability > 0.5 ? 'text-danger' : 'text-dark'}">${r.failure_probability_pct}%</td>
            <td class="fw-bold">${r.topsis_score.toFixed(4)}</td>
            <td><span class="badge ${r.badge_class}">${r.risk_level}</span></td>
            <td class="text-start small fw-semibold">${r.action_vi}</td>
            <td class="text-start">${factorTags}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary py-0 px-2" onclick="inspectMachine('${r.machine_id}')">
                    <i class="fa-solid fa-magnifying-glass me-1"></i> Soi
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

/**
 * Render Horizontal Bar Chart of TOPSIS Scores
 */
function renderTopsisBarChart(ranking) {
    const ctx = document.getElementById("topsisBarChart");
    if (!ctx) return;

    if (topsisChartInstance) {
        topsisChartInstance.destroy();
    }

    // Prepare data (reversed for bottom-to-top barh or sorted top-to-bottom)
    const labels = ranking.map(r => r.machine_id);
    const scores = ranking.map(r => r.topsis_score);
    const colors = ranking.map(r => r.color);

    topsisChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Điểm Ưu Tiên TOPSIS',
                data: scores,
                backgroundColor: colors,
                borderColor: colors,
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            scales: {
                x: {
                    beginAtZero: true,
                    max: 1.0,
                    title: {
                        display: true,
                        text: 'TOPSIS Score (Maintenance Priority / Risk)'
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const idx = context.dataIndex;
                            const item = ranking[idx];
                            return ` Điểm: ${item.topsis_score} | ${item.risk_level} (${item.action_vi})`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Render Donut Chart for Risk Level distribution
 */
function renderRiskDonutChart(counts) {
    const ctx = document.getElementById("riskDonutChart");
    if (!ctx) return;

    if (donutChartInstance) {
        donutChartInstance.destroy();
    }

    const dataValues = [
        counts.CRITICAL || 0,
        counts.HIGH || 0,
        counts.MEDIUM || 0,
        counts.NORMAL || 0
    ];

    donutChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['CRITICAL', 'HIGH', 'MEDIUM', 'NORMAL'],
            datasets: [{
                data: dataValues,
                backgroundColor: ['#DC2626', '#EA580C', '#EAB308', '#16A34A'],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 12, font: { size: 11 } }
                }
            },
            cutout: '65%'
        }
    });

    const total = dataValues.reduce((a, b) => a + b, 0);
    const criticalRate = total > 0 ? (((counts.CRITICAL || 0) + (counts.HIGH || 0)) / total * 100).toFixed(0) : 0;
    document.getElementById("riskDonutSummary").innerHTML = `
        <strong>${criticalRate}%</strong> máy thuộc diện cần can thiệp bảo trì sớm (Critical / High).
    `;
}

/**
 * Inspect a specific machine and show Explainability details
 */
function inspectMachine(machineId) {
    if (!currentRunResults || !currentRunResults.ranking) return;

    const machine = currentRunResults.ranking.find(m => m.machine_id === machineId);
    if (!machine) return;

    // Update Text Details
    document.getElementById("inspectingMachineBadge").textContent = `Máy đang chọn: ${machine.machine_id} (Hạng #${machine.priority_rank})`;
    document.getElementById("explainMachineId").textContent = machine.machine_id;
    document.getElementById("explainFailProb").textContent = `${machine.failure_probability_pct}%`;
    document.getElementById("explainTopsisScore").textContent = machine.topsis_score.toFixed(4);
    document.getElementById("explainActionVi").textContent = machine.action_vi;
    
    const badge = document.getElementById("explainRiskBadge");
    badge.className = `badge ${machine.badge_class} fs-6`;
    badge.textContent = machine.risk_level;

    // Factors List
    const factorsContainer = document.getElementById("explainFactorsList");
    factorsContainer.innerHTML = "";
    machine.contributing_factors.forEach((f, i) => {
        const item = document.createElement("div");
        item.className = "p-2 bg-white border rounded d-flex justify-content-between align-items-center shadow-xs";
        item.innerHTML = `
            <div>
                <span class="badge bg-primary me-2">#${i + 1}</span>
                <strong>${f.label}</strong>
                <div class="fs-8 text-muted">Giá trị thực tế: <strong>${f.raw_value}</strong> | Chuẩn hóa: <strong>${f.normalized_value}</strong></div>
            </div>
            <div class="text-end">
                <span class="fs-8 text-muted d-block">Đóng góp điểm:</span>
                <span class="badge bg-danger">${f.contribution_score}</span>
            </div>
        `;
        factorsContainer.appendChild(item);
    });

    // Radar Criteria Chart
    renderRadarCriteriaChart(machine);

    // Scroll to explain section smoothly if clicked
    document.getElementById("explainSection").scrollIntoView({ behavior: 'smooth' });
}

/**
 * Render Radar Chart of 6 normalized criteria for the inspected machine
 */
function renderRadarCriteriaChart(machine) {
    const ctx = document.getElementById("radarCriteriaChart");
    if (!ctx) return;

    if (radarChartInstance) {
        radarChartInstance.destroy();
    }

    const norm = machine.normalized_criteria || {};
    const labels = [
        'P(Failure)',
        'Độ mòn Tool Wear',
        'Torque Nm',
        'Nhiệt độ Process',
        'Tốc độ Speed',
        'Nhiệt độ Air'
    ];

    const values = [
        norm.Failure_Probability || 0,
        norm.Tool_wear_min || 0,
        norm.Torque_Nm || 0,
        norm.Process_temperature_K || 0,
        norm.Rotational_speed_rpm || 0,
        norm.Air_temperature_K || 0
    ];

    radarChartInstance = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: `Chỉ số rủi ro [${machine.machine_id}]`,
                data: values,
                backgroundColor: 'rgba(37, 99, 235, 0.25)',
                borderColor: '#2563EB',
                pointBackgroundColor: '#DC2626',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: '#DC2626',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 1.0,
                    ticks: { stepSize: 0.2, display: false },
                    pointLabels: { font: { size: 10, weight: 'bold' } }
                }
            },
            plugins: {
                legend: { position: 'top', labels: { boxWidth: 10 } }
            }
        }
    });
}
