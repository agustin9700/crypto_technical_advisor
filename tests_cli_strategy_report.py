import subprocess
import os
import pytest

def test_cli_strategy_report_help():
    """Verifica que el nuevo flag aparezca en la ayuda."""
    result = subprocess.run(["python", "cli.py", "--help"], capture_output=True, text=True)
    assert "--strategy-report" in result.stdout
    assert "--from-date" in result.stdout
    assert "--out" in result.stdout

def test_cli_strategy_report_execution():
    """Verifica que el comando se ejecute sin errores (aunque la DB esté vacía)."""
    result = subprocess.run(["python", "cli.py", "--strategy-report"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Strategy Performance Comparison" in result.stdout

def test_cli_strategy_report_output_file():
    """Verifica que se genere el archivo Markdown."""
    out_path = "test_strategy_report.md"
    if os.path.exists(out_path):
        os.remove(out_path)
        
    result = subprocess.run(["python", "cli.py", "--strategy-report", "--out", out_path], capture_output=True, text=True)
    assert result.returncode == 0
    assert os.path.exists(out_path)
    
    with open(out_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "# Strategy Performance Comparison Report" in content
        assert "## Tabla Comparativa" in content
        
    os.remove(out_path)

if __name__ == "__main__":
    pytest.main([__file__])
