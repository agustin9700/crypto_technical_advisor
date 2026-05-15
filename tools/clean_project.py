import os
import shutil
import argparse
from datetime import datetime

def clean_project(dry_run=True, clean_outputs=False, backup_outputs=False):
    print(f"{'DRY RUN: ' if dry_run else ''}Iniciando limpieza del proyecto...")
    
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # Directorios a eliminar
    dirs_to_remove = [
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "brain",
        "dist",
    ]
    
    # Extensiones de archivos a eliminar
    files_to_remove_ext = [".pyc", ".pyo", ".log", ".tmp", ".bak"]
    
    # Archivos específicos a eliminar
    files_to_remove_names = [".DS_Store", "Thumbs.db"]

    # Backup de outputs si se solicita
    if backup_outputs:
        outputs_dir = os.path.join(root_dir, "outputs")
        if os.path.exists(outputs_dir):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(root_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_file = os.path.join(backup_dir, f"outputs_backup_{timestamp}")
            if dry_run:
                print(f"  [WILL BACKUP] {outputs_dir} -> {backup_file}.zip")
            else:
                shutil.make_archive(backup_file, 'zip', outputs_dir)
                print(f"  [BACKUP DONE] {backup_file}.zip")

    # Escaneo y eliminación
    for root, dirs, files in os.walk(root_dir):
        # Excluir carpetas sensibles de la búsqueda recursiva
        if any(exc in root for exc in [".git", ".venv", "venv", "backups"]):
            continue

        for d in dirs:
            if d in dirs_to_remove:
                path = os.path.join(root, d)
                if dry_run:
                    print(f"  [WILL REMOVE DIR] {path}")
                else:
                    shutil.rmtree(path, ignore_errors=True)
                    print(f"  [REMOVED DIR] {path}")
        
        for f in files:
            if any(f.endswith(ext) for ext in files_to_remove_ext) or f in files_to_remove_names:
                path = os.path.join(root, f)
                if dry_run:
                    print(f"  [WILL REMOVE FILE] {path}")
                else:
                    os.remove(path)
                    print(f"  [REMOVED FILE] {path}")

    # Limpieza de outputs
    if clean_outputs:
        outputs_dir = os.path.join(root_dir, "outputs")
        if os.path.exists(outputs_dir):
            for f in os.listdir(outputs_dir):
                if f == ".gitkeep":
                    continue
                path = os.path.join(outputs_dir, f)
                if dry_run:
                    print(f"  [WILL REMOVE OUTPUT] {path}")
                else:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    print(f"  [REMOVED OUTPUT] {path}")

    print("Limpieza finalizada.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean project temporary files and caches.")
    parser.add_argument("--apply", action="store_true", help="Apply the changes (default is dry-run)")
    parser.add_argument("--clean-outputs", action="store_true", help="Clean the contents of outputs/ folder")
    parser.add_argument("--backup-outputs", action="store_true", help="Create a backup of outputs/ before cleaning")
    
    args = parser.parse_args()
    clean_project(dry_run=not args.apply, clean_outputs=args.clean_outputs, backup_outputs=args.backup_outputs)
