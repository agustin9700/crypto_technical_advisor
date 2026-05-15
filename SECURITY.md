# Security

## Secrets

Do not commit API keys, API secrets, tokens, passwords or `.env` files.

Use environment variables:

```bash
export PAPER_API_KEY="tu_api_key"
export PAPER_API_SECRET="tu_api_secret"
```

For Windows CMD/PowerShell:

```bat
set PAPER_API_KEY=tu_api_key
set PAPER_API_SECRET=tu_api_secret
```

`.env.example` is safe to commit because values are empty or fake. A local `.env` is ignored by `.gitignore`.

## Packaging

Create clean artifacts with:

```bash
python tools/package_project.py --dry-run
python tools/package_project.py
```

The packager excludes `.git/`, virtualenvs, `outputs/`, caches, `.env`, logs, temporary files and prior archives.

## Trading Safety

This project is paper/analysis only. It must not be configured to place live orders without a separate security review, order-size limits and kill-switch controls.
