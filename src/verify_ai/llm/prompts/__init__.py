"""Prompt templates for LLM interactions."""

# API Test Generation Prompt
API_TEST_SYSTEM_PROMPT = """You are an expert QA engineer specializing in API testing.
Your task is to generate comprehensive test cases for REST APIs.

Guidelines:
1. Generate complete, executable pytest test code
2. Cover both success and error scenarios
3. Include edge cases and boundary conditions
4. Use descriptive test names that explain what's being tested
5. Add clear comments explaining test purpose
6. Use pytest fixtures for setup/teardown
7. Mock external dependencies appropriately
8. Include assertions for status codes, response structure, and data"""

API_TEST_PROMPT_TEMPLATE = """Generate pytest test cases for the following API endpoint:

**Endpoint**: {method} {path}
**Summary**: {summary}
**Description**: {description}

**Parameters**:
{parameters}

**Request Body Schema**:
{request_body}

**Response Schemas**:
{responses}

**Base URL**: {base_url}

Generate comprehensive test cases covering:
1. Successful request with valid data
2. Validation errors (missing/invalid parameters)
3. Edge cases (empty values, max lengths, special characters)
4. Authentication/authorization if applicable

Output complete, runnable pytest code wrapped in ```python code blocks."""


# Unit Test Generation Prompt
UNIT_TEST_SYSTEM_PROMPT = """You are an expert Python developer and test engineer.
Your task is to generate comprehensive unit tests for Python code.

Guidelines:
1. Generate complete, executable pytest test code
2. Cover all code paths and branches
3. Include edge cases and boundary conditions
4. Use descriptive test names following pattern: test_<function>_<scenario>_<expected>
5. Add clear docstrings explaining test purpose
6. Use pytest fixtures for setup/teardown
7. Mock external dependencies and I/O operations
8. Include both positive and negative test cases
9. Test exception handling"""

UNIT_TEST_PROMPT_TEMPLATE = """Generate pytest unit tests for the following Python code:

**File**: {file_path}

**Function/Class to test**:
```python
{source_code}
```

**Docstring**: {docstring}

**Parameters**: {parameters}
**Return Type**: {return_type}

Generate comprehensive test cases covering:
1. Normal/expected behavior with valid inputs
2. Edge cases (empty inputs, None values, boundary values)
3. Error handling (invalid inputs, exceptions)
4. All code branches if applicable

Output complete, runnable pytest code wrapped in ```python code blocks.
Include necessary imports at the top."""


# Code Analysis Prompt
CODE_ANALYSIS_PROMPT = """Analyze the following code and identify:
1. Key functions and their purposes
2. Potential bugs or issues
3. Areas that need testing
4. Suggested test scenarios

Code:
```{language}
{code}
```

Provide a structured analysis."""


# Fix Suggestion Prompt
FIX_SUGGESTION_SYSTEM_PROMPT = """You are an expert developer helping to fix test failures.
Analyze the test failure and provide a clear fix.

Guidelines:
1. Identify the root cause of the failure
2. Suggest a specific fix (either to test or source code)
3. Explain why this fix is appropriate
4. Provide the corrected code"""

FIX_SUGGESTION_PROMPT_TEMPLATE = """A test has failed. Please analyze and suggest a fix.

**Test Name**: {test_name}
**Test File**: {test_file}

**Test Code**:
```python
{test_code}
```

**Source Code Being Tested**:
```python
{source_code}
```

**Error Message**:
```
{error_message}
```

**Stack Trace**:
```
{stack_trace}
```

Analyze the failure and provide:
1. Root cause analysis
2. Whether to fix the test or the source code
3. The corrected code

Output your fix wrapped in ```python code blocks."""
