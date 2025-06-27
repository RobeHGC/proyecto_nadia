#!/bin/bash
# Run the same checks as CI pipeline locally

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Running CI checks locally...${NC}"
echo "=============================="

# Check if running in project root
if [ ! -f "pytest.ini" ]; then
    echo -e "${RED}Error: Must run from project root directory${NC}"
    exit 1
fi

# 1. Lint checks
echo -e "\n${YELLOW}1. Running ruff linter...${NC}"
if command -v ruff &> /dev/null; then
    ruff check . --output-format=grouped
else
    echo -e "${RED}ruff not installed. Install with: pip install ruff${NC}"
    exit 1
fi

# 2. Format checks
echo -e "\n${YELLOW}2. Checking code formatting...${NC}"
ruff format --check .

# 3. Import sorting
echo -e "\n${YELLOW}3. Checking import sorting...${NC}"
if command -v isort &> /dev/null; then
    isort --check-only --diff .
else
    echo -e "${RED}isort not installed. Install with: pip install isort${NC}"
    exit 1
fi

# 4. Type checking (optional)
if command -v mypy &> /dev/null; then
    echo -e "\n${YELLOW}4. Running type checker...${NC}"
    mypy . --ignore-missing-imports || true
else
    echo -e "\n${YELLOW}4. Skipping type checking (mypy not installed)${NC}"
fi

# 5. Security scan for secrets
echo -e "\n${YELLOW}5. Scanning for secrets...${NC}"
# Basic pattern matching for common secret patterns
if grep -r -E "(sk-[a-zA-Z0-9]{48}|AIza[a-zA-Z0-9]{35}|api_key.*=.*['\"][a-zA-Z0-9]{20,}['\"])" \
    --include="*.py" \
    --include="*.js" \
    --include="*.env*" \
    --exclude-dir=".git" \
    --exclude-dir="venv" \
    --exclude-dir="__pycache__" .; then
    echo -e "${RED}Potential secrets found! Please review the matches above.${NC}"
    exit 1
else
    echo -e "${GREEN}No obvious secrets detected${NC}"
fi

# 6. Run tests
echo -e "\n${YELLOW}6. Running test suite...${NC}"
if [ -z "$SKIP_TESTS" ]; then
    export PYTHONPATH="${PWD}"
    
    # Check if test dependencies are available
    if ! python -c "import pytest" 2>/dev/null; then
        echo -e "${RED}pytest not installed. Install with: pip install pytest pytest-asyncio pytest-cov${NC}"
        exit 1
    fi
    
    # Run tests with coverage
    pytest tests/ -v --tb=short --cov=. --cov-report=term-missing --cov-fail-under=80
else
    echo -e "${YELLOW}Tests skipped (SKIP_TESTS is set)${NC}"
fi

# 7. Check for common issues
echo -e "\n${YELLOW}7. Checking for common issues...${NC}"

# Check for print statements in production code
if grep -r "print(" --include="*.py" --exclude-dir="tests" --exclude-dir="scripts" . | grep -v "# noqa"; then
    echo -e "${YELLOW}Warning: print() statements found in production code${NC}"
fi

# Check for TODO comments
TODO_COUNT=$(grep -r "TODO" --include="*.py" . | wc -l)
if [ $TODO_COUNT -gt 0 ]; then
    echo -e "${YELLOW}Found $TODO_COUNT TODO comments${NC}"
fi

# Check for large files
echo -e "\n${YELLOW}Checking for large files...${NC}"
find . -type f -size +1M -not -path "./.git/*" -not -path "./venv/*" -exec ls -lh {} \; | awk '{print $5 " " $9}'

echo -e "\n${GREEN}✅ All CI checks completed!${NC}"
echo -e "${GREEN}=============================${NC}"

# Summary
echo -e "\n${GREEN}Summary:${NC}"
echo "- Linting: ✅"
echo "- Formatting: ✅" 
echo "- Import sorting: ✅"
echo "- Security scan: ✅"
if [ -z "$SKIP_TESTS" ]; then
    echo "- Tests: ✅"
else
    echo "- Tests: ⏭️  (skipped)"
fi

echo -e "\n${GREEN}Your code is ready for CI/CD pipeline!${NC}"