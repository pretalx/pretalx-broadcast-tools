set shell := ["bash", "-euo", "pipefail", "-c"]
set positional-arguments

# Format Django templates with djhtml
[group('linting')]
djhtml *args="":
    find . -name "*.html" -not -path '*/.venv/*' -not -path '*/vendored/*' -not -path '*/node_modules/*' -not -path '*/htmlcov/*' -not -path '*dist/*' -not -path "*.min.html" -print | xargs uv run --extra=dev djhtml "$@"

# Run ruff format
[group('linting')]
format *args=".":
    uv run --extra=dev ruff format "$@"

# Run ruff check
[group('linting')]
check *args=".":
    uv run --extra=dev ruff check "$@"

# Run all formatters and linters
[group('linting')]
[parallel]
fmt: format (check "--fix") djhtml

# Check Django templates with djhtml (check only)
[group('linting')]
djhtml-check:
    just djhtml --check

# Run all code quality checks
[group('linting')]
fmt-check: (format "--check") check djhtml-check

# Run tests (installs pretalx if not already present)
[group('testing')]
test *args="":
    uv run --extra=dev python -c "import pretalx" 2>/dev/null || just install-pretalx
    uv run --extra=dev pytest tests "$@"

# Install pretalx from git
[group('testing')]
install-pretalx:
    uv pip install "pretalx[dev] @ git+https://github.com/pretalx/pretalx@main"

# Install a local editable copy of pretalx (for development)
[group('testing')]
install-pretalx-local path:
    uv pip install -e "$1[dev]"

# Compile locale files
localecompile:
    django-admin compilemessages

# Generate locale files
localegen:
    django-admin makemessages -l de_DE -i build -i dist -i "*egg*" `find pretalx_broadcast_tools/locale/ -mindepth 1 -maxdepth 1 -type d -printf "-l %f "`
