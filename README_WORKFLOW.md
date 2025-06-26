# NADIA Development Workflow

## Plan de Implementación Completo

### Fase 1: Lo Esencial ✅ (COMPLETADA - 12 minutos)
**Objetivo**: Tener el ciclo básico de desarrollo funcionando

#### Implementado:
- ✅ **GitHub Issue Templates**: `bug_report.md` y `feature_request.md`
- ✅ **Testing Infrastructure**: pytest con PYTHONPATH configurado
- ✅ **GitHub Actions CI**: Workflow básico que ejecuta tests en PRs
- ✅ **Documentación**: Comandos esenciales en `CLAUDE.md`

#### Comandos Disponibles:
```bash
# Testing
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest -v

# GitHub Issues
gh issue create --template bug_report
gh issue create --template feature_request

# Workflow Issue
.claude/commands/issue.md [ISSUE_NUMBER]
```

---

### Fase 2: Testing Avanzado (PRÓXIMO)
**Objetivo**: Cobertura completa de testing con herramientas especializadas

#### Por Implementar:
- **Unit Tests**: Expandir suite actual (16 tests existentes necesitan arreglos de import)
- **Integration Tests**: API + Database + Redis interactions
- **E2E Tests**: Dashboard workflows usando Puppeteer MCP
- **Performance Tests**: Response times, memory usage, LLM costs
- **Security Tests**: API key detection, SQL injection prevention

#### Estructura Propuesta:
```
tests/
├── unit/           # Tests rápidos, aislados
├── integration/    # Tests de componentes trabajando juntos  
├── e2e/           # Tests end-to-end con Puppeteer MCP
├── performance/   # Benchmarks y stress tests
└── security/      # Vulnerability scanning
```

---

### Fase 3: CI/CD Robusto (FUTURO)
**Objetivo**: Pipeline completo de calidad y deployment

#### Componentes:
- **Pre-commit Hooks**: 
  - Code formatting (black, prettier)
  - Security scanning (detect API keys)
  - Fast test subset
- **GitHub Actions**: 
  - Matrix testing (Python 3.10, 3.11, 3.12)
  - Dependency vulnerability scanning
  - Performance regression detection
  - Automatic deployment to staging
- **Quality Gates**:
  - Test coverage > 80%
  - No high-severity security issues
  - Performance benchmarks within limits

---

### Fase 4: Observabilidad & Monitoreo (FUTURO)
**Objetivo**: Visibility completa del sistema en producción

#### Componentes:
- **Structured Logging**: JSON logs con trace IDs
- **Metrics Collection**: Prometheus + Grafana
- **Error Tracking**: Sentry integration
- **Performance Monitoring**: LLM cost tracking, response times
- **Health Checks**: Automated system status monitoring

---

## Workflow de Desarrollo

### 1. **Planificación**
```bash
# Crear issue desde template
gh issue create --template feature_request

# Analizar requirements
.claude/commands/issue.md [ISSUE_NUMBER]
```

### 2. **Desarrollo**
```bash
# Branch por issue
git checkout -b feature/issue-123-description

# Commits granulares
git add -A && git commit -m "step: add user authentication"
```

### 3. **Testing**
```bash
# Tests locales
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest -v

# Tests específicos
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/test_coherence_integration.py
```

### 4. **Review & Deploy**
```bash
# Draft PR
gh pr create --draft --title "Feature: User Authentication"

# CI automático ejecuta tests
# Manual review usando dual-terminal Claude Code
# Merge cuando esté aprobado
```

---

## Estado Actual del Proyecto

### ✅ Sistemas Implementados:
- **Memory System**: Redis 50 msg/user + temporal summaries
- **PROTOCOLO DE SILENCIO**: Quarantine system 
- **COMPREHENSIVE RECOVERY**: Zero message loss system
- **COHERENCE SYSTEM**: Temporal conflict detection (100% integrated)
- **Dashboard**: Review, Analytics, Quarantine, Recovery, Coherence tabs
- **Testing**: Basic pytest infrastructure

### 🔄 En Desarrollo:
- **Development Workflow**: Este documento y sistema de issues

### 📋 Próximas Prioridades:
1. **Fix Unit Tests**: Resolver imports en 16 tests existentes
2. **E2E Testing**: Implementar Puppeteer MCP para dashboard
3. **Performance Benchmarks**: Baseline metrics para coherence system
4. **Security Hardening**: Pre-commit hooks para API keys

---

## Arquitectura de Testing

### Current Testing Strategy:
```
Level 1: Unit Tests (Fast - <1s each)
├── agents/supervisor_agent.py tests
├── utils/protocol_manager.py tests  
└── memory/user_memory.py tests

Level 2: Integration Tests (Medium - <10s each)
├── API + Database interactions
├── Redis + LLM pipeline tests
└── Recovery system end-to-end

Level 3: E2E Tests (Slow - <60s each)
├── Dashboard user workflows (Puppeteer MCP)
├── Telegram bot message flows
└── Complete coherence pipeline validation
```

### Testing Commands:
```bash
# Fast feedback loop
pytest tests/unit/ -v

# Full integration 
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/ -v

# Specific component
pytest tests/test_coherence_integration.py::test_coherence_integration -v
```

---

## MCP Debugging Integration

### Available MCP Servers:
- **postgres-nadia**: Direct database queries (`@postgres_interactions`)
- **filesystem-nadia**: Code analysis (`@agents/recovery_agent.py`)
- **git-nadia**: Repository history (`/mcp__git__log`)

### Enhanced Debugging Workflow:
```
Traditional: Issue → Copy/paste logs → 9 steps → 3 minutes
MCP-enhanced: Issue → @direct_access → 1 step → 10 seconds
```

---

**Última Actualización**: Diciembre 26, 2025
**Estado**: Fase 1 Completada ✅ | Fase 2 En Planificación 🔄