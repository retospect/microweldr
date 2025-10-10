# Development Guide

This guide covers development setup and running the SVG welder from source code.

## Development Setup

### Prerequisites
- Python 3.8.1 or higher
- Poetry (for dependency management)
- Git

### Initial Setup
```bash
# Clone the repository
git clone <repository-url>
cd svg-to-gcode-welder

# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Install with validation libraries (optional)
poetry install --extras validation

# Install development dependencies
poetry install --with dev

# Activate virtual environment
poetry shell
```

### Development Dependencies
The development environment includes:
- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pre-commit**: Git hooks

## Running Examples (Development)

### Using Poetry (Recommended)
```bash
# Basic example
poetry run svg-welder examples/example.svg

# Comprehensive sample
poetry run svg-welder examples/comprehensive_sample.svg

# With verbose output
poetry run svg-welder examples/example.svg --verbose

# Skip validation for faster processing
poetry run svg-welder examples/example.svg --no-validation

# Custom output location
poetry run svg-welder examples/example.svg -o my_output.gcode
```

### Using Python Module Directly
```bash
# Activate environment first
poetry shell

# Run as module
python -m svg_welder.cli.main examples/example.svg

# Or run the CLI script directly
python svg_welder/cli/main.py examples/example.svg
```

### Using Makefile (Development Shortcuts)
```bash
# Quick example run
make run-example

# Comprehensive sample
make run-comprehensive

# Install development environment
make install-dev

# Run tests
make test

# Run tests with coverage
make test-coverage

# Format code
make format

# Check code quality
make lint

# Clean build artifacts
make clean
```

## Development Workflow

### Code Quality
```bash
# Format code
make format
# or
poetry run black svg_welder tests
poetry run isort svg_welder tests

# Check formatting
make format-check

# Lint code
make lint
# or
poetry run flake8 svg_welder tests
poetry run mypy svg_welder

# Run all tests
make test

# Run with coverage
make test-coverage
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks
make install-pre-commit
# or
poetry run pre-commit install

# Run hooks manually
poetry run pre-commit run --all-files
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run unit tests only
make test-unit
# or
poetry run pytest tests/unit/

# Run integration tests only
make test-integration
# or
poetry run pytest tests/integration/

# Run with coverage report
poetry run pytest --cov=svg_welder --cov-report=html
```

## Project Structure (Development)

```
svg-welder/
├── svg_welder/              # Main package
│   ├── core/                # Core functionality
│   │   ├── models.py        # Data models
│   │   ├── config.py        # Configuration management
│   │   ├── converter.py     # Main converter
│   │   ├── svg_parser.py    # SVG parsing
│   │   └── gcode_generator.py # G-code generation
│   ├── validation/          # Validation modules
│   ├── animation/           # Animation generation
│   └── cli/                 # Command line interface
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── examples/               # Example files
├── pyproject.toml          # Poetry configuration
├── Makefile               # Development commands
└── README.md              # User documentation
```

## Adding New Features

### 1. Create Feature Branch
```bash
git checkout -b feature/my-new-feature
```

### 2. Implement Changes
- Add code to appropriate module in `svg_welder/`
- Add tests in `tests/unit/` or `tests/integration/`
- Update configuration if needed

### 3. Test Changes
```bash
# Run tests
make test

# Test with examples
make run-example
make run-comprehensive

# Check code quality
make lint
make format-check
```

### 4. Update Documentation
- Update README.md for user-facing changes
- Update DEVELOPMENT.md for development changes
- Add docstrings to new functions/classes

### 5. Commit and Push
```bash
git add .
git commit -m "Add new feature: description"
git push origin feature/my-new-feature
```

## Debugging

### Verbose Output
```bash
# See detailed processing information
poetry run svg-welder examples/example.svg --verbose
```

### Generated Files
```bash
# Check generated G-code
cat examples/example.gcode

# View animation in browser
open examples/example_animation.svg
```

### Common Development Issues

**Import Errors:**
```bash
# Ensure you're in the poetry environment
poetry shell
# or prefix commands with poetry run
```

**Test Failures:**
```bash
# Run specific test file
poetry run pytest tests/unit/test_models.py -v

# Run with debugging
poetry run pytest tests/unit/test_models.py -v -s
```

**Configuration Issues:**
```bash
# Validate configuration
poetry run python -c "from svg_welder.core.config import Config; Config('config.toml').validate()"
```

## Building and Distribution

### Build Package
```bash
# Build wheel and source distribution
make build
# or
poetry build
```

### Install Local Development Version
```bash
# Install in editable mode
pip install -e .

# Or install with extras
pip install -e .[validation]
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Update documentation
7. Submit a pull request

### Code Style Guidelines
- Follow PEP 8 (enforced by black and flake8)
- Add type hints to all functions
- Write docstrings for public functions
- Keep functions focused and small
- Add tests for new functionality

### Commit Message Format
```
Add feature: Brief description

Detailed explanation of changes:
- What was added/changed
- Why it was necessary
- Any breaking changes

Fixes #issue-number
```
