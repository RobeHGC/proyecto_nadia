#!/bin/bash
# Pre-commit hook to prevent credential leaks

echo "🔒 Running security checks..."

# Check for common credential patterns
if git diff --cached --name-only | xargs grep -l "sk-" 2>/dev/null; then
    echo "❌ BLOCKED: OpenAI/Anthropic API key detected in staged files!"
    echo "   Remove API keys from code before committing."
    exit 1
fi

if git diff --cached --name-only | xargs grep -l "AIza" 2>/dev/null; then
    echo "❌ BLOCKED: Google/Gemini API key detected in staged files!"
    echo "   Remove API keys from code before committing."
    exit 1
fi

# Check for .env files
if git diff --cached --name-only | grep -E "\\.env$|\\.env\\." | grep -v "example"; then
    echo "❌ BLOCKED: Environment file with credentials detected!"
    echo "   Only commit .env.example files, not .env files with real credentials."
    exit 1
fi

# Check for session files
if git diff --cached --name-only | grep -E "\\.session$"; then
    echo "❌ BLOCKED: Telegram session file detected!"
    echo "   Session files contain authentication data and should not be committed."
    exit 1
fi

# Check for hardcoded phone numbers
if git diff --cached --name-only | xargs grep -l "+52864" 2>/dev/null; then
    echo "⚠️  WARNING: Phone number detected in staged files!"
    echo "   Consider using environment variables for phone numbers."
fi

echo "✅ Security checks passed!"
exit 0