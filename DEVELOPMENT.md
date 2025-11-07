# Development Guide

This guide covers development setup and running the SVG welder from source code.

## Development Setup

### Prerequisites
- Python 3.10 or higher
- Git

### Initial Setup
```bash
# Clone the repository
git clone <repository-url>
cd svg-to-gcode-welder

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install in development mode with all dependencies
pip install -e .[validation,dev]

# Or install step by step
pip install -e .                    # Core package
pip install -e .[validation]        # With validation libraries
pip install pytest pytest-cov isort flake8 mypy pre-commit  # Dev tools
```

### Development Dependencies
The development environment includes:
- **pytest**: Testing framework
- **pytest-cov**: Coverage reporting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pre-commit**: Git hooks

### Optional Dependencies
- **lxml**: Enhanced SVG validation (install with `pip install -e .[validation]`)
- **gcodeparser**: G-code syntax validation (install with `pip install -e .[validation]`)

## Running Examples (Development)

### Using Virtual Environment (Recommended)
```bash
# Activate virtual environment first
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Basic example
svg-welder examples/example.svg

# Comprehensive sample
svg-welder examples/comprehensive_sample.svg

# With verbose output
svg-welder examples/example.svg --verbose

# Skip validation for faster processing
svg-welder examples/example.svg --no-validation

# Custom output location
svg-welder examples/example.svg -o my_output.gcode
```

### Alternative Methods
```bash
# Using Python module directly (with venv activated)
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
# Activate virtual environment first
source venv/bin/activate

# Check code formatting (required before commits)
make test-format
# or
black --check svg_welder tests

# Auto-format code
make format
# or
black svg_welder tests
isort svg_welder tests

# Lint code
flake8 svg_welder tests
mypy svg_welder

# Run all tests (includes formatting check)
make test
# or
pytest

# Run with coverage
pytest --cov=svg_welder --cov-report=html
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks (with venv activated)
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

### Testing
```bash
# Activate virtual environment first
source venv/bin/activate

# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/

# Run with coverage report
pytest --cov=svg_welder --cov-report=html --cov-report=term-missing
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
# Ensure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Verify installation
pip list | grep svg-welder
```

**Test Failures:**
```bash
# Activate virtual environment first
source venv/bin/activate

# Run specific test file
pytest tests/unit/test_models.py -v

# Run with debugging
pytest tests/unit/test_models.py -v -s
```

**Configuration Issues:**
```bash
# Validate configuration (with venv activated)
python -c "from svg_welder.core.config import Config; Config('config.toml').validate()"
```

## Building and Distribution

### Build Package
```bash
# Activate virtual environment first
source venv/bin/activate

# Build wheel and source distribution
python -m build

# Or install build tool first if needed
pip install build
python -m build
```

### Install Local Development Version
```bash
# Already done during setup, but if needed:
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
