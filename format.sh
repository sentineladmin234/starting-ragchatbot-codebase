#!/bin/bash

# Quick code formatting script for the RAG chatbot project
# This script applies Black formatting to all Python files

set -e

echo "🧹 Formatting Python code with Black..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found. Run this script from the project root."
    exit 1
fi

uv run black .

echo "✅ Code formatting complete!"