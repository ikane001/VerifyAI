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

// State
let currentOffset = 0;
const runsPerPage = 20;

/**
 * Initialize the dashboard
 */
async function init() {
    console.log('Initializing VerifyAI Dashboard...');
    
    // Load theme preference
    loadThemePreference();
    
    // Load initial data
    await loadDashboard();
    
    // Set up auto-refresh
    setInterval(loadDashboard, CONFIG.refreshInterval);
    
    console.log('Dashboard initialized');
}

/**
 * Load all dashboard data
 */
async function loadDashboard() {
    try {
        updateConnectionStatus(true);
        
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
        
        // Remove skeleton class
        document.querySelectorAll('.skeleton').forEach(el => {
            el.classList.remove('skeleton');
        });
        
    } catch (error) {
        console.error('Failed to load dashboard:', error);
        updateConnectionStatus(false);
        showToast('无法加载数据，请检查 API 服务器是否运行', 'error');
    }
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(connected) {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.connection-status span:last-child');
    
    if (statusDot && statusText) {
        if (connected) {
            statusDot.classList.add('connected');
            statusText.textContent = '实时更新';
        } else {
            statusDot.classList.remove('connected');
            statusText.textContent = '连接断开';
        }
    }
}

/**
 * Update project info display
 */
function updateProjectInfo(project) {
    const el = document.getElementById('project-path');
    if (el && project) {
        // Show only the last part of the path
        const parts = project.split('/');
        el.textContent = parts[parts.length - 1] || project;
        el.title = project;
    }
}

/**
 * Render statistics cards
 */
function renderStats(stats) {
    const container = document.getElementById('stats-container');
    if (!container || !stats) return;
    
    const trendIcons = {
        'up': '↑',
        'down': '↓',
        'stable': '→'
    };
    
    const coverageColor = stats.current_coverage >= 80 ? 'var(--success-color)' :
                          stats.current_coverage >= 50 ? 'var(--warning-color)' :
                          'var(--danger-color)';
    
    const successColor = stats.success_rate >= 80 ? 'var(--success-color)' :
                         stats.success_rate >= 50 ? 'var(--warning-color)' :
                         'var(--danger-color)';
    
    container.innerHTML = `
        <div class="stat-card">
            <div class="stat-icon coverage-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M12 6v6l4 2"/>
                </svg>
            </div>
            <div class="stat-content">
                <h3>代码覆盖率</h3>
                <div class="value" style="color: ${coverageColor}">${stats.current_coverage.toFixed(1)}%</div>
                <div class="trend ${stats.coverage_trend}">
                    ${trendIcons[stats.coverage_trend] || '→'} ${getTrendText(stats.coverage_trend)}
                </div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon runs-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
            </div>
            <div class="stat-content">
                <h3>测试执行次数</h3>
                <div class="value">${stats.total_test_runs}</div>
                <div class="trend stable">
                    ${stats.successful_runs} 成功, ${stats.failed_runs} 失败
                </div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon success-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 9V5a3 3 0 00-3-3l-4 9v11h11.28a2 2 0 002-1.7l1.38-9a2 2 0 00-2-2.3zM7 22H4a2 2 0 01-2-2v-7a2 2 0 012-2h3"/>
                </svg>
            </div>
            <div class="stat-content">
                <h3>成功率</h3>
                <div class="value" style="color: ${successColor}">${stats.success_rate.toFixed(0)}%</div>
                <div class="progress-bar" style="margin-top: 0.5rem;">
                    <div class="progress-bar-fill ${getProgressClass(stats.success_rate)}" 
                         style="width: ${stats.success_rate}%"></div>
                </div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon duration-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                </svg>
            </div>
            <div class="stat-content">
                <h3>平均耗时</h3>
                <div class="value">${formatDuration(stats.avg_duration_seconds)}</div>
                <div class="trend stable">
                    平均通过率: ${stats.avg_pass_rate.toFixed(0)}%
                </div>
            </div>
        </div>
    `;
}

/**
 * Get trend text in Chinese
 */
function getTrendText(trend) {
    const texts = {
        'up': '上升',
        'down': '下降',
        'stable': '稳定'
    };
    return texts[trend] || '稳定';
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
    
    // Handle empty data
    if (!trends || trends.length === 0) {
        trends = generateSampleData();
    }
    
    const labels = trends.map(t => formatDate(t.timestamp));
    const data = trends.map(t => t.coverage_percent);
    
    coverageChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '覆盖率',
                data: data,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: '#58a6ff',
                pointBorderColor: '#0d1117',
                pointBorderWidth: 2,
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
                    grid: { 
                        color: 'rgba(48, 54, 61, 0.5)',
                        drawBorder: false,
                    },
                    ticks: { 
                        color: '#8b949e',
                        callback: value => value + '%',
                        font: { size: 11 }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { 
                        color: '#8b949e',
                        font: { size: 11 },
                        maxRotation: 0,
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#21262d',
                    titleColor: '#e6edf3',
                    bodyColor: '#8b949e',
                    borderColor: '#30363d',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: context => `覆盖率: ${context.raw.toFixed(1)}%`
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
    
    // Handle empty data
    if (!runs || runs.length === 0) {
        runs = [];
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
                    label: '通过',
                    data: passedData,
                    backgroundColor: 'rgba(63, 185, 80, 0.8)',
                    borderRadius: 4,
                    borderSkipped: false,
                },
                {
                    label: '失败',
                    data: failedData,
                    backgroundColor: 'rgba(248, 81, 73, 0.8)',
                    borderRadius: 4,
                    borderSkipped: false,
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
                    grid: { 
                        color: 'rgba(48, 54, 61, 0.5)',
                        drawBorder: false,
                    },
                    ticks: { 
                        color: '#8b949e',
                        font: { size: 11 }
                    }
                },
                x: {
                    stacked: true,
                    grid: { display: false },
                    ticks: { 
                        color: '#8b949e',
                        font: { size: 11 },
                        maxRotation: 0,
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#21262d',
                    titleColor: '#e6edf3',
                    bodyColor: '#8b949e',
                    borderColor: '#30363d',
                    borderWidth: 1,
                    padding: 12,
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
    const footerEl = document.getElementById('table-footer');
    
    if (countEl) {
        countEl.textContent = `${runs ? runs.length : 0} 条记录`;
    }
    
    if (!runs || runs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <polyline points="14,2 14,8 20,8"/>
                    </svg>
                    <p>暂无测试记录</p>
                    <p>运行 <code>vai verify</code> 开始测试</p>
                </td>
            </tr>
        `;
        if (footerEl) footerEl.style.display = 'none';
        return;
    }
    
    tbody.innerHTML = runs.map(run => `
        <tr>
            <td>${formatDateTime(run.timestamp)}</td>
            <td><span class="status-badge status-${run.status}">${getStatusText(run.status)}</span></td>
            <td>${getTriggerText(run.trigger)}</td>
            <td>${run.passed_tests}/${run.total_tests}</td>
            <td>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <div class="progress-bar" style="width: 50px;">
                        <div class="progress-bar-fill ${getProgressClass(run.pass_rate)}" 
                             style="width: ${run.pass_rate}%"></div>
                    </div>
                    <span>${run.pass_rate.toFixed(0)}%</span>
                </div>
            </td>
            <td>${run.coverage_percent ? run.coverage_percent.toFixed(1) + '%' : '-'}</td>
            <td>${formatDuration(run.duration_seconds)}</td>
            <td>${run.commit_sha ? `<a href="#" class="commit-sha">${run.commit_sha.slice(0, 7)}</a>` : '-'}</td>
        </tr>
    `).join('');
    
    if (footerEl) {
        footerEl.style.display = runs.length >= runsPerPage ? 'flex' : 'none';
    }
}

/**
 * Get status text in Chinese
 */
function getStatusText(status) {
    const texts = {
        'passed': '通过',
        'failed': '失败',
        'running': '运行中',
        'pending': '等待中',
        'error': '错误'
    };
    return texts[status] || status;
}

/**
 * Get trigger text in Chinese
 */
function getTriggerText(trigger) {
    const texts = {
        'push': '推送',
        'pr': 'PR',
        'merge': '合并',
        'manual': '手动',
        'scheduled': '定时'
    };
    return texts[trigger] || trigger;
}

/**
 * Generate sample data for empty charts
 */
function generateSampleData() {
    const data = [];
    const now = new Date();
    for (let i = 6; i >= 0; i--) {
        const date = new Date(now);
        date.setDate(date.getDate() - i);
        data.push({
            timestamp: date.toISOString(),
            coverage_percent: 0,
        });
    }
    return data;
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

/**
 * Update last updated timestamp
 */
function updateLastUpdated() {
    const el = document.getElementById('last-updated');
    if (el) {
        el.textContent = `最后更新: ${new Date().toLocaleTimeString('zh-CN')}`;
    }
}

/**
 * Theme toggle
 */
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    const icon = document.getElementById('theme-icon');
    if (icon) {
        icon.textContent = newTheme === 'light' ? '🌙' : '☀️';
    }
}

/**
 * Load theme preference
 */
function loadThemePreference() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        const icon = document.getElementById('theme-icon');
        if (icon) {
            icon.textContent = savedTheme === 'light' ? '🌙' : '☀️';
        }
    }
}

/**
 * Update coverage chart with new range
 */
async function updateCoverageChart(days) {
    try {
        const response = await fetch(`${CONFIG.apiBase}/coverage/trend?days=${days}`);
        const data = await response.json();
        renderCoverageChart(data.trends);
    } catch (error) {
        console.error('Failed to update coverage chart:', error);
    }
}

/**
 * Load more runs
 */
async function loadMoreRuns() {
    currentOffset += runsPerPage;
    try {
        const response = await fetch(`${CONFIG.apiBase}/tests/history?offset=${currentOffset}&limit=${runsPerPage}`);
        const data = await response.json();
        
        if (data.runs && data.runs.length > 0) {
            const tbody = document.getElementById('runs-body');
            const newRows = data.runs.map(run => `
                <tr>
                    <td>${formatDateTime(run.timestamp)}</td>
                    <td><span class="status-badge status-${run.status}">${getStatusText(run.status)}</span></td>
                    <td>${getTriggerText(run.trigger)}</td>
                    <td>${run.passed_tests}/${run.total_tests}</td>
                    <td>${run.pass_rate.toFixed(0)}%</td>
                    <td>${run.coverage_percent ? run.coverage_percent.toFixed(1) + '%' : '-'}</td>
                    <td>${formatDuration(run.duration_seconds)}</td>
                    <td>${run.commit_sha ? `<a href="#" class="commit-sha">${run.commit_sha.slice(0, 7)}</a>` : '-'}</td>
                </tr>
            `).join('');
            
            tbody.insertAdjacentHTML('beforeend', newRows);
        }
        
        if (data.runs.length < runsPerPage) {
            document.getElementById('table-footer').style.display = 'none';
        }
    } catch (error) {
        console.error('Failed to load more runs:', error);
    }
}

/**
 * Export runs to JSON
 */
function exportRuns() {
    showToast('导出功能即将推出', 'info');
}

/**
 * Run coverage analysis
 */
function runCoverage() {
    showToast('请在终端运行: vai coverage', 'info');
}

/**
 * Run tests
 */
function runTests() {
    showToast('请在终端运行: vai verify', 'info');
}

/**
 * Generate tests
 */
function generateTests() {
    showToast('请在终端运行: vai generate', 'info');
}

// Utility functions

function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

function formatDateTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatDuration(seconds) {
    if (!seconds) return '-';
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
