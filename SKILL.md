# VerifyAI Skill

AI-powered automated verification system for generating and maintaining tests.

## Triggers

Use this skill when:
- User wants to generate tests for their code
- User asks about test coverage or verification
- User wants to analyze test failures
- User mentions "verify", "test generation", or "vai"
- User wants to replay API logs or HAR files as tests

## Commands

### Initialize Project
```bash
vai init [path]
```
Creates `verify-ai.yaml` configuration file with detected project settings.

### Scan Project
```bash
vai scan [path] [--verbose]
```
Analyzes project structure: languages, functions, classes, API endpoints.

### Generate Tests
```bash
vai generate [path] [--type api|unit|all] [--llm claude|openai|ollama] [--dry-run]
```
Uses LLM to generate comprehensive test cases for the project.

### Run Verification
```bash
vai verify [path] [--trigger push|pr|merge|scheduled|manual] [--base main]
```
Runs verification with layered strategy based on trigger type:
- **push**: Quick checks (2min timeout)
- **pr**: Standard checks with test generation (5min)
- **merge**: Full verification (10min)
- **scheduled**: Comprehensive with test regeneration (1h)

### View Git Changes
```bash
vai diff [--from HEAD~1] [--to HEAD] [--functions]
```
Shows changes between commits with optional function-level detail.

### Analyze Failures
```bash
vai analyze [path] [--output pytest_output.txt] [--fix/--no-fix]
```
Parses test failures, identifies root causes, suggests fixes.

### Replay Logs
```bash
vai replay <log_file> [--format auto|har|json|nginx] [--output tests.py]
```
Generates tests from:
- HAR files (browser recordings)
- API access logs (nginx, JSON)
- Error logs (for reproduction tests)

## Configuration

Create `verify-ai.yaml` in project root:

```yaml
project:
  name: my-project
  languages: [python]
  test_output: ./tests/generated

llm:
  provider: claude  # claude | openai | ollama
  model: claude-sonnet-4-20250514
  fallback: ollama/codellama

triggers:
  push: [lint, affected_unit_tests]
  pull_request: [unit_tests, integration_tests, ai_review]
  merge_to_main: [regression_tests, e2e_tests]
  scheduled:
    cron: "0 2 * * *"
    jobs: [full_regression, test_regeneration]

fix:
  auto_fix_tests: true
  auto_fix_source: false
  require_approval: true
```

## Environment Variables

- `VAI_CLAUDE_API_KEY`: Claude API key
- `VAI_OPENAI_API_KEY`: OpenAI API key
- `VAI_DEFAULT_LLM`: Default LLM provider

Auto-loads from `~/.claude/settings.json` if using Claude Code.

## Workflow Examples

### Generate tests for new code
```bash
vai scan . --verbose          # See what will be tested
vai generate . --dry-run      # Preview test generation
vai generate .                # Generate tests
```

### Verify before PR
```bash
vai verify . --trigger pr --base main
```

### Analyze failing tests
```bash
pytest > output.txt 2>&1
vai analyze . --output output.txt --fix
```

### Replay production traffic
```bash
vai replay api_logs.json --output tests/test_api.py
vai replay session.har --output tests/test_browser.py
```

## Supported Languages

- Python (full AST support)
- JavaScript/TypeScript
- Go
- Java

Uses tree-sitter for multi-language parsing.
