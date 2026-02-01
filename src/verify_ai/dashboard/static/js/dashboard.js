/**
 * VerifyAI Dashboard JavaScript
 */

// Chart instances
let coverageChart = null;
let testsChart = null;

// Configuration
const CONFIG = {
    refreshInterval: 30000, // 30 seconds
    apiBase: '/api/dashboard',
};

/**
 * Initialize the dashboard
 */
async function init() {
    await loadDashboard();
    
    // Set up auto-refresh
    setInterval(loadDashboard, CONFIG.refreshInterval);
}

/**
 * Load all dashboard data
 */
async function loadDashboard() {
    try {
        const response = await fetch(`${CONFIG.apiBase}/summary`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update all sections
        updateProjectInfo(data.project);
        renderStats(data.stats);
        renderCoverageChart(data.recent_coverage);
        renderTestsChart(data.recent_runs);
        renderRuns(data.recent_runs);
        updateLastUpdated();
        
    } catch (error) {
        console.error('Failed to load dashboard:', error);
        showError('Failed to load dashboard data. Is the API server running?');
    }
}

/**
 * Update project info display
 */
function updateProjectInfo(project) {
    const el = document.getElementById('project-path');
    if (el) {
        el.textContent = project;
    }
}

/**
 * Render statistics cards
 */
function renderStats(stats) {
    const container = document.getElementById('stats-container');
    
    const trendIcons = {
        'up': '↑',
        'down': '↓',
        'stable': '→'
    };
    
    const coverageColor = stats.current_coverage >= 80 ? 'var(--success-color)' :
                          stats.current_coverage >= 50 ? 'var(--warning-color)' :
                          'var(--danger-color)';
    
    container.innerHTML = `
        <div class="stat-card">
            <h3>Coverage</h3>
            <div class="value" style="color: ${coverageColor}">${stats.current_coverage.toFixed(1)}%</div>
            <div class="trend ${stats.coverage_trend}">
                ${trendIcons[stats.coverage_trend] || '→'} ${stats.coverage_trend}
            </div>
        </div>
        <div class="stat-card">
            <h3>Total Runs</h3>
            <div class="value">${stats.total_test_runs}</div>
            <div class="trend stable">
                ${stats.successful_runs} passed, ${stats.failed_runs} failed
            </div>
        </div>
        <div class="stat-card">
            <h3>Success Rate</h3>
            <div class="value">${stats.success_rate.toFixed(0)}%</div>
            <div class="progress-bar">
                <div class="progress-bar-fill ${getProgressClass(stats.success_rate)}" 
                     style="width: ${stats.success_rate}%"></div>
            </div>
        </div>
        <div class="stat-card">
            <h3>Avg Duration</h3>
            <div class="value">${formatDuration(stats.avg_duration_seconds)}</div>
            <div class="trend stable">
                Pass rate: ${stats.avg_pass_rate.toFixed(0)}%
            </div>
        </div>
    `;
}

/**
 * Render coverage trend chart
 */
function renderCoverageChart(trends) {
    const ctx = document.getElementById('coverageChart');
    if (!ctx) return;
    
    // Destroy existing chart
    if (coverageChart) {
        coverageChart.destroy();
    }
    
    const labels = trends.map(t => formatDate(t.timestamp));
    const data = trends.map(t => t.coverage_percent);
    
    coverageChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Coverage %',
                data: data,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: '#30363d' },
                    ticks: { 
                        color: '#8b949e',
                        callback: value => value + '%'
                    }
                },
                x: {
                    grid: { color: '#30363d' },
                    ticks: { color: '#8b949e' }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: context => `Coverage: ${context.raw.toFixed(1)}%`
                    }
                }
            }
        }
    });
}

/**
 * Render tests chart
 */
function renderTestsChart(runs) {
    const ctx = document.getElementById('testsChart');
    if (!ctx) return;
    
    // Destroy existing chart
    if (testsChart) {
        testsChart.destroy();
    }
    
    const labels = runs.map(r => formatDate(r.timestamp));
    const passedData = runs.map(r => r.passed_tests);
    const failedData = runs.map(r => r.failed_tests);
    
    testsChart = new Chart(ctx.getContext('2d'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Passed',
                    data: passedData,
                    backgroundColor: 'rgba(63, 185, 80, 0.8)',
                    borderRadius: 4,
                },
                {
                    label: 'Failed',
                    data: failedData,
                    backgroundColor: 'rgba(248, 81, 73, 0.8)',
                    borderRadius: 4,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    stacked: true,
                    grid: { color: '#30363d' },
                    ticks: { color: '#8b949e' }
                },
                x: {
                    stacked: true,
                    grid: { display: false },
                    ticks: { color: '#8b949e' }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#8b949e' }
                }
            }
        }
    });
}

/**
 * Render test runs table
 */
function renderRuns(runs) {
    const tbody = document.getElementById('runs-body');
    const countEl = document.getElementById('runs-count');
    
    if (countEl) {
        countEl.textContent = `${runs.length} runs`;
    }
    
    if (runs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state">
                    <div class="icon">📋</div>
                    <p>No test runs yet. Run <code>vai verify</code> to start.</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = runs.map(run => `
        <tr>
            <td>${formatDateTime(run.timestamp)}</td>
            <td><span class="status-badge status-${run.status}">${run.status}</span></td>
            <td>${run.trigger}</td>
            <td>${run.passed_tests}/${run.total_tests}</td>
            <td>
                <div class="progress-bar" style="width: 60px; display: inline-block; vertical-align: middle;">
                    <div class="progress-bar-fill ${getProgressClass(run.pass_rate)}" 
                         style="width: ${run.pass_rate}%"></div>
                </div>
                <span style="margin-left: 0.5rem;">${run.pass_rate.toFixed(0)}%</span>
            </td>
            <td>${run.coverage_percent ? run.coverage_percent.toFixed(1) + '%' : '-'}</td>
            <td>${formatDuration(run.duration_seconds)}</td>
            <td>${run.commit_sha ? `<span class="commit-sha">${run.commit_sha.slice(0, 7)}</span>` : '-'}</td>
        </tr>
    `).join('');
}

/**
 * Show error message
 */
function showError(message) {
    const container = document.getElementById('stats-container');
    container.innerHTML = `<div class="error" style="grid-column: 1/-1;">${message}</div>`;
}

/**
 * Update last updated timestamp
 */
function updateLastUpdated() {
    const el = document.getElementById('last-updated');
    if (el) {
        el.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
    }
}

// Utility functions

function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatDateTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${seconds.toFixed(1)}s`;
    } else if (seconds < 3600) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}m ${secs}s`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${mins}m`;
    }
}

function getProgressClass(percent) {
    if (percent >= 80) return 'high';
    if (percent >= 50) return 'medium';
    return 'low';
}

// Initialize on load
document.addEventListener('DOMContentLoaded', init);
