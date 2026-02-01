"""Dashboard FastAPI application."""

import webbrowser
from pathlib import Path
from typing import Any, Optional

# Try to import FastAPI, but make it optional
try:
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, FileResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None

from verify_ai.dashboard.routes import create_dashboard_router
from verify_ai.dashboard.storage import DashboardStorage


# Path to static files
STATIC_DIR = Path(__file__).parent / "static"


def create_dashboard_app(
    project_path: Optional[Path] = None,
    storage: Optional[DashboardStorage] = None,
) -> Any:
    """Create FastAPI application for dashboard.
    
    Args:
        project_path: Default project path
        storage: DashboardStorage instance
        
    Returns:
        FastAPI application
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI not installed. Install with: pip install 'verify-ai[server]'"
        )
    
    from verify_ai import __version__
    
    app = FastAPI(
        title="VerifyAI Dashboard",
        description="Web dashboard for VerifyAI test monitoring",
        version=__version__,
    )
    
    # Initialize storage
    _storage = storage or DashboardStorage()
    _project_path = str(project_path or Path.cwd())
    
    # Include dashboard API routes
    dashboard_router = create_dashboard_router(
        storage=_storage,
        default_project=_project_path,
    )
    app.include_router(dashboard_router)
    
    # Mount static files if directory exists
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Root route - serve dashboard
    @app.get("/", response_class=HTMLResponse)
    async def dashboard_home():
        """Serve the dashboard main page."""
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text())
        
        # Fallback inline HTML if static file doesn't exist
        return HTMLResponse(content=_get_fallback_html(_project_path))
    
    # Health check
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy", "version": __version__}
    
    return app


def _get_fallback_html(project_path: str) -> str:
    """Generate fallback HTML if static files are missing.
    
    Args:
        project_path: Project path to display
        
    Returns:
        HTML string
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VerifyAI Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --border-color: #30363d;
            --accent-color: #58a6ff;
            --success-color: #3fb950;
            --warning-color: #d29922;
            --danger-color: #f85149;
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }}
        
        h1 {{
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .logo {{
            width: 32px;
            height: 32px;
            background: var(--accent-color);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }}
        
        .project-info {{
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid var(--border-color);
        }}
        
        .stat-card h3 {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}
        
        .stat-card .value {{
            font-size: 2rem;
            font-weight: bold;
        }}
        
        .stat-card .trend {{
            font-size: 0.875rem;
            margin-top: 0.5rem;
        }}
        
        .trend.up {{ color: var(--success-color); }}
        .trend.down {{ color: var(--danger-color); }}
        .trend.stable {{ color: var(--text-secondary); }}
        
        .chart-container {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid var(--border-color);
            margin-bottom: 2rem;
        }}
        
        .chart-container h2 {{
            font-size: 1rem;
            margin-bottom: 1rem;
        }}
        
        .chart-wrapper {{
            height: 300px;
        }}
        
        .runs-table {{
            width: 100%;
            background: var(--bg-secondary);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            overflow: hidden;
        }}
        
        .runs-table th,
        .runs-table td {{
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .runs-table th {{
            background: var(--bg-tertiary);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
        }}
        
        .runs-table tr:last-child td {{
            border-bottom: none;
        }}
        
        .status-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
        }}
        
        .status-passed {{ background: rgba(63, 185, 80, 0.2); color: var(--success-color); }}
        .status-failed {{ background: rgba(248, 81, 73, 0.2); color: var(--danger-color); }}
        .status-running {{ background: rgba(88, 166, 255, 0.2); color: var(--accent-color); }}
        
        .loading {{
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
        }}
        
        .error {{
            background: rgba(248, 81, 73, 0.1);
            border: 1px solid var(--danger-color);
            border-radius: 8px;
            padding: 1rem;
            color: var(--danger-color);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>
                <div class="logo">V</div>
                VerifyAI Dashboard
            </h1>
            <div class="project-info" id="project-path">{project_path}</div>
        </header>
        
        <div class="stats-grid" id="stats-container">
            <div class="loading">Loading statistics...</div>
        </div>
        
        <div class="chart-container">
            <h2>Coverage Trend</h2>
            <div class="chart-wrapper">
                <canvas id="coverageChart"></canvas>
            </div>
        </div>
        
        <h2 style="margin-bottom: 1rem;">Recent Test Runs</h2>
        <table class="runs-table" id="runs-table">
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Status</th>
                    <th>Trigger</th>
                    <th>Tests</th>
                    <th>Coverage</th>
                    <th>Duration</th>
                </tr>
            </thead>
            <tbody id="runs-body">
                <tr><td colspan="6" class="loading">Loading...</td></tr>
            </tbody>
        </table>
    </div>
    
    <script>
        // Fetch and display dashboard data
        async function loadDashboard() {{
            try {{
                const response = await fetch('/api/dashboard/summary');
                const data = await response.json();
                
                renderStats(data.stats);
                renderChart(data.recent_coverage);
                renderRuns(data.recent_runs);
            }} catch (error) {{
                console.error('Failed to load dashboard:', error);
                document.getElementById('stats-container').innerHTML = 
                    '<div class="error">Failed to load dashboard data</div>';
            }}
        }}
        
        function renderStats(stats) {{
            const container = document.getElementById('stats-container');
            const trendIcon = {{
                'up': '↑',
                'down': '↓', 
                'stable': '→'
            }};
            
            container.innerHTML = `
                <div class="stat-card">
                    <h3>Coverage</h3>
                    <div class="value">${{stats.current_coverage.toFixed(1)}}%</div>
                    <div class="trend ${{stats.coverage_trend}}">${{trendIcon[stats.coverage_trend]}} ${{stats.coverage_trend}}</div>
                </div>
                <div class="stat-card">
                    <h3>Total Runs</h3>
                    <div class="value">${{stats.total_test_runs}}</div>
                </div>
                <div class="stat-card">
                    <h3>Success Rate</h3>
                    <div class="value">${{stats.success_rate.toFixed(0)}}%</div>
                </div>
                <div class="stat-card">
                    <h3>Avg Duration</h3>
                    <div class="value">${{stats.avg_duration_seconds.toFixed(1)}}s</div>
                </div>
            `;
        }}
        
        function renderChart(trends) {{
            const ctx = document.getElementById('coverageChart').getContext('2d');
            
            const labels = trends.map(t => new Date(t.timestamp).toLocaleDateString());
            const data = trends.map(t => t.coverage_percent);
            
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: labels,
                    datasets: [{{
                        label: 'Coverage %',
                        data: data,
                        borderColor: '#58a6ff',
                        backgroundColor: 'rgba(88, 166, 255, 0.1)',
                        fill: true,
                        tension: 0.4,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            max: 100,
                            grid: {{ color: '#30363d' }},
                            ticks: {{ color: '#8b949e' }}
                        }},
                        x: {{
                            grid: {{ color: '#30363d' }},
                            ticks: {{ color: '#8b949e' }}
                        }}
                    }},
                    plugins: {{
                        legend: {{ display: false }}
                    }}
                }}
            }});
        }}
        
        function renderRuns(runs) {{
            const tbody = document.getElementById('runs-body');
            
            if (runs.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="6">No test runs yet</td></tr>';
                return;
            }}
            
            tbody.innerHTML = runs.map(run => `
                <tr>
                    <td>${{new Date(run.timestamp).toLocaleString()}}</td>
                    <td><span class="status-badge status-${{run.status}}">${{run.status}}</span></td>
                    <td>${{run.trigger}}</td>
                    <td>${{run.passed_tests}}/${{run.total_tests}}</td>
                    <td>${{run.coverage_percent ? run.coverage_percent.toFixed(1) + '%' : '-'}}</td>
                    <td>${{run.duration_seconds.toFixed(1)}}s</td>
                </tr>
            `).join('');
        }}
        
        // Load dashboard on page load
        loadDashboard();
        
        // Auto-refresh every 30 seconds
        setInterval(loadDashboard, 30000);
    </script>
</body>
</html>
"""


def run_dashboard(
    host: str = "127.0.0.1",
    port: int = 8080,
    project_path: Optional[Path] = None,
    open_browser: bool = True,
):
    """Run the dashboard server.
    
    Args:
        host: Host to bind to
        port: Port to listen on
        project_path: Project path to monitor
        open_browser: Open browser automatically
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI not installed. Install with: pip install 'verify-ai[server]'"
        )
    
    import uvicorn
    
    app = create_dashboard_app(project_path=project_path)
    
    if open_browser:
        import threading
        url = f"http://{host}:{port}"
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    
    uvicorn.run(app, host=host, port=port)
