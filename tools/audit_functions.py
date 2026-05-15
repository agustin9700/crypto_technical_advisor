import ast
import os
import re
from pathlib import Path

def get_python_files(root_dir):
    excluded_dirs = {".venv", "venv", ".git", "__pycache__", ".pytest_cache", "dist", "outputs", "backups", "brain"}
    py_files = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        for f in files:
            if f.endswith(".py"):
                py_files.append(Path(root) / f)
    return py_files

def audit_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    functions = []
    
    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.current_class = None

        def visit_ClassDef(self, node):
            old_class = self.current_class
            self.current_class = node.name
            doc = ast.get_docstring(node)
            functions.append({
                "type": "class",
                "name": node.name,
                "file": file_path.name,
                "line_start": node.lineno,
                "line_end": getattr(node, "end_lineno", node.lineno),
                "doc": doc,
                "parent": None
            })
            self.generic_visit(node)
            self.current_class = old_class

        def visit_FunctionDef(self, node):
            doc = ast.get_docstring(node)
            functions.append({
                "type": "method" if self.current_class else "function",
                "name": node.name,
                "file": file_path.name,
                "line_start": node.lineno,
                "line_end": getattr(node, "end_lineno", node.lineno),
                "doc": doc,
                "parent": self.current_class
            })
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)

    visitor = Visitor()
    visitor.visit(tree)
    return functions

def find_references(all_functions, py_files):
    # Cargar todos los contenidos
    file_contents = {}
    for f in py_files:
        with open(f, "r", encoding="utf-8", errors="ignore") as file:
            file_contents[f.name] = file.read()

    for func in all_functions:
        name = func["name"]
        refs = []
        
        # Ignorar nombres muy comunes o dunder
        if name.startswith("__") and name.endswith("__"):
            func["used_by"] = ["python_internal"]
            continue

        for filename, content in file_contents.items():
            # Buscar el nombre como palabra completa
            # Evitar contar la definición misma en el mismo archivo
            matches = re.findall(r"\b" + re.escape(name) + r"\b", content)
            
            # Restar 1 si es el archivo donde se define (la definición cuenta como 1)
            count = len(matches)
            if filename == func["file"]:
                count -= 1
            
            if count > 0:
                refs.append(filename)
        
        func["used_by"] = list(set(refs))

def generate_report(all_functions, py_files):
    summary = {
        "files": len(py_files),
        "functions": len([f for f in all_functions if f["type"] == "function"]),
        "classes": len([f for f in all_functions if f["type"] == "class"]),
        "methods": len([f for f in all_functions if f["type"] == "method"]),
    }
    
    unused = [f for f in all_functions if not f["used_by"] and not f["name"].startswith("_")]
    private = [f for f in all_functions if f["name"].startswith("_")]
    
    streamlit_used = [f for f in all_functions if "app.py" in f["used_by"]]
    cli_used = [f for f in all_functions if "cli.py" in f["used_by"]]
    tests_used = [f for f in all_functions if any(t.startswith("tests_") for t in f["used_by"])]

    report = [
        "# Function Inventory",
        "",
        "## Resumen",
        f"- Total archivos analizados: {summary['files']}",
        f"- Total funciones top-level: {summary['functions']}",
        f"- Total clases: {summary['classes']}",
        f"- Total métodos: {summary['methods']}",
        f"- Funciones/Métodos sin referencias externas directas: {len(unused)}",
        f"- Funciones privadas (empiezan con _): {len(private)}",
        f"- Usadas por Streamlit (app.py): {len(streamlit_used)}",
        f"- Usadas por CLI (cli.py): {len(cli_used)}",
        f"- Usadas por tests: {len(tests_used)}",
        "",
        "## Por archivo",
        ""
    ]
    
    files_sorted = sorted(list(set(f["file"] for f in all_functions)))
    for f_name in files_sorted:
        report.append(f"### {f_name}")
        report.append("| Función/Clase | Línea | Tipo | Usada por | Estado Sugerido |")
        report.append("|---|---:|---|---|---|")
        
        file_funcs = [f for f in all_functions if f["file"] == f_name]
        for func in sorted(file_funcs, key=lambda x: x["line_start"]):
            name = func["name"]
            if func["parent"]:
                name = f"{func['parent']}.{name}"
            
            used = ", ".join(func["used_by"]) if func["used_by"] else "None"
            
            # Lógica simple de estado
            state = "KEEP_CORE"
            if "app.py" in func["used_by"]: state = "KEEP_UI"
            if "cli.py" in func["used_by"]: state = "KEEP_CLI"
            if any(t.startswith("tests_") for t in func["used_by"]): state = "KEEP_TEST"
            if not func["used_by"] and not func["name"].startswith("_"):
                state = "UNUSED_CANDIDATE"
            if func["name"].startswith("_"):
                state = "PRIVATE_HELPER"

            report.append(f"| {name} | {func['line_start']} | {func['type']} | {used} | {state} |")
        report.append("")

    return "\n".join(report)

def main():
    root = Path(".")
    py_files = get_python_files(root)
    all_functions = []
    
    for f in py_files:
        all_functions.extend(audit_file(f))
    
    find_references(all_functions, py_files)
    
    report_md = generate_report(all_functions, py_files)
    
    with open("FUNCTION_INVENTORY.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    
    print(f"Inventario generado en FUNCTION_INVENTORY.md. Total funciones: {len(all_functions)}")

if __name__ == "__main__":
    main()
