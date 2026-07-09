set shell := ["bash", "-euo", "pipefail", "-c"]
set quiet
set fallback
set positional-arguments
set default-list

uv_dev := "uv run --extra=dev"

# Run ruff format
[group('linting')]
format *args=".":
    {{ uv_dev }} ruff format "$@"

# Run ruff check
[group('linting')]
check *args=".":
    {{ uv_dev }} ruff check "$@"

# Format Django templates with djangofmt.
[group('linting')]
djangofmt *args="":
    -{{ uv_dev }} djangofmt {{ args }} .

[group('linting')]
djangofmt-check:
    just djangofmt
    git diff --exit-code -- '*.html' || (echo "HTML templates are not formatted. Run 'just djangofmt' to fix." && exit 1)

# Run all formatters and linters
[group('linting')]
[parallel]
fmt: format (check "--fix") djangofmt && fmt-done

[private]
fmt-done:
    echo '{{ GREEN }}Formatting complete{{ NORMAL }}'

# Run all code quality checks
[group('linting')]
fmt-check: (format "--check") check djangofmt-check && check-done

[private]
check-done:
    echo '{{ GREEN }}All checks passed{{ NORMAL }}'

# Run tests (installs pretalx if not already present)
[group('tests')]
test *args: ensure-pretalx
    {{ uv_dev }} pytest "$@"

# Install pretalx from git
[group('development')]
install-pretalx:
    uv pip install "pretalx[dev] @ git+https://github.com/pretalx/pretalx@main"

# Install a local editable copy of pretalx (for development)
[group('development')]
install-pretalx-local path:
    uv pip install -e "{{ path }}[dev]"

# Ensure pretalx is importable, installing it from git if needed
[private]
ensure-pretalx:
    {{ uv_dev }} python -c "import pretalx" 2>/dev/null || just install-pretalx

# Generate locale files
[group('development')]
[script('bash')]
localegen: ensure-pretalx
    module=$(find . -maxdepth 1 -type d -name 'pretalx_*' -not -name '*.egg-info' | head -1)
    {{ uv_dev }} django-admin makemessages --add-location file -i build -i dist -i "*egg*" $(find "$module/locale/" -mindepth 1 -maxdepth 1 -type d -printf "-l %f " 2>/dev/null)

# Compile locale files
[group('development')]
localecompile: ensure-pretalx
    {{ uv_dev }} django-admin compilemessages
