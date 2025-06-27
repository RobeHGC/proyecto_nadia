#!/bin/bash
# Security Setup Script for NADIA Project

echo "🔒 Setting up security protections..."

# 1. Install pre-commit hook
if [ -f .git/hooks/pre-commit ]; then
    echo "⚠️  Pre-commit hook already exists. Backing up..."
    mv .git/hooks/pre-commit .git/hooks/pre-commit.backup
fi

cp .pre-commit-hook.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
echo "✅ Pre-commit hook installed"

# 2. Protect existing sensitive files
if [ -f bot_session.session ]; then
    git update-index --assume-unchanged bot_session.session
    echo "✅ Session file protected from git tracking"
fi

# 3. Create secure environment setup
if [ ! -f .env ]; then
    echo "📝 Creating .env from example..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit .env with your real credentials"
fi

if [ ! -f .env.testing ]; then
    echo "📝 Creating .env.testing from example..."
    cp .env.testing.example .env.testing
    echo "⚠️  IMPORTANT: Edit .env.testing with your test credentials"
fi

# 4. Set proper file permissions
chmod 600 .env .env.testing 2>/dev/null
echo "✅ Environment files secured with restrictive permissions"

# 5. Verify .gitignore
if ! grep -q "\.env$" .gitignore; then
    echo ".env" >> .gitignore
    echo "✅ Added .env to .gitignore"
fi

if ! grep -q "*.session" .gitignore; then
    echo "*.session" >> .gitignore
    echo "✅ Added *.session to .gitignore"
fi

echo ""
echo "🎉 Security setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your real credentials"
echo "2. Edit .env.testing with your test credentials"
echo "3. NEVER commit .env or .session files"
echo "4. Run 'git status' to verify no sensitive files are staged"
echo ""
echo "To test pre-commit hook:"
echo "  echo 'sk-test' > test.txt && git add test.txt && git commit -m 'test'"
echo "  (This should be blocked by the security hook)"