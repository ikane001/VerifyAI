"""Test generator using LLM."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..config import LLMConfig, ProjectConfig
from ..llm import LLMClient, create_llm_client
from ..llm.prompts import (
    API_TEST_PROMPT_TEMPLATE,
    API_TEST_SYSTEM_PROMPT,
    UNIT_TEST_PROMPT_TEMPLATE,
    UNIT_TEST_SYSTEM_PROMPT,
)
from ..parsers.code_parser import ClassInfo, FunctionInfo
from ..parsers.openapi import APIEndpoint


@dataclass
class GeneratedTest:
    """A generated test case."""

    name: str
    test_type: Literal["api", "unit", "integration"]
    source_file: str | None
    test_code: str
    language: str = "python"
    target_function: str | None = None
    target_class: str | None = None
    target_endpoint: str | None = None


class TestGenerator:
    """Generator for test cases using LLM."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        config: ProjectConfig | None = None,
    ):
        """Initialize test generator.

        Args:
            llm_client: LLM client to use for generation
            config: Project configuration
        """
        self.config = config or ProjectConfig()
        self.llm_client = llm_client

    async def _get_client(self) -> LLMClient:
        """Get or create LLM client."""
        if self.llm_client is None:
            self.llm_client = create_llm_client(config=self.config.llm)
        return self.llm_client

    async def generate_api_test(
        self,
        endpoint: APIEndpoint,
        base_url: str = "http://localhost:8000",
    ) -> GeneratedTest:
        """Generate API test for an endpoint.

        Args:
            endpoint: API endpoint to test
            base_url: Base URL for the API

        Returns:
            GeneratedTest with the generated code
        """
        client = await self._get_client()

        # Format parameters
        params_str = "\n".join(
            [
                f"  - {p.name} ({p.location}): {p.param_type}"
                + (", required" if p.required else ", optional")
                for p in endpoint.parameters
            ]
        ) or "None"

        # Format request body
        request_body_str = "None"
        if endpoint.request_body:
            import json
            request_body_str = json.dumps(endpoint.request_body, indent=2)

        # Format responses
        responses_str = "\n".join(
            [f"  - {code}: {resp.get('description', 'No description')}"
             for code, resp in endpoint.responses.items()]
        ) or "None"

        prompt = API_TEST_PROMPT_TEMPLATE.format(
            method=endpoint.method.upper(),
            path=endpoint.path,
            summary=endpoint.summary or "No summary",
            description=endpoint.description or "No description",
            parameters=params_str,
            request_body=request_body_str,
            responses=responses_str,
            base_url=base_url,
        )

        code = await client.generate_code(
            prompt=prompt,
            language="python",
            system_prompt=API_TEST_SYSTEM_PROMPT,
        )

        return GeneratedTest(
            name=f"test_{endpoint.operation_id or endpoint.path.replace('/', '_')}",
            test_type="api",
            source_file=None,
            test_code=code,
            target_endpoint=f"{endpoint.method.upper()} {endpoint.path}",
        )

    async def generate_unit_test(
        self,
        function: FunctionInfo,
    ) -> GeneratedTest:
        """Generate unit test for a function.

        Args:
            function: Function to generate tests for

        Returns:
            GeneratedTest with the generated code
        """
        client = await self._get_client()

        prompt = UNIT_TEST_PROMPT_TEMPLATE.format(
            file_path=function.file_path,
            source_code=function.source_code,
            docstring=function.docstring or "No docstring",
            parameters=", ".join(function.parameters) or "None",
            return_type=function.return_type or "Not specified",
        )

        code = await client.generate_code(
            prompt=prompt,
            language="python",
            system_prompt=UNIT_TEST_SYSTEM_PROMPT,
        )

        return GeneratedTest(
            name=f"test_{function.name}",
            test_type="unit",
            source_file=function.file_path,
            test_code=code,
            target_function=function.name,
            target_class=function.class_name,
        )

    async def generate_class_tests(
        self,
        class_info: ClassInfo,
    ) -> list[GeneratedTest]:
        """Generate unit tests for all methods in a class.

        Args:
            class_info: Class to generate tests for

        Returns:
            List of GeneratedTest for each method
        """
        tests = []

        # Generate tests for each method
        for method in class_info.methods:
            if method.name.startswith("_") and method.name != "__init__":
                continue  # Skip private methods except __init__

            test = await self.generate_unit_test(method)
            tests.append(test)

        return tests

    async def generate_tests_for_file(
        self,
        file_path: Path,
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
    ) -> list[GeneratedTest]:
        """Generate all tests for a source file.

        Args:
            file_path: Path to the source file
            functions: Functions in the file
            classes: Classes in the file

        Returns:
            List of all generated tests
        """
        tests = []

        # Generate tests for top-level functions
        for func in functions:
            if func.file_path == str(file_path) and not func.name.startswith("_"):
                test = await self.generate_unit_test(func)
                tests.append(test)

        # Generate tests for classes
        for cls in classes:
            if cls.file_path == str(file_path):
                class_tests = await self.generate_class_tests(cls)
                tests.extend(class_tests)

        return tests

    async def generate_api_tests_batch(
        self,
        endpoints: list[APIEndpoint],
        base_url: str = "http://localhost:8000",
        max_concurrent: int = 3,
    ) -> list[GeneratedTest]:
        """Generate API tests for multiple endpoints.

        Args:
            endpoints: List of endpoints to test
            base_url: Base URL for the API
            max_concurrent: Maximum concurrent LLM calls

        Returns:
            List of generated tests
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_with_semaphore(endpoint: APIEndpoint) -> GeneratedTest:
            async with semaphore:
                return await self.generate_api_test(endpoint, base_url)

        tasks = [generate_with_semaphore(ep) for ep in endpoints]
        return await asyncio.gather(*tasks)


class TestWriter:
    """Writer for saving generated tests to files."""

    def __init__(self, output_dir: Path):
        """Initialize test writer.

        Args:
            output_dir: Directory to write test files
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_test(self, test: GeneratedTest) -> Path:
        """Write a generated test to a file.

        Args:
            test: Generated test to write

        Returns:
            Path to the written file
        """
        # Determine file name
        if test.test_type == "api":
            file_name = f"test_api_{test.name}.py"
        elif test.target_class:
            file_name = f"test_{test.target_class.lower()}.py"
        else:
            file_name = f"{test.name}.py"

        file_path = self.output_dir / file_name

        # If file exists, append to it
        if file_path.exists():
            existing = file_path.read_text()
            # Avoid duplicate imports
            new_code = self._merge_test_code(existing, test.test_code)
            file_path.write_text(new_code)
        else:
            file_path.write_text(test.test_code)

        return file_path

    def _merge_test_code(self, existing: str, new: str) -> str:
        """Merge new test code with existing file.

        Avoids duplicate imports and maintains structure.
        """
        # Simple merge: append new tests after existing ones
        # A more sophisticated approach would parse and merge ASTs
        lines = existing.strip().split("\n")

        # Find where imports end
        import_end = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                import_end = i + 1

        # Extract new test functions (skip imports)
        new_lines = new.strip().split("\n")
        new_tests_start = 0
        for i, line in enumerate(new_lines):
            if line.startswith("def test_") or line.startswith("class Test"):
                new_tests_start = i
                break

        # Combine
        result = "\n".join(lines)
        if new_tests_start < len(new_lines):
            result += "\n\n" + "\n".join(new_lines[new_tests_start:])

        return result

    def write_all(self, tests: list[GeneratedTest]) -> list[Path]:
        """Write all generated tests.

        Args:
            tests: List of tests to write

        Returns:
            List of paths to written files
        """
        paths = []
        for test in tests:
            path = self.write_test(test)
            paths.append(path)
        return paths
