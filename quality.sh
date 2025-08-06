#!/bin/bash

# Development quality check script for the RAG chatbot project
# This script runs all code quality checks including formatting and validation

set -e

echo "🧹 Running code quality checks..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found. Run this script from the project root."
    exit 1
fi

echo "📝 Formatting Python code with Black..."
uv run black .

echo "✅ Code formatting complete!"

echo "🔍 Checking code formatting compliance..."
uv run black --check .

echo "✅ All quality checks passed!"
echo "🎉 Your code is ready for production!"