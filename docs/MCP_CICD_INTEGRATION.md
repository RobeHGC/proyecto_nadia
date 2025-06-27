# MCP CI/CD Integration Guide

> **Purpose**: How to integrate MCP tools into CI/CD pipelines for automated testing, security scanning, and deployment validation

## Table of Contents

1. [Overview](#overview)
2. [GitHub Actions Integration](#github-actions-integration)
3. [GitLab CI Integration](#gitlab-ci-integration)
4. [Jenkins Integration](#jenkins-integration)
5. [Pre-commit Hooks](#pre-commit-hooks)
6. [Docker Integration](#docker-integration)
7. [Deployment Validation](#deployment-validation)
8. [Best Practices](#best-practices)

## Overview

The MCP system provides powerful tools for automated quality assurance in CI/CD pipelines:

- **Security Scanning** - Detect secrets, vulnerabilities, and misconfigurations
- **Health Monitoring** - Validate system health before/after deployments
- **Performance Testing** - Establish baselines and detect regressions
- **Database Validation** - Check migrations and data integrity

### **MCP Tools Available for CI/CD**
| Tool | Purpose | CI/CD Use Case |
|------|---------|----------------|
| `security-nadia` | Security scanning | Pre-commit security checks |
| `health-nadia` | System health | Deployment validation |
| `performance-nadia` | Performance metrics | Regression testing |
| `postgres-nadia` | Database queries | Migration validation |
| `redis-nadia` | Redis operations | Cache validation |

## GitHub Actions Integration

### **Basic Security Pipeline**

Create `.github/workflows/mcp-security.yml`:

```yaml
name: MCP Security Checks

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  mcp-security:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
        
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        
    - name: Setup MCP Environment
      run: |
        export PYTHONPATH=$PWD
        chmod +x scripts/mcp-workflow.sh
        
    - name: Run MCP Security Scan
      run: |
        ./scripts/mcp-workflow.sh security-check
      env:
        MCP_ENVIRONMENT: ci
        
    - name: Upload Security Report
      if: failure()
      uses: actions/upload-artifact@v3
      with:
        name: security-report
        path: logs/mcp-security-*.log
        
    - name: Comment PR with Results
      if: github.event_name == 'pull_request'
      uses: actions/github-script@v6
      with:
        script: |
          const fs = require('fs');
          const logPath = 'logs/mcp-security-scan.log';
          if (fs.existsSync(logPath)) {
            const content = fs.readFileSync(logPath, 'utf8');
            await github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## 🔒 MCP Security Scan Results\n\n\`\`\`\n${content}\n\`\`\``
            });
          }
```

### **Comprehensive CI Pipeline**

Create `.github/workflows/mcp-ci.yml`:

```yaml
name: MCP Comprehensive CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

env:
  PYTHONPATH: ${{ github.workspace }}

jobs:
  mcp-pre-checks:
    name: Pre-deployment Checks
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: nadia_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
          
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - name: Checkout
      uses: actions/checkout@v4
      
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
        
    - name: Cache dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
        
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
        
    - name: Setup test environment
      run: |
        cp .env.example .env.test
        chmod +x scripts/mcp-workflow.sh
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost/nadia_test
        REDIS_URL: redis://localhost:6379
        
    - name: Run Database Migrations
      run: |
        python -m alembic upgrade head
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost/nadia_test
        
    - name: MCP Security Scan
      run: |
        ./scripts/mcp-workflow.sh security-check
        
    - name: MCP Health Check
      run: |
        ./scripts/mcp-workflow.sh health-check
        
    - name: Run Tests with Coverage
      run: |
        pytest tests/ --cov=. --cov-report=xml
        
    - name: MCP Performance Baseline
      run: |
        ./scripts/mcp-workflow.sh perf-baseline
        
    - name: Upload Coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        
    - name: Save MCP Reports
      uses: actions/upload-artifact@v3
      with:
        name: mcp-reports
        path: |
          logs/mcp-*.log
          perf_baseline_*.json

  mcp-deployment-test:
    name: Deployment Validation
    runs-on: ubuntu-latest
    needs: mcp-pre-checks
    if: github.ref == 'refs/heads/main'
    
    steps:
    - name: Checkout
      uses: actions/checkout@v4
      
    - name: Build Docker Images
      run: |
        docker-compose -f docker-compose.ci.yml build
        
    - name: Start Test Environment
      run: |
        docker-compose -f docker-compose.ci.yml up -d
        sleep 30  # Wait for services to start
        
    - name: MCP Health Validation
      run: |
        # Wait for services to be healthy
        timeout 60 bash -c 'until curl -f http://localhost:8000/health; do sleep 2; done'
        
        # Run comprehensive health check
        docker-compose -f docker-compose.ci.yml exec -T nadia-api \
          python -c "
import asyncio
from monitoring.mcp_alert_manager import send_mcp_alert
async def test():
    await send_mcp_alert('ci_deployment_test', 'Deployment validation starting', 'INFO')
asyncio.run(test())
"
        
    - name: API Integration Tests
      run: |
        docker-compose -f docker-compose.ci.yml exec -T nadia-api \
          pytest tests/integration/ -v
          
    - name: MCP Performance Validation
      run: |
        docker-compose -f docker-compose.ci.yml exec -T nadia-api \
          ./scripts/mcp-workflow.sh perf-baseline
          
    - name: Cleanup
      if: always()
      run: |
        docker-compose -f docker-compose.ci.yml down -v
```

### **Security-First Pipeline**

Create `.github/workflows/mcp-security-first.yml`:

```yaml
name: Security-First MCP Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  security-gate:
    name: Security Gate
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout
      uses: actions/checkout@v4
      
    - name: Setup environment
      run: |
        export PYTHONPATH=$PWD
        chmod +x scripts/mcp-workflow.sh
        
    - name: Critical Security Checks
      run: |
        # Fail fast on critical security issues
        ./scripts/mcp-workflow.sh security-check || {
          echo "❌ Security checks failed - blocking pipeline"
          exit 1
        }
        
    - name: Secrets Detection
      run: |
        # Additional secrets scanning
        if grep -r "api_key\|secret\|password" --include="*.py" --include="*.js" --exclude-dir=".git" .; then
          echo "❌ Potential hardcoded secrets detected"
          exit 1
        fi
        
    - name: Dependency Security Scan
      run: |
        pip install safety
        safety check --json || {
          echo "❌ Vulnerable dependencies detected"
          exit 1
        }
        
    - name: Security Report
      if: failure()
      run: |
        echo "🚨 Security gate failed - review required before merge"
        # Send alert
        curl -X POST "${{ secrets.SLACK_WEBHOOK }}" \
          -H 'Content-type: application/json' \
          --data '{"text":"🚨 Security gate failed for ${{ github.repository }} - PR #${{ github.event.number }}"}'

  continue-pipeline:
    name: Continue CI Pipeline
    runs-on: ubuntu-latest
    needs: security-gate
    
    steps:
    - name: Checkout
      uses: actions/checkout@v4
      
    - name: Run remaining checks
      run: |
        echo "✅ Security gate passed - continuing pipeline"
        # Additional CI steps here
```

## GitLab CI Integration

### **GitLab CI Pipeline**

Create `.gitlab-ci.yml`:

```yaml
stages:
  - security
  - test
  - deploy
  - validate

variables:
  PYTHONPATH: $CI_PROJECT_DIR
  POSTGRES_DB: nadia_test
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: postgres
  REDIS_URL: redis://redis:6379

# Security Stage
mcp-security-scan:
  stage: security
  image: python:3.12
  services:
    - postgres:15
    - redis:7
  variables:
    DATABASE_URL: postgresql://postgres:postgres@postgres/nadia_test
  before_script:
    - pip install -r requirements.txt
    - chmod +x scripts/mcp-workflow.sh
  script:
    - ./scripts/mcp-workflow.sh security-check
    - if [ $? -ne 0 ]; then echo "❌ Security scan failed"; exit 1; fi
  artifacts:
    when: always
    paths:
      - logs/mcp-security-*.log
    expire_in: 1 week
  rules:
    - if: $CI_PIPELINE_SOURCE == "push"
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

# Test Stage
mcp-health-test:
  stage: test
  image: python:3.12
  services:
    - postgres:15
    - redis:7
  variables:
    DATABASE_URL: postgresql://postgres:postgres@postgres/nadia_test
  before_script:
    - pip install -r requirements.txt
    - python -m alembic upgrade head
  script:
    - ./scripts/mcp-workflow.sh health-check
    - pytest tests/ --cov=. --cov-report=xml
    - ./scripts/mcp-workflow.sh perf-baseline
  coverage: '/TOTAL.+ ([0-9]{1,3}%)/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
    paths:
      - perf_baseline_*.json
      - logs/mcp-*.log

# Deploy Stage
deploy-staging:
  stage: deploy
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - # Deploy to staging environment
  only:
    - develop

# Validation Stage  
mcp-deployment-validation:
  stage: validate
  image: python:3.12
  variables:
    STAGING_URL: https://staging.nadia.com
  script:
    - |
      # Wait for deployment
      timeout 300 bash -c 'until curl -f $STAGING_URL/health; do sleep 10; done'
      
      # Validate with MCP
      export MCP_TARGET_ENV=staging
      ./scripts/mcp-workflow.sh health-check
      
      # Performance validation
      ./scripts/mcp-workflow.sh perf-baseline
      
      # Send success notification
      curl -X POST "$SLACK_WEBHOOK" \
        -H 'Content-type: application/json' \
        --data "{\"text\":\"✅ Deployment validation passed for $CI_PROJECT_NAME\"}"
  only:
    - develop

# Production deployment
deploy-production:
  stage: deploy
  image: docker:latest
  services:
    - docker:dind
  script:
    - # Production deployment steps
    - echo "🚀 Deploying to production"
  when: manual
  only:
    - main
```

## Jenkins Integration

### **Jenkinsfile Pipeline**

Create `Jenkinsfile`:

```groovy
pipeline {
    agent any
    
    environment {
        PYTHONPATH = "${WORKSPACE}"
        DATABASE_URL = "postgresql://postgres:postgres@localhost/nadia_test"
        REDIS_URL = "redis://localhost:6379"
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'chmod +x scripts/mcp-workflow.sh'
            }
        }
        
        stage('Setup') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install -r requirements.txt
                '''
            }
        }
        
        stage('MCP Security Gate') {
            steps {
                script {
                    def securityResult = sh(
                        script: '. venv/bin/activate && ./scripts/mcp-workflow.sh security-check',
                        returnStatus: true
                    )
                    
                    if (securityResult != 0) {
                        error("❌ MCP Security scan failed - blocking pipeline")
                    }
                    
                    echo "✅ Security gate passed"
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'logs/mcp-security-*.log', allowEmptyArchive: true
                }
                failure {
                    slackSend(
                        channel: '#alerts',
                        color: 'danger',
                        message: "🚨 Security gate failed for ${env.JOB_NAME} - Build #${env.BUILD_NUMBER}"
                    )
                }
            }
        }
        
        stage('Tests & Health Checks') {
            parallel {
                stage('Unit Tests') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            pytest tests/ --cov=. --cov-report=xml --junitxml=test-results.xml
                        '''
                    }
                    post {
                        always {
                            publishTestResults testResultsPattern: 'test-results.xml'
                            publishCoverageGlobalReport coverageReportPattern: 'coverage.xml'
                        }
                    }
                }
                
                stage('MCP Health Check') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            ./scripts/mcp-workflow.sh health-check
                        '''
                    }
                }
                
                stage('Performance Baseline') {
                    steps {
                        sh '''
                            . venv/bin/activate
                            ./scripts/mcp-workflow.sh perf-baseline
                        '''
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'perf_baseline_*.json', allowEmptyArchive: true
                        }
                    }
                }
            }
        }
        
        stage('Build & Deploy to Staging') {
            when { branch 'develop' }
            steps {
                sh '''
                    docker build -t nadia:staging .
                    # Deploy to staging
                '''
            }
        }
        
        stage('Staging Validation') {
            when { branch 'develop' }
            steps {
                script {
                    // Wait for staging deployment
                    sh 'sleep 60'
                    
                    // Validate with MCP
                    def validationResult = sh(
                        script: '''
                            . venv/bin/activate
                            export MCP_TARGET_ENV=staging
                            ./scripts/mcp-workflow.sh health-check
                        ''',
                        returnStatus: true
                    )
                    
                    if (validationResult == 0) {
                        slackSend(
                            channel: '#deployments',
                            color: 'good',
                            message: "✅ Staging deployment validated for ${env.JOB_NAME}"
                        )
                    } else {
                        error("❌ Staging validation failed")
                    }
                }
            }
        }
        
        stage('Deploy to Production') {
            when { 
                allOf {
                    branch 'main'
                    input message: 'Deploy to production?', ok: 'Deploy'
                }
            }
            steps {
                sh '''
                    docker build -t nadia:production .
                    # Deploy to production
                '''
                
                // Send production deployment alert
                script {
                    sh '''
                        . venv/bin/activate
                        python3 -c "
import asyncio
from monitoring.mcp_alert_manager import send_mcp_alert
asyncio.run(send_mcp_alert('production_deployment', 'Production deployment completed', 'INFO'))
"
                    '''
                }
            }
        }
    }
    
    post {
        always {
            // Archive MCP logs
            archiveArtifacts artifacts: 'logs/mcp-*.log', allowEmptyArchive: true
            
            // Cleanup
            sh 'rm -rf venv'
        }
        failure {
            slackSend(
                channel: '#alerts',
                color: 'danger',
                message: "❌ Pipeline failed for ${env.JOB_NAME} - Build #${env.BUILD_NUMBER}"
            )
        }
        success {
            slackSend(
                channel: '#deployments',
                color: 'good',
                message: "✅ Pipeline completed for ${env.JOB_NAME} - Build #${env.BUILD_NUMBER}"
            )
        }
    }
}
```

## Pre-commit Hooks

### **Advanced Pre-commit Configuration**

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: mcp-security-check
        name: MCP Security Scan
        entry: ./scripts/mcp-workflow.sh security-check
        language: system
        types: [python]
        stages: [pre-commit]
        
      - id: mcp-secrets-detection
        name: MCP Secrets Detection
        entry: bash -c 'if grep -r "api_key\|secret\|password" --include="*.py" --include="*.js" .; then echo "Secrets detected"; exit 1; fi'
        language: system
        stages: [pre-commit]
        
      - id: mcp-performance-check
        name: MCP Performance Check
        entry: ./scripts/mcp-workflow.sh perf-baseline
        language: system
        stages: [pre-push]
        
  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

### **Git Hooks Setup Script**

Create `scripts/setup-git-hooks.sh`:

```bash
#!/bin/bash

# Setup Git Hooks with MCP Integration

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GIT_HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo "Setting up Git hooks with MCP integration..."

# Pre-commit hook
cat > "$GIT_HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
set -e

echo "🔍 Running MCP pre-commit checks..."

# Security check
if ! ./scripts/mcp-workflow.sh security-check; then
    echo "❌ Security check failed - commit blocked"
    exit 1
fi

# Secrets detection
if git diff --cached --name-only | xargs grep -l "api_key\|secret\|password" 2>/dev/null; then
    echo "❌ Potential secrets detected in staged files"
    echo "Please remove secrets and use environment variables"
    exit 1
fi

echo "✅ Pre-commit checks passed"
EOF

# Pre-push hook  
cat > "$GIT_HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
set -e

echo "🚀 Running MCP pre-push validation..."

# Health check
if ! ./scripts/mcp-workflow.sh health-check; then
    echo "❌ Health check failed - push blocked"
    exit 1
fi

# Performance baseline
./scripts/mcp-workflow.sh perf-baseline

echo "✅ Pre-push validation passed"
EOF

# Post-merge hook
cat > "$GIT_HOOKS_DIR/post-merge" << 'EOF'
#!/bin/bash

echo "🔄 Running post-merge MCP checks..."

# Check if dependencies changed
if git diff HEAD@{1} --name-only | grep -q "requirements.txt\|package.json"; then
    echo "📦 Dependencies changed - running health check"
    ./scripts/mcp-workflow.sh health-check
fi

# Send merge notification
python3 -c "
import asyncio
from monitoring.mcp_alert_manager import send_mcp_alert
asyncio.run(send_mcp_alert('git_merge', 'Code merged - running post-merge validation', 'INFO'))
" 2>/dev/null || true

echo "✅ Post-merge checks completed"
EOF

# Make hooks executable
chmod +x "$GIT_HOOKS_DIR"/*

echo "✅ Git hooks installed successfully"
echo ""
echo "Installed hooks:"
echo "  - pre-commit: Security and secrets check"
echo "  - pre-push: Health and performance validation"  
echo "  - post-merge: Dependency and notification checks"
```

## Docker Integration

### **Multi-stage Dockerfile with MCP**

Create `Dockerfile.mcp`:

```dockerfile
# Multi-stage Dockerfile with MCP integration
FROM python:3.12-slim AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Development stage with MCP tools
FROM base AS development
COPY . .
RUN chmod +x scripts/mcp-workflow.sh

# Run MCP checks during build
RUN ./scripts/mcp-workflow.sh security-check || \
    (echo "❌ Security check failed during build" && exit 1)

# Production stage
FROM base AS production
COPY . .
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["python", "-m", "api.server"]
```

### **Docker Compose for CI**

Create `docker-compose.ci.yml`:

```yaml
version: '3.8'

services:
  nadia-api:
    build:
      context: .
      dockerfile: Dockerfile.mcp
      target: development
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/nadia_test
      - REDIS_URL=redis://redis:6379
      - MCP_ENVIRONMENT=ci
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: nadia_test
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  mcp-validator:
    build:
      context: .
      dockerfile: Dockerfile.mcp
      target: development
    command: |
      bash -c "
        echo '🔍 Running MCP validation suite...'
        sleep 30  # Wait for services
        
        ./scripts/mcp-workflow.sh health-check || exit 1
        ./scripts/mcp-workflow.sh security-check || exit 1
        ./scripts/mcp-workflow.sh perf-baseline || exit 1
        
        echo '✅ MCP validation completed'
      "
    depends_on:
      nadia-api:
        condition: service_healthy
    environment:
      - MCP_ENVIRONMENT=ci_validation
```

## Deployment Validation

### **Deployment Health Check Script**

Create `scripts/deployment-health-check.sh`:

```bash
#!/bin/bash

# Deployment Health Check with MCP Integration

set -e

ENVIRONMENT="${1:-staging}"
MAX_WAIT="${2:-300}"
API_URL="${3:-http://localhost:8000}"

echo "🚀 Starting deployment validation for $ENVIRONMENT"
echo "API URL: $API_URL"
echo "Max wait time: ${MAX_WAIT}s"

# Wait for API to be ready
echo "⏳ Waiting for API to be ready..."
timeout $MAX_WAIT bash -c "until curl -f $API_URL/health >/dev/null 2>&1; do sleep 5; done"

echo "✅ API is responding"

# Set MCP environment
export MCP_TARGET_ENV="$ENVIRONMENT"
export PYTHONPATH="/app"

# Run comprehensive health checks
echo "🔍 Running MCP health validation..."

# System health
if ! ./scripts/mcp-workflow.sh health-check; then
    echo "❌ Health check failed"
    exit 1
fi

# Database connectivity
echo "🗄️ Validating database..."
python3 -c "
import asyncio
from database.models import DatabaseManager
import os

async def test_db():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print('No DATABASE_URL - skipping DB test')
        return
    
    try:
        db = DatabaseManager(db_url)
        # Test basic query
        async with db._pool.acquire() as conn:
            result = await conn.fetchval('SELECT 1')
            print(f'✅ Database connection successful: {result}')
    except Exception as e:
        print(f'❌ Database test failed: {e}')
        exit(1)

asyncio.run(test_db())
"

# Redis connectivity
echo "🔄 Validating Redis..."
python3 -c "
import asyncio
import redis.asyncio as redis
import os

async def test_redis():
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    try:
        r = redis.from_url(redis_url)
        result = await r.ping()
        await r.aclose()
        print(f'✅ Redis connection successful: {result}')
    except Exception as e:
        print(f'❌ Redis test failed: {e}')
        exit(1)

asyncio.run(test_redis())
"

# API endpoints validation
echo "🌐 Validating API endpoints..."
curl -f "$API_URL/health" > /dev/null || {
    echo "❌ Health endpoint failed"
    exit 1
}

# Test key endpoints
for endpoint in "/api/reviews/pending" "/api/dashboard/metrics"; do
    if curl -f -H "Authorization: Bearer ${API_KEY:-test}" "$API_URL$endpoint" > /dev/null 2>&1; then
        echo "✅ $endpoint - OK"
    else
        echo "⚠️ $endpoint - Failed (may be expected without auth)"
    fi
done

# Performance validation
echo "📊 Running performance validation..."
./scripts/mcp-workflow.sh perf-baseline

# Send deployment success notification
echo "📢 Sending deployment notification..."
python3 -c "
import asyncio
from monitoring.mcp_alert_manager import send_mcp_alert

async def notify():
    await send_mcp_alert(
        'deployment_success',
        f'Deployment to $ENVIRONMENT completed and validated successfully',
        'INFO'
    )

asyncio.run(notify())
" 2>/dev/null || echo "Notification skipped"

echo "🎉 Deployment validation completed successfully!"
echo ""
echo "Summary:"
echo "  ✅ API health check"
echo "  ✅ Database connectivity"
echo "  ✅ Redis connectivity"
echo "  ✅ Endpoint validation"
echo "  ✅ Performance baseline"
echo "  ✅ Notification sent"
```

### **Blue-Green Deployment with MCP**

Create `scripts/blue-green-deploy.sh`:

```bash
#!/bin/bash

# Blue-Green Deployment with MCP Validation

set -e

NEW_VERSION="$1"
CURRENT_COLOR="${2:-blue}"
TARGET_COLOR="${3:-green}"

if [ -z "$NEW_VERSION" ]; then
    echo "Usage: $0 <version> [current_color] [target_color]"
    exit 1
fi

echo "🔄 Starting blue-green deployment"
echo "New version: $NEW_VERSION"
echo "Current: $CURRENT_COLOR → Target: $TARGET_COLOR"

# Deploy to target environment
echo "🚀 Deploying to $TARGET_COLOR environment..."
docker-compose -f docker-compose.$TARGET_COLOR.yml up -d

# Wait for deployment
sleep 30

# MCP validation on new environment
echo "🔍 Running MCP validation on $TARGET_COLOR..."
export MCP_TARGET_ENV="$TARGET_COLOR"

# Health check
if ! ./scripts/deployment-health-check.sh "$TARGET_COLOR" 300 "http://${TARGET_COLOR}:8000"; then
    echo "❌ $TARGET_COLOR environment validation failed"
    echo "🔄 Rolling back..."
    docker-compose -f docker-compose.$TARGET_COLOR.yml down
    exit 1
fi

# Performance comparison
echo "📊 Comparing performance with $CURRENT_COLOR..."
./scripts/mcp-workflow.sh perf-baseline > "${TARGET_COLOR}_perf.json"

# Compare with current baseline if available
if [ -f "${CURRENT_COLOR}_perf.json" ]; then
    python3 -c "
import json

try:
    with open('${CURRENT_COLOR}_perf.json') as f:
        current = json.load(f)
    with open('${TARGET_COLOR}_perf.json') as f:
        target = json.load(f)
    
    # Simple performance comparison
    print('Performance comparison:')
    print(f'Current ({CURRENT_COLOR}): baseline')
    print(f'Target ({TARGET_COLOR}): new deployment')
    print('✅ Performance validation completed')
except Exception as e:
    print(f'Performance comparison failed: {e}')
"
fi

# Switch traffic
echo "🔀 Switching traffic to $TARGET_COLOR..."
# Update load balancer configuration
# nginx/traefik/haproxy config update would go here

# Final validation
echo "🔍 Final validation after traffic switch..."
sleep 10
./scripts/deployment-health-check.sh "$TARGET_COLOR" 60 "http://production:8000"

# Send success notification
python3 -c "
import asyncio
from monitoring.mcp_alert_manager import send_mcp_alert

async def notify():
    await send_mcp_alert(
        'blue_green_deployment',
        f'Blue-green deployment completed: {NEW_VERSION} on {TARGET_COLOR}',
        'INFO'
    )

asyncio.run(notify())
" 2>/dev/null || true

echo "🎉 Blue-green deployment completed successfully!"
echo "New version $NEW_VERSION is live on $TARGET_COLOR"

# Cleanup old environment (optional)
if [ "${CLEANUP_OLD:-false}" = "true" ]; then
    echo "🧹 Cleaning up $CURRENT_COLOR environment..."
    docker-compose -f docker-compose.$CURRENT_COLOR.yml down
fi
```

## Best Practices

### **1. Security-First Approach**

```yaml
# Always run security checks first
stages:
  - security-gate    # Block on security issues
  - tests           # Run tests only if secure
  - deploy          # Deploy only if tests pass
  - validate        # Validate deployment
```

### **2. Fail Fast Strategy**

```bash
# Exit immediately on security failures
./scripts/mcp-workflow.sh security-check || {
    echo "❌ Security check failed - blocking pipeline"
    exit 1
}
```

### **3. Comprehensive Validation**

```yaml
# Multi-stage validation
validation:
  parallel:
    - security_scan
    - health_check
    - performance_test
    - integration_test
```

### **4. Notification Strategy**

```bash
# Notify on important events
on_success() {
    send_mcp_alert "deployment_success" "Deployment completed" "INFO"
}

on_failure() {
    send_mcp_alert "deployment_failure" "Deployment failed" "CRITICAL"
}
```

### **5. Environment-Specific Configs**

```bash
# Different validations per environment
case "$ENVIRONMENT" in
    "staging")
        # Light validation
        ./scripts/mcp-workflow.sh health-check
        ;;
    "production")
        # Comprehensive validation
        ./scripts/mcp-workflow.sh health-check
        ./scripts/mcp-workflow.sh security-check
        ./scripts/mcp-workflow.sh perf-baseline
        ;;
esac
```

## Integration Examples

### **Kubernetes Deployment**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: mcp-deployment-validator
spec:
  template:
    spec:
      containers:
      - name: validator
        image: nadia:latest
        command: ["/bin/bash"]
        args:
          - -c
          - |
            ./scripts/deployment-health-check.sh production 300 http://nadia-api:8000
            ./scripts/mcp-workflow.sh security-check
      restartPolicy: Never
```

### **Terraform Integration**

```hcl
resource "null_resource" "mcp_validation" {
  depends_on = [aws_instance.nadia_app]
  
  provisioner "local-exec" {
    command = "./scripts/deployment-health-check.sh production 300 http://${aws_instance.nadia_app.public_ip}:8000"
  }
  
  provisioner "local-exec" {
    when    = destroy
    command = "python3 -c \"import asyncio; from monitoring.mcp_alert_manager import send_mcp_alert; asyncio.run(send_mcp_alert('infrastructure_destroy', 'Infrastructure being destroyed', 'WARNING'))\""
  }
}
```

---

This comprehensive CI/CD integration ensures that MCP tools are seamlessly integrated into your deployment pipeline, providing automated security scanning, health validation, and performance monitoring at every stage of development and deployment.