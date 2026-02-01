"""Code parser for extracting structure from source files."""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class FunctionInfo:
    """Information about a function."""

    name: str
    file_path: str
    line_number: int
    docstring: str = ""
    parameters: list[str] = field(default_factory=list)
    return_type: str | None = None
    is_async: bool = False
    is_method: bool = False
    class_name: str | None = None
    decorators: list[str] = field(default_factory=list)
    source_code: str = ""

    @property
    def full_name(self) -> str:
        """Get full qualified name."""
        if self.class_name:
            return f"{self.class_name}.{self.name}"
        return self.name


@dataclass
class ClassInfo:
    """Information about a class."""

    name: str
    file_path: str
    line_number: int
    docstring: str = ""
    base_classes: list[str] = field(default_factory=list)
    methods: list[FunctionInfo] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)


class CodeParser:
    """Parser for extracting code structure."""

    def __init__(self, language: Literal["python", "javascript", "typescript"] = "python"):
        self.language = language

    def parse_file(self, file_path: Path) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        """Parse a source file and extract functions and classes.

        Args:
            file_path: Path to the source file

        Returns:
            Tuple of (functions, classes)
        """
        if self.language == "python":
            return self._parse_python(file_path)
        else:
            # For JS/TS, we'll use a simpler regex-based approach for now
            # Full support would need tree-sitter (Phase 2)
            return self._parse_javascript_simple(file_path)

    def _parse_python(self, file_path: Path) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        """Parse Python source file using AST."""
        source = file_path.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return [], []

        functions = []
        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Skip methods (they're handled in class parsing)
                if self._is_top_level(node, tree):
                    func_info = self._extract_function_info(node, file_path, source)
                    functions.append(func_info)

            elif isinstance(node, ast.ClassDef):
                class_info = self._extract_class_info(node, file_path, source)
                classes.append(class_info)

        return functions, classes

    def _is_top_level(self, node: ast.AST, tree: ast.Module) -> bool:
        """Check if node is at module level."""
        return node in tree.body

    def _extract_function_info(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, file_path: Path, source: str
    ) -> FunctionInfo:
        """Extract function information from AST node."""
        # Get parameters
        params = []
        for arg in node.args.args:
            param_str = arg.arg
            if arg.annotation:
                param_str += f": {ast.unparse(arg.annotation)}"
            params.append(param_str)

        # Get return type
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)

        # Get decorators
        decorators = [ast.unparse(d) for d in node.decorator_list]

        # Get source code
        source_lines = source.split("\n")
        end_lineno = getattr(node, "end_lineno", node.lineno)
        source_code = "\n".join(source_lines[node.lineno - 1 : end_lineno])

        return FunctionInfo(
            name=node.name,
            file_path=str(file_path),
            line_number=node.lineno,
            docstring=ast.get_docstring(node) or "",
            parameters=params,
            return_type=return_type,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decorators,
            source_code=source_code,
        )

    def _extract_class_info(self, node: ast.ClassDef, file_path: Path, source: str) -> ClassInfo:
        """Extract class information from AST node."""
        # Get base classes
        bases = [ast.unparse(base) for base in node.bases]

        # Get decorators
        decorators = [ast.unparse(d) for d in node.decorator_list]

        # Get methods
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = self._extract_function_info(item, file_path, source)
                func_info.is_method = True
                func_info.class_name = node.name
                methods.append(func_info)

        return ClassInfo(
            name=node.name,
            file_path=str(file_path),
            line_number=node.lineno,
            docstring=ast.get_docstring(node) or "",
            base_classes=bases,
            methods=methods,
            decorators=decorators,
        )

    def _parse_javascript_simple(
        self, file_path: Path
    ) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        """Simple regex-based JS/TS parsing (placeholder for tree-sitter)."""
        source = file_path.read_text()
        functions = []
        classes = []

        # Find function declarations
        func_pattern = r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"
        for match in re.finditer(func_pattern, source):
            line_num = source[: match.start()].count("\n") + 1
            params = [p.strip() for p in match.group(2).split(",") if p.strip()]
            functions.append(
                FunctionInfo(
                    name=match.group(1),
                    file_path=str(file_path),
                    line_number=line_num,
                    parameters=params,
                    is_async="async" in match.group(0),
                )
            )

        # Find arrow functions
        arrow_pattern = r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>"
        for match in re.finditer(arrow_pattern, source):
            line_num = source[: match.start()].count("\n") + 1
            functions.append(
                FunctionInfo(
                    name=match.group(1),
                    file_path=str(file_path),
                    line_number=line_num,
                    is_async="async" in match.group(0),
                )
            )

        # Find classes
        class_pattern = r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?"
        for match in re.finditer(class_pattern, source):
            line_num = source[: match.start()].count("\n") + 1
            bases = [match.group(2)] if match.group(2) else []
            classes.append(
                ClassInfo(
                    name=match.group(1),
                    file_path=str(file_path),
                    line_number=line_num,
                    base_classes=bases,
                )
            )

        return functions, classes


def detect_language(file_path: Path) -> str | None:
    """Detect programming language from file extension."""
    extension_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".java": "java",
        ".rs": "rust",
        ".rb": "ruby",
    }
    return extension_map.get(file_path.suffix.lower())
