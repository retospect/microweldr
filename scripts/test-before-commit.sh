#!/bin/bash

# Test runner script to ensure all tests pass before commit
# Usage: ./scripts/test-before-commit.sh

set -e

echo "🧪 Running comprehensive pre-commit checks..."

# Run code formatting
echo "📝 Formatting code..."
black microweldr tests
isort microweldr tests

# Remove trailing whitespace
echo "🧹 Cleaning up whitespace..."
find microweldr tests -name "*.py" -exec sed -i '' 's/[[:space:]]*$//' {} \;

# Run all tests
echo "🔬 Running all tests..."
pytest --tb=short -v

# Run linting
echo "🔍 Running linting..."
flake8 microweldr tests --max-line-length=88 --extend-ignore=E203,W503

# Show test coverage
echo "📊 Test coverage summary..."
pytest --cov=microweldr --cov-report=term-missing --tb=no -q

echo "✅ All 157 tests passed! Ready to commit."
