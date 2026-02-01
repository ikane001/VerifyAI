"""Tree-sitter based multi-language code parser."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Any
import logging

try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
    import tree_sitter_go as tsgo
    import tree_sitter_java as tsjava
    from tree_sitter import Language, Parser, Node
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Parser = None
    Node = None

from .code_parser import FunctionInfo, ClassInfo, detect_language

logger = logging.getLogger(__name__)

# Supported languages
SupportedLanguage = Literal["python", "javascript", "typescript", "go", "java"]


@dataclass
class ImportInfo:
    """Information about an import statement."""

    module: str
    names: list[str] = field(default_factory=list)
    alias: str | None = None
    line_number: int = 0
    is_relative: bool = False


@dataclass
class DependencyInfo:
    """Dependency information for a file."""

    file_path: str
    imports: list[ImportInfo] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # Module names this file depends on


class TreeSitterParser:
    """Multi-language code parser using tree-sitter."""

    def __init__(self):
        """Initialize the tree-sitter parser."""
        if not TREE_SITTER_AVAILABLE:
            raise ImportError(
                "tree-sitter packages not installed. "
                "Install with: pip install tree-sitter tree-sitter-python tree-sitter-javascript ..."
            )

        self._parsers: dict[str, Parser] = {}
        self._languages: dict[str, Language] = {}
        self._init_languages()

    def _init_languages(self):
        """Initialize language parsers."""
        language_modules = {
            "python": tspython,
            "javascript": tsjavascript,
            "go": tsgo,
            "java": tsjava,
        }

        for lang_name, module in language_modules.items():
            try:
                language = Language(module.language())
                parser = Parser(language)
                self._languages[lang_name] = language
                self._parsers[lang_name] = parser
                logger.debug(f"Initialized {lang_name} parser")
            except Exception as e:
                logger.warning(f"Failed to initialize {lang_name} parser: {e}")

        # TypeScript has separate language functions for ts and tsx
        try:
            # Try typescript language
            ts_lang = Language(tstypescript.language_typescript())
            ts_parser = Parser(ts_lang)
            self._languages["typescript"] = ts_lang
            self._parsers["typescript"] = ts_parser
            logger.debug("Initialized typescript parser")
        except Exception as e:
            # Fallback: use javascript parser for typescript
            if "javascript" in self._parsers:
                self._parsers["typescript"] = self._parsers["javascript"]
                self._languages["typescript"] = self._languages["javascript"]
                logger.debug("Using javascript parser as fallback for typescript")
            else:
                logger.warning(f"Failed to initialize typescript parser: {e}")

    def get_parser(self, language: str) -> Parser | None:
        """Get parser for a specific language."""
        # Handle typescript variants
        if language in ("typescript", "tsx"):
            language = "typescript"
        elif language in ("javascript", "jsx"):
            language = "javascript"

        return self._parsers.get(language)

    def parse_file(self, file_path: Path) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        """Parse a source file and extract functions and classes.

        Args:
            file_path: Path to the source file

        Returns:
            Tuple of (functions, classes)
        """
        language = detect_language(file_path)
        if not language or language not in self._parsers:
            return [], []

        try:
            source = file_path.read_bytes()
            tree = self._parsers[language].parse(source)
            root_node = tree.root_node

            if language == "python":
                return self._parse_python(root_node, file_path, source.decode())
            elif language in ("javascript", "typescript"):
                return self._parse_javascript(root_node, file_path, source.decode())
            elif language == "go":
                return self._parse_go(root_node, file_path, source.decode())
            elif language == "java":
                return self._parse_java(root_node, file_path, source.decode())
            else:
                return [], []

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return [], []

    def parse_imports(self, file_path: Path) -> DependencyInfo:
        """Parse import statements from a file.

        Args:
            file_path: Path to the source file

        Returns:
            DependencyInfo with imports and dependencies
        """
        language = detect_language(file_path)
        if not language or language not in self._parsers:
            return DependencyInfo(file_path=str(file_path))

        try:
            source = file_path.read_bytes()
            tree = self._parsers[language].parse(source)
            root_node = tree.root_node

            if language == "python":
                return self._parse_python_imports(root_node, file_path, source.decode())
            elif language in ("javascript", "typescript"):
                return self._parse_js_imports(root_node, file_path, source.decode())
            elif language == "go":
                return self._parse_go_imports(root_node, file_path, source.decode())
            elif language == "java":
                return self._parse_java_imports(root_node, file_path, source.decode())
            else:
                return DependencyInfo(file_path=str(file_path))

        except Exception as e:
            logger.error(f"Error parsing imports from {file_path}: {e}")
            return DependencyInfo(file_path=str(file_path))

    # ========== Python Parsing ==========

    def _parse_python(
        self, root: Node, file_path: Path, source: str
    ) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        """Parse Python source code."""
        functions = []
        classes = []

        for child in root.children:
            if child.type == "function_definition":
                func = self._extract_python_function(child, file_path, source)
                if func:
                    functions.append(func)

            elif child.type == "decorated_definition":
                # Handle decorated functions/classes
                for subchild in child.children:
                    if subchild.type == "function_definition":
                        func = self._extract_python_function(subchild, file_path, source, child)
                        if func:
                            functions.append(func)
                    elif subchild.type == "class_definition":
                        cls = self._extract_python_class(subchild, file_path, source, child)
                        if cls:
                            classes.append(cls)

            elif child.type == "class_definition":
                cls = self._extract_python_class(child, file_path, source)
                if cls:
                    classes.append(cls)

        return functions, classes

    def _extract_python_function(
        self, node: Node, file_path: Path, source: str, decorated_node: Node | None = None
    ) -> FunctionInfo | None:
        """Extract function info from Python AST node."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_node_text(name_node, source)
        params_node = node.child_by_field_name("parameters")
        return_type_node = node.child_by_field_name("return_type")

        # Get parameters
        parameters = []
        if params_node:
            for param in params_node.children:
                if param.type in ("identifier", "typed_parameter", "default_parameter"):
                    param_text = self._get_node_text(param, source)
                    if param_text and param_text not in ("(", ")", ",", "self", "cls"):
                        parameters.append(param_text)

        # Get return type
        return_type = None
        if return_type_node:
            return_type = self._get_node_text(return_type_node, source)

        # Get docstring
        docstring = self._get_python_docstring(node, source)

        # Get decorators
        decorators = []
        if decorated_node:
            for child in decorated_node.children:
                if child.type == "decorator":
                    decorators.append(self._get_node_text(child, source).lstrip("@"))

        # Check if async
        is_async = any(c.type == "async" for c in node.children)

        # Get source code
        source_code = self._get_node_text(decorated_node or node, source)

        return FunctionInfo(
            name=name,
            file_path=str(file_path),
            line_number=node.start_point[0] + 1,
            docstring=docstring,
            parameters=parameters,
            return_type=return_type,
            is_async=is_async,
            decorators=decorators,
            source_code=source_code,
        )

    def _extract_python_class(
        self, node: Node, file_path: Path, source: str, decorated_node: Node | None = None
    ) -> ClassInfo | None:
        """Extract class info from Python AST node."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_node_text(name_node, source)

        # Get base classes
        base_classes = []
        superclass_node = node.child_by_field_name("superclasses")
        if superclass_node:
            for child in superclass_node.children:
                if child.type in ("identifier", "attribute"):
                    base_classes.append(self._get_node_text(child, source))

        # Get docstring
        docstring = self._get_python_docstring(node, source)

        # Get decorators
        decorators = []
        if decorated_node:
            for child in decorated_node.children:
                if child.type == "decorator":
                    decorators.append(self._get_node_text(child, source).lstrip("@"))

        # Get methods
        methods = []
        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                if child.type == "function_definition":
                    method = self._extract_python_function(child, file_path, source)
                    if method:
                        method.is_method = True
                        method.class_name = name
                        methods.append(method)
                elif child.type == "decorated_definition":
                    for subchild in child.children:
                        if subchild.type == "function_definition":
                            method = self._extract_python_function(subchild, file_path, source, child)
                            if method:
                                method.is_method = True
                                method.class_name = name
                                methods.append(method)

        return ClassInfo(
            name=name,
            file_path=str(file_path),
            line_number=node.start_point[0] + 1,
            docstring=docstring,
            base_classes=base_classes,
            methods=methods,
            decorators=decorators,
        )

    def _get_python_docstring(self, node: Node, source: str) -> str:
        """Extract docstring from a Python function or class."""
        body = node.child_by_field_name("body")
        if not body or not body.children:
            return ""

        first_stmt = body.children[0]
        if first_stmt.type == "expression_statement":
            expr = first_stmt.children[0] if first_stmt.children else None
            if expr and expr.type == "string":
                docstring = self._get_node_text(expr, source)
                # Remove quotes
                if docstring.startswith('"""') or docstring.startswith("'''"):
                    return docstring[3:-3].strip()
                elif docstring.startswith('"') or docstring.startswith("'"):
                    return docstring[1:-1].strip()
        return ""

    def _parse_python_imports(
        self, root: Node, file_path: Path, source: str
    ) -> DependencyInfo:
        """Parse Python import statements."""
        imports = []
        dependencies = set()

        for child in root.children:
            if child.type == "import_statement":
                # import foo, bar
                for name_node in child.children:
                    if name_node.type == "dotted_name":
                        module = self._get_node_text(name_node, source)
                        imports.append(ImportInfo(
                            module=module,
                            line_number=child.start_point[0] + 1,
                        ))
                        dependencies.add(module.split(".")[0])

            elif child.type == "import_from_statement":
                # from foo import bar
                module_node = child.child_by_field_name("module_name")
                module = self._get_node_text(module_node, source) if module_node else ""

                names = []
                for name_node in child.children:
                    if name_node.type == "dotted_name" and name_node != module_node:
                        names.append(self._get_node_text(name_node, source))
                    elif name_node.type == "aliased_import":
                        name = name_node.child_by_field_name("name")
                        if name:
                            names.append(self._get_node_text(name, source))

                is_relative = source[child.start_byte:child.end_byte].count("from .") > 0

                imports.append(ImportInfo(
                    module=module,
                    names=names,
                    line_number=child.start_point[0] + 1,
                    is_relative=is_relative,
                ))

                if module and not is_relative:
                    dependencies.add(module.split(".")[0])

        return DependencyInfo(
            file_path=str(file_path),
            imports=imports,
            dependencies=list(dependencies),
        )

    # ========== JavaScript/TypeScript Parsing ==========

    def _parse_javascript(
        self, root: Node, file_path: Path, source: str
    ) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        """Parse JavaScript/TypeScript source code."""
        functions = []
        classes = []

        def traverse(node: Node):
            if node.type == "function_declaration":
                func = self._extract_js_function(node, file_path, source)
                if func:
                    functions.append(func)

            elif node.type == "lexical_declaration":
                # const foo = () => {} or const foo = function() {}
                for child in node.children:
                    if child.type == "variable_declarator":
                        func = self._extract_js_arrow_function(child, file_path, source)
                        if func:
                            functions.append(func)

            elif node.type == "class_declaration":
                cls = self._extract_js_class(node, file_path, source)
                if cls:
                    classes.append(cls)

            elif node.type == "export_statement":
                for child in node.children:
                    if child.type == "function_declaration":
                        func = self._extract_js_function(child, file_path, source)
                        if func:
                            functions.append(func)
                    elif child.type == "class_declaration":
                        cls = self._extract_js_class(child, file_path, source)
                        if cls:
                            classes.append(cls)

            for child in node.children:
                traverse(child)

        traverse(root)
        return functions, classes

    def _extract_js_function(
        self, node: Node, file_path: Path, source: str
    ) -> FunctionInfo | None:
        """Extract function info from JS/TS AST node."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_node_text(name_node, source)
        params_node = node.child_by_field_name("parameters")

        parameters = []
        if params_node:
            for param in params_node.children:
                if param.type in ("identifier", "required_parameter", "optional_parameter"):
                    param_text = self._get_node_text(param, source)
                    if param_text and param_text not in ("(", ")", ","):
                        parameters.append(param_text)

        # Check for async
        is_async = any(c.type == "async" for c in node.children)

        return FunctionInfo(
            name=name,
            file_path=str(file_path),
            line_number=node.start_point[0] + 1,
            parameters=parameters,
            is_async=is_async,
            source_code=self._get_node_text(node, source),
        )

    def _extract_js_arrow_function(
        self, node: Node, file_path: Path, source: str
    ) -> FunctionInfo | None:
        """Extract arrow function info."""
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")

        if not name_node or not value_node:
            return None

        if value_node.type not in ("arrow_function", "function"):
            return None

        name = self._get_node_text(name_node, source)

        parameters = []
        params_node = value_node.child_by_field_name("parameters")
        if params_node:
            for param in params_node.children:
                if param.type in ("identifier", "required_parameter", "optional_parameter"):
                    param_text = self._get_node_text(param, source)
                    if param_text and param_text not in ("(", ")", ","):
                        parameters.append(param_text)

        is_async = any(c.type == "async" for c in value_node.children)

        return FunctionInfo(
            name=name,
            file_path=str(file_path),
            line_number=node.start_point[0] + 1,
            parameters=parameters,
            is_async=is_async,
            source_code=self._get_node_text(node.parent, source) if node.parent else "",
        )

    def _extract_js_class(
        self, node: Node, file_path: Path, source: str
    ) -> ClassInfo | None:
        """Extract class info from JS/TS AST node."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_node_text(name_node, source)

        # Get base class
        base_classes = []
        heritage = node.child_by_field_name("heritage")
        if heritage:
            for child in heritage.children:
                if child.type == "identifier":
                    base_classes.append(self._get_node_text(child, source))

        # Get methods
        methods = []
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if child.type == "method_definition":
                    method = self._extract_js_method(child, file_path, source, name)
                    if method:
                        methods.append(method)

        return ClassInfo(
            name=name,
            file_path=str(file_path),
            line_number=node.start_point[0] + 1,
            base_classes=base_classes,
            methods=methods,
        )

    def _extract_js_method(
        self, node: Node, file_path: Path, source: str, class_name: str
    ) -> FunctionInfo | None:
        """Extract method info from JS/TS class."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_node_text(name_node, source)

        parameters = []
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for param in params_node.children:
                if param.type in ("identifier", "required_parameter", "optional_parameter"):
                    param_text = self._get_node_text(param, source)
                    if param_text and param_text not in ("(", ")", ","):
                        parameters.append(param_text)

        is_async = any(c.type == "async" for c in node.children)

        return FunctionInfo(
            name=name,
            file_path=str(file_path),
            line_number=node.start_point[0] + 1,
            parameters=parameters,
            is_async=is_async,
            is_method=True,
            class_name=class_name,
            source_code=self._get_node_text(node, source),
        )

    def _parse_js_imports(
        self, root: Node, file_path: Path, source: str
    ) -> DependencyInfo:
        """Parse JavaScript/TypeScript import statements."""
        imports = []
        exports = []
        dependencies = set()

        def traverse(node: Node):
            if node.type == "import_statement":
                source_node = node.child_by_field_name("source")
                if source_node:
                    module = self._get_node_text(source_node, source).strip("'\"")
                    names = []
                    for child in node.children:
                        if child.type == "import_specifier":
                            name = child.child_by_field_name("name")
                            if name:
                                names.append(self._get_node_text(name, source))
                        elif child.type == "identifier":
                            names.append(self._get_node_text(child, source))

                    imports.append(ImportInfo(
                        module=module,
                        names=names,
                        line_number=node.start_point[0] + 1,
                        is_relative=module.startswith("."),
                    ))

                    if not module.startswith("."):
                        dependencies.add(module.split("/")[0])

            elif node.type == "export_statement":
                for child in node.children:
                    if child.type in ("function_declaration", "class_declaration"):
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            exports.append(self._get_node_text(name_node, source))

            for child in node.children:
                traverse(child)

        traverse(root)

        return DependencyInfo(
            file_path=str(file_path),
            imports=imports,
            exports=exports,
            dependencies=list(dependencies),
        )

    # ========== Go Parsing ==========

    def _parse_go(
        self, root: Node, file_path: Path, source: str
    ) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        """Parse Go source code."""
        functions = []
        classes = []  # Go doesn't have classes, but we can extract types

        for child in root.children:
            if child.type == "function_declaration":
                func = self._extract_go_function(child, file_path, source)
                if func:
                    functions.append(func)

            elif child.type == "method_declaration":
                func = self._extract_go_method(child, file_path, source)
                if func:
                    functions.append(func)

            elif child.type == "type_declaration":
                # Extract struct types as "classes"
                for spec in child.children:
                    if spec.type == "type_spec":
                        name_node = spec.child_by_field_name("name")
                        type_node = spec.child_by_field_name("type")
                        if name_node and type_node and type_node.type == "struct_type":
                            classes.append(ClassInfo(
                                name=self._get_node_text(name_node, source),
                                file_path=str(file_path),
                                line_number=spec.start_point[0] + 1,
                            ))

        return functions, classes

    def _extract_go_function(
        self, node: Node, file_path: Path, source: str
    ) -> FunctionInfo | None:
        """Extract function info from Go AST node."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_node_text(name_node, source)
        params_node = node.child_by_field_name("parameters")

        parameters = []
        if params_node:
            for param in params_node.children:
                if param.type == "parameter_declaration":
                    param_text = self._get_node_text(param, source)
                    parameters.append(param_text)

        return FunctionInfo(
            name=name,
            file_path=str(file_path),
            line_number=node.start_point[0] + 1,
            parameters=parameters,
            source_code=self._get_node_text(node, source),
        )

    def _extract_go_method(
        self, node: Node, file_path: Path, source: str
    ) -> FunctionInfo | None:
        """Extract method info from Go AST node."""
        name_node = node.child_by_field_name("name")
        receiver_node = node.child_by_field_name("receiver")

        if not name_node:
            return None

        name = self._get_node_text(name_node, source)

        # Extract receiver type as class name
        class_name = None
        if receiver_node:
            for child in receiver_node.children:
                if child.type == "parameter_declaration":
                    type_node = child.child_by_field_name("type")
                    if type_node:
                        class_name = self._get_node_text(type_node, source).lstrip("*")

        params_node = node.child_by_field_name("parameters")
        parameters = []
        if params_node:
            for param in params_node.children:
                if param.type == "parameter_declaration":
                    param_text = self._get_node_text(param, source)
                    parameters.append(param_text)

        return FunctionInfo(
            name=name,
            file_path=str(file_path),
            line_number=node.start_point[0] + 1,
            parameters=parameters,
            is_method=True,
            class_name=class_name,
            source_code=self._get_node_text(node, source),
        )

    def _parse_go_imports(
        self, root: Node, file_path: Path, source: str
    ) -> DependencyInfo:
        """Parse Go import statements."""
        imports = []
        dependencies = set()

        for child in root.children:
            if child.type == "import_declaration":
                for spec in child.children:
                    if spec.type == "import_spec":
                        path_node = spec.child_by_field_name("path")
                        if path_node:
                            module = self._get_node_text(path_node, source).strip('"')
                            imports.append(ImportInfo(
                                module=module,
                                line_number=spec.start_point[0] + 1,
                            ))
                            # Get package name from import path
                            pkg_name = module.split("/")[-1]
                            dependencies.add(pkg_name)

        return DependencyInfo(
            file_path=str(file_path),
            imports=imports,
            dependencies=list(dependencies),
        )

    # ========== Java Parsing ==========

    def _parse_java(
        self, root: Node, file_path: Path, source: str
    ) -> tuple[list[FunctionInfo], list[ClassInfo]]:
        """Parse Java source code."""
        functions = []
        classes = []

        def traverse(node: Node):
            if node.type == "class_declaration":
                cls = self._extract_java_class(node, file_path, source)
                if cls:
                    classes.append(cls)
                    functions.extend(cls.methods)

            for child in node.children:
                traverse(child)

        traverse(root)
        return functions, classes

    def _extract_java_class(
        self, node: Node, file_path: Path, source: str
    ) -> ClassInfo | None:
        """Extract class info from Java AST node."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_node_text(name_node, source)

        # Get base class and interfaces
        base_classes = []
        superclass = node.child_by_field_name("superclass")
        if superclass:
            for child in superclass.children:
                if child.type == "type_identifier":
                    base_classes.append(self._get_node_text(child, source))

        interfaces = node.child_by_field_name("interfaces")
        if interfaces:
            for child in interfaces.children:
                if child.type == "type_identifier":
                    base_classes.append(self._get_node_text(child, source))

        # Get methods
        methods = []
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if child.type == "method_declaration":
                    method = self._extract_java_method(child, file_path, source, name)
                    if method:
                        methods.append(method)

        return ClassInfo(
            name=name,
            file_path=str(file_path),
            line_number=node.start_point[0] + 1,
            base_classes=base_classes,
            methods=methods,
        )

    def _extract_java_method(
        self, node: Node, file_path: Path, source: str, class_name: str
    ) -> FunctionInfo | None:
        """Extract method info from Java AST node."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._get_node_text(name_node, source)

        params_node = node.child_by_field_name("parameters")
        parameters = []
        if params_node:
            for param in params_node.children:
                if param.type == "formal_parameter":
                    param_text = self._get_node_text(param, source)
                    parameters.append(param_text)

        # Get return type
        return_type = None
        type_node = node.child_by_field_name("type")
        if type_node:
            return_type = self._get_node_text(type_node, source)

        return FunctionInfo(
            name=name,
            file_path=str(file_path),
            line_number=node.start_point[0] + 1,
            parameters=parameters,
            return_type=return_type,
            is_method=True,
            class_name=class_name,
            source_code=self._get_node_text(node, source),
        )

    def _parse_java_imports(
        self, root: Node, file_path: Path, source: str
    ) -> DependencyInfo:
        """Parse Java import statements."""
        imports = []
        dependencies = set()

        for child in root.children:
            if child.type == "import_declaration":
                for name_node in child.children:
                    if name_node.type == "scoped_identifier":
                        module = self._get_node_text(name_node, source)
                        imports.append(ImportInfo(
                            module=module,
                            line_number=child.start_point[0] + 1,
                        ))
                        # Get package name
                        parts = module.split(".")
                        if len(parts) >= 2:
                            dependencies.add(f"{parts[0]}.{parts[1]}")

        return DependencyInfo(
            file_path=str(file_path),
            imports=imports,
            dependencies=list(dependencies),
        )

    # ========== Utility Methods ==========

    def _get_node_text(self, node: Node, source: str) -> str:
        """Get the text content of a node."""
        if node is None:
            return ""
        return source[node.start_byte:node.end_byte]


def create_parser() -> TreeSitterParser | None:
    """Create a tree-sitter parser if available.

    Returns:
        TreeSitterParser instance or None if tree-sitter is not installed.
    """
    if not TREE_SITTER_AVAILABLE:
        return None
    try:
        return TreeSitterParser()
    except Exception as e:
        logger.warning(f"Failed to create tree-sitter parser: {e}")
        return None
