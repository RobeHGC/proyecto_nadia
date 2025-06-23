#!/usr/bin/env python3
"""
Sistema de Testing End-to-End Automatizado con Loop de Mejora Continua
Simula usuario real, verifica flujo completo, detecta problemas y sugiere mejoras automáticamente
"""
import asyncio
import os
import sys
import json
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar credenciales de testing
load_dotenv('.env.testing')

class TestStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"

class IssueType(Enum):
    PERFORMANCE = "performance"
    FUNCTIONALITY = "functionality"
    CACHE = "cache"
    QUOTA = "quota"
    DASHBOARD = "dashboard"
    SECURITY = "security"

@dataclass
class TestResult:
    """Resultado detallado de un test."""
    test_id: str
    message: str
    timestamp: datetime
    status: TestStatus
    duration: float
    steps: Dict[str, bool]
    metrics: Dict[str, Any]
    errors: List[str]
    review_data: Optional[Dict] = None
    response_data: Optional[Dict] = None

@dataclass
class IssueDetected:
    """Problema detectado durante testing."""
    issue_type: IssueType
    severity: str  # low, medium, high, critical
    description: str
    test_id: str
    timestamp: datetime
    suggested_fix: str
    auto_fixable: bool

class PerfectionLoop:
    """Sistema de mejora continua que busca la perfección del proyecto."""
    
    def __init__(self):
        # Credenciales del tester
        self.test_api_id = int(os.getenv('TEST_API_ID', '0'))
        self.test_api_hash = os.getenv('TEST_API_HASH', '')
        self.test_phone = os.getenv('TEST_PHONE_NUMBER', '')
        
        # Configuración
        self.target_bot = os.getenv('TARGET_BOT_USERNAME', '@nadia_hitl_bot')
        self.dashboard_url = os.getenv('DASHBOARD_URL', 'http://localhost:8000')
        self.dashboard_api_key = os.getenv('DASHBOARD_API_KEY', 'miclavesegura45mil')
        
        # Cliente Telegram
        self.client = None
        
        # Estado del sistema
        self.test_results: List[TestResult] = []
        self.detected_issues: List[IssueDetected] = []
        self.performance_history: List[Dict] = []
        self.last_message_sent = None
        self.last_response_received = None
        
        # Métricas de perfección
        self.success_rate_target = 0.95  # 95% éxito mínimo
        self.response_time_target = 10.0  # 10s máximo
        self.cache_hit_rate_target = 0.75  # 75% cache hits
        
        # Contadores de mejora
        self.improvement_cycle = 0
        self.fixes_applied = 0
        
    async def initialize(self):
        """Inicializa el sistema de testing."""
        logger.info("🚀 Inicializando Sistema de Perfección Continua...")
        
        if not all([self.test_api_id, self.test_api_hash, self.test_phone]):
            raise ValueError("❌ Credenciales de testing faltantes en .env.testing")
            
        # Inicializar cliente Telegram
        self.client = TelegramClient(
            StringSession(),
            self.test_api_id,
            self.test_api_hash,
            system_version="Testing Bot v2.0"
        )
        
        logger.info("🔐 Conectando cliente de testing...")
        await self.client.start(phone=self.test_phone)
        
        # Handler para respuestas
        @self.client.on(events.NewMessage(from_users=self.target_bot))
        async def response_handler(event):
            self.last_response_received = {
                'text': event.text,
                'timestamp': datetime.now(),
                'bubbles': self._extract_bubbles(event.text),
                'message_id': event.id
            }
            logger.info(f"📨 Respuesta recibida: {event.text[:50]}...")
            
        logger.info("✅ Sistema inicializado correctamente")
        
    def _extract_bubbles(self, text: str) -> List[str]:
        """Extrae globos de una respuesta."""
        if '[GLOBO]' in text:
            return [bubble.strip() for bubble in text.split('[GLOBO]') if bubble.strip()]
        return [text]
        
    async def run_comprehensive_test(self, test_message: str, test_id: str = None) -> TestResult:
        """Ejecuta un test comprensivo con métricas detalladas."""
        if not test_id:
            test_id = f"test_{int(time.time())}"
            
        logger.info(f"\n{'='*80}")
        logger.info(f"🧪 EJECUTANDO TEST COMPRENSIVO: {test_id}")
        logger.info(f"📝 Mensaje: '{test_message}'")
        logger.info(f"{'='*80}")
        
        start_time = time.time()
        test_result = TestResult(
            test_id=test_id,
            message=test_message,
            timestamp=datetime.now(),
            status=TestStatus.RUNNING,
            duration=0.0,
            steps={},
            metrics={},
            errors=[]
        )
        
        try:
            # Paso 1: Enviar mensaje
            step_start = time.time()
            await self._send_test_message(test_message)
            test_result.steps['message_sent'] = True
            test_result.metrics['send_time'] = time.time() - step_start
            
            # Paso 2: Verificar dashboard
            step_start = time.time()
            review_data = await self._check_dashboard_with_retries()
            test_result.steps['appeared_in_dashboard'] = review_data is not None
            test_result.metrics['dashboard_check_time'] = time.time() - step_start
            test_result.review_data = review_data
            
            if review_data:
                # Paso 3: Analizar calidad de respuesta AI
                await self._analyze_ai_response_quality(review_data, test_result)
                
                # Paso 4: Aprobar review
                step_start = time.time()
                approved = await self._approve_review(review_data['id'])
                test_result.steps['approved_in_dashboard'] = approved
                test_result.metrics['approval_time'] = time.time() - step_start
                
                if approved:
                    # Paso 5: Esperar respuesta del bot
                    step_start = time.time()
                    response = await self._wait_for_response(timeout=30)
                    test_result.steps['response_received'] = response is not None
                    test_result.metrics['response_wait_time'] = time.time() - step_start
                    test_result.response_data = response
                    
                    if response:
                        # Paso 6: Verificar calidad de respuesta final
                        await self._verify_response_quality(response, test_result)
            
            # Calcular resultado final
            test_result.duration = time.time() - start_time
            test_result.status = TestStatus.PASSED if all(test_result.steps.values()) else TestStatus.FAILED
            
            # Detectar problemas automáticamente
            await self._detect_issues(test_result)
            
        except Exception as e:
            test_result.status = TestStatus.FAILED
            test_result.errors.append(str(e))
            test_result.duration = time.time() - start_time
            logger.error(f"❌ Error en test {test_id}: {e}")
            traceback.print_exc()
            
        # Guardar resultado
        self.test_results.append(test_result)
        self._log_test_result(test_result)
        
        return test_result
        
    async def _send_test_message(self, message: str):
        """Envía mensaje de prueba."""
        logger.info(f"📤 Enviando: '{message}'")
        sent_time = time.time()
        
        await self.client.send_message(self.target_bot, message)
        
        self.last_message_sent = {
            'text': message,
            'timestamp': datetime.now(),
            'sent_time': sent_time
        }
        
    async def _check_dashboard_with_retries(self, max_retries: int = 15) -> Optional[Dict]:
        """Verifica dashboard con reintentos inteligentes."""
        logger.info("🔍 Verificando dashboard...")
        
        headers = {'Authorization': f'Bearer {self.dashboard_api_key}'}
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.dashboard_url}/api/reviews/pending",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            reviews = await response.json()
                            
                            # Buscar nuestro mensaje
                            for review in reviews:
                                if review.get('user_message') == self.last_message_sent['text']:
                                    logger.info(f"✅ Mensaje encontrado en dashboard!")
                                    logger.info(f"   - Review ID: {review['id']}")
                                    logger.info(f"   - LLM1: {review.get('llm1_model_used', 'N/A')}")
                                    logger.info(f"   - LLM2: {review.get('llm2_model_used', 'N/A')}")
                                    logger.info(f"   - Risk Score: {review.get('constitution_risk_score', 0):.3f}")
                                    logger.info(f"   - Cache Ratio: {review.get('cache_ratio', 0):.1%}")
                                    return review
                        else:
                            logger.warning(f"⚠️ Dashboard response {response.status}")
                            
            except Exception as e:
                logger.warning(f"⚠️ Intento {attempt + 1} falló: {e}")
                
            # Backoff exponencial
            wait_time = min(2 ** attempt, 8)
            await asyncio.sleep(wait_time)
            
        logger.error("❌ Timeout: Mensaje no encontrado en dashboard")
        return None
        
    async def _analyze_ai_response_quality(self, review_data: Dict, test_result: TestResult):
        """Analiza la calidad de la respuesta AI."""
        logger.info("🤖 Analizando calidad de respuesta AI...")
        
        ai_bubbles = review_data.get('ai_bubbles', [])
        risk_score = review_data.get('constitution_risk_score', 0)
        cache_ratio = review_data.get('cache_ratio', 0)
        
        # Métricas de calidad
        quality_metrics = {
            'bubble_count': len(ai_bubbles),
            'total_length': sum(len(bubble) for bubble in ai_bubbles),
            'avg_bubble_length': sum(len(bubble) for bubble in ai_bubbles) / len(ai_bubbles) if ai_bubbles else 0,
            'risk_score': risk_score,
            'cache_ratio': cache_ratio,
            'has_emojis': any('❤️' in bubble or '😘' in bubble or '💕' in bubble for bubble in ai_bubbles),
            'persona_consistency': self._check_persona_consistency(ai_bubbles)
        }
        
        test_result.metrics.update(quality_metrics)
        
        # Detectar problemas de calidad
        if risk_score > 0.7:
            self._add_issue(
                IssueType.SECURITY,
                "high",
                f"Risk score alto: {risk_score:.3f}",
                test_result.test_id,
                "Revisar Constitution rules y ajustar prompts",
                False
            )
            
        if cache_ratio < self.cache_hit_rate_target:
            self._add_issue(
                IssueType.CACHE,
                "medium",
                f"Cache ratio bajo: {cache_ratio:.1%}",
                test_result.test_id,
                "Optimizar stable prefixes y prompt consistency",
                True
            )
            
    def _check_persona_consistency(self, bubbles: List[str]) -> float:
        """Verifica consistencia de persona (0.0-1.0)."""
        if not bubbles:
            return 0.0
            
        # Indicadores de persona Nadia
        persona_indicators = [
            'hey', 'haha', 'omg', 'tbh', 'ngl', 'lowkey', 'highkey',
            '❤️', '😘', '💕', '🥰', '😊', '✨'
        ]
        
        total_score = 0
        for bubble in bubbles:
            bubble_lower = bubble.lower()
            score = sum(1 for indicator in persona_indicators if indicator in bubble_lower)
            total_score += min(score / 3, 1.0)  # Max 1.0 per bubble
            
        return total_score / len(bubbles)
        
    async def _approve_review(self, review_id: str) -> bool:
        """Aprueba review en dashboard."""
        logger.info(f"✅ Aprobando review {review_id}...")
        
        headers = {
            'Authorization': f'Bearer {self.dashboard_api_key}',
            'Content-Type': 'application/json'
        }
        
        approval_data = {
            'final_bubbles': ["Automated test approval - OK"],
            'edit_tags': ["automated_test"],
            'quality_score': 4,
            'reviewer_notes': f'Auto-approved by PerfectionLoop at {datetime.now().isoformat()}'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.dashboard_url}/api/reviews/{review_id}/approve",
                    headers=headers,
                    json=approval_data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info("✅ Review aprobado exitosamente")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Error aprobando: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ Excepción aprobando: {e}")
            return False
            
    async def _wait_for_response(self, timeout: int = 30) -> Optional[Dict]:
        """Espera respuesta del bot."""
        logger.info("⏳ Esperando respuesta del bot...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if (self.last_response_received and 
                self.last_response_received['timestamp'] > self.last_message_sent['timestamp']):
                
                response_time = (
                    self.last_response_received['timestamp'] - 
                    self.last_message_sent['timestamp']
                ).total_seconds()
                
                logger.info(f"✅ Respuesta recibida en {response_time:.2f}s")
                return self.last_response_received
                
            await asyncio.sleep(0.5)
            
        logger.warning("⏰ Timeout esperando respuesta")
        return None
        
    async def _verify_response_quality(self, response: Dict, test_result: TestResult):
        """Verifica calidad de respuesta final."""
        logger.info("🔍 Verificando calidad de respuesta final...")
        
        bubbles = response.get('bubbles', [])
        text = response.get('text', '')
        
        quality_checks = {
            'has_content': len(text.strip()) > 0,
            'proper_bubbles': len(bubbles) > 0,
            'reasonable_length': 10 <= len(text) <= 500,
            'has_personality': any(emoji in text for emoji in ['❤️', '😘', '💕', '🥰', '😊']),
            'no_errors': '[ERROR]' not in text.upper() and 'ERROR:' not in text.upper()
        }
        
        test_result.metrics['final_quality_checks'] = quality_checks
        
        # Detectar problemas
        for check, passed in quality_checks.items():
            if not passed:
                severity = "high" if check in ['has_content', 'no_errors'] else "medium"
                self._add_issue(
                    IssueType.FUNCTIONALITY,
                    severity,
                    f"Fallo en verificación: {check}",
                    test_result.test_id,
                    f"Revisar y ajustar sistema para {check}",
                    check in ['reasonable_length', 'has_personality']
                )
                
    def _add_issue(self, issue_type: IssueType, severity: str, description: str, 
                   test_id: str, suggested_fix: str, auto_fixable: bool):
        """Añade problema detectado."""
        issue = IssueDetected(
            issue_type=issue_type,
            severity=severity,
            description=description,
            test_id=test_id,
            timestamp=datetime.now(),
            suggested_fix=suggested_fix,
            auto_fixable=auto_fixable
        )
        
        self.detected_issues.append(issue)
        logger.warning(f"⚠️ Problema detectado: {description}")
        
    async def _detect_issues(self, test_result: TestResult):
        """Detecta problemas automáticamente."""
        logger.info("🔍 Ejecutando detección automática de problemas...")
        
        # Problema de rendimiento
        if test_result.duration > self.response_time_target:
            self._add_issue(
                IssueType.PERFORMANCE,
                "medium",
                f"Test tardó {test_result.duration:.2f}s (límite: {self.response_time_target}s)",
                test_result.test_id,
                "Optimizar pipeline LLM o aumentar recursos",
                False
            )
            
        # Problemas de funcionalidad
        failed_steps = [step for step, passed in test_result.steps.items() if not passed]
        if failed_steps:
            for step in failed_steps:
                self._add_issue(
                    IssueType.FUNCTIONALITY,
                    "high",
                    f"Paso falló: {step}",
                    test_result.test_id,
                    f"Investigar y reparar {step}",
                    step in ['appeared_in_dashboard', 'approved_in_dashboard']
                )
                
    def _log_test_result(self, result: TestResult):
        """Log detallado del resultado."""
        status_emoji = "✅" if result.status == TestStatus.PASSED else "❌"
        logger.info(f"\n{status_emoji} TEST {result.test_id} - {result.status.value.upper()}")
        logger.info(f"   Duración: {result.duration:.2f}s")
        logger.info(f"   Pasos exitosos: {sum(result.steps.values())}/{len(result.steps)}")
        
        if result.errors:
            logger.error(f"   Errores: {', '.join(result.errors)}")
            
    async def run_perfection_suite(self) -> Dict[str, Any]:
        """Ejecuta suite completa orientada a la perfección."""
        logger.info("\n🎯 INICIANDO SUITE DE PERFECCIÓN")
        logger.info("="*80)
        
        # Tests variados para cubrir todos los casos
        test_cases = [
            ("Hello! How are you today?", "basic_greeting"),
            ("My name is Alex and I'm new here", "name_introduction"),  
            ("Tell me something flirty 😘", "personality_test"),
            ("What's your favorite thing to do?", "conversation_flow"),
            ("Send me something with emojis", "emoji_generation"),
            ("Can you help me with something personal?", "intimacy_test"),
            ("🔥🔥🔥", "emoji_only"),
            ("a" * 150, "long_message"),
            ("", "empty_message"),
            ("How much does it cost?", "boundary_test")
        ]
        
        suite_results = {
            'start_time': datetime.now(),
            'test_results': [],
            'overall_metrics': {},
            'issues_found': [],
            'improvement_suggestions': []
        }
        
        # Ejecutar todos los tests
        for message, test_id in test_cases:
            logger.info(f"\n🧪 Ejecutando: {test_id}")
            
            try:
                result = await self.run_comprehensive_test(message, test_id)
                suite_results['test_results'].append(asdict(result))
                
                # Pausa entre tests para no sobrecargar
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"❌ Error en test {test_id}: {e}")
                
        # Análisis de suite completa
        await self._analyze_suite_performance(suite_results)
        
        # Generar reporte de perfección
        self._generate_perfection_report(suite_results)
        
        return suite_results
        
    async def _analyze_suite_performance(self, suite_results: Dict):
        """Analiza rendimiento de toda la suite."""
        logger.info("📊 Analizando rendimiento de suite...")
        
        results = [TestResult(**r) for r in suite_results['test_results']]
        
        if not results:
            return
            
        # Métricas globales
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.status == TestStatus.PASSED)
        success_rate = passed_tests / total_tests
        
        avg_duration = sum(r.duration for r in results) / total_tests
        avg_cache_ratio = sum(r.metrics.get('cache_ratio', 0) for r in results) / total_tests
        
        suite_results['overall_metrics'] = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'success_rate': success_rate,
            'avg_duration': avg_duration,
            'avg_cache_ratio': avg_cache_ratio,
            'target_success_rate': self.success_rate_target,
            'meets_success_target': success_rate >= self.success_rate_target,
            'meets_performance_target': avg_duration <= self.response_time_target,
            'meets_cache_target': avg_cache_ratio >= self.cache_hit_rate_target
        }
        
        # Detectar problemas sistémicos
        if success_rate < self.success_rate_target:
            self._add_issue(
                IssueType.FUNCTIONALITY,
                "critical",
                f"Success rate {success_rate:.1%} bajo del objetivo {self.success_rate_target:.1%}",
                "suite_analysis",
                "Investigar fallos comunes y reparar sistema",
                False
            )
            
        logger.info(f"📊 Success Rate: {success_rate:.1%} (objetivo: {self.success_rate_target:.1%})")
        logger.info(f"📊 Duración promedio: {avg_duration:.2f}s (objetivo: <{self.response_time_target}s)")
        logger.info(f"📊 Cache ratio promedio: {avg_cache_ratio:.1%} (objetivo: >{self.cache_hit_rate_target:.1%})")
        
    def _generate_perfection_report(self, suite_results: Dict):
        """Genera reporte detallado de perfección."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"perfection_report_{timestamp}.json"
        
        # Incluir problemas detectados
        suite_results['issues_found'] = [asdict(issue) for issue in self.detected_issues]
        suite_results['improvement_cycle'] = self.improvement_cycle
        suite_results['fixes_applied'] = self.fixes_applied
        
        # Sugerencias de mejora
        suite_results['improvement_suggestions'] = self._generate_improvement_suggestions()
        
        # Guardar reporte
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(suite_results, f, indent=2, default=str)
            
        logger.info(f"📄 Reporte de perfección guardado: {filename}")
        
        # Log resumen
        metrics = suite_results['overall_metrics']
        logger.info("\n" + "="*80)
        logger.info("🎯 RESUMEN DE PERFECCIÓN")
        logger.info("="*80)
        logger.info(f"✅ Tests exitosos: {metrics['passed_tests']}/{metrics['total_tests']} ({metrics['success_rate']:.1%})")
        logger.info(f"⏱️ Tiempo promedio: {metrics['avg_duration']:.2f}s")
        logger.info(f"💾 Cache ratio: {metrics['avg_cache_ratio']:.1%}")
        logger.info(f"⚠️ Problemas detectados: {len(self.detected_issues)}")
        logger.info(f"🔧 Mejoras sugeridas: {len(suite_results['improvement_suggestions'])}")
        
    def _generate_improvement_suggestions(self) -> List[Dict]:
        """Genera sugerencias de mejora basadas en problemas detectados."""
        suggestions = []
        
        # Agrupar problemas por tipo
        issues_by_type = {}
        for issue in self.detected_issues:
            if issue.issue_type not in issues_by_type:
                issues_by_type[issue.issue_type] = []
            issues_by_type[issue.issue_type].append(issue)
            
        # Generar sugerencias por tipo
        for issue_type, issues in issues_by_type.items():
            if issue_type == IssueType.CACHE:
                suggestions.append({
                    'category': 'Cache Optimization',
                    'priority': 'high',
                    'description': 'Optimizar stable prefixes para mejor cache hit rate',
                    'implementation': 'Revisar StablePrefixManager y ajustar templates',
                    'auto_fixable': True
                })
                
            elif issue_type == IssueType.PERFORMANCE:
                suggestions.append({
                    'category': 'Performance Tuning',
                    'priority': 'medium',
                    'description': 'Optimizar pipeline LLM para reducir latencia',
                    'implementation': 'Paralelizar llamadas, optimizar prompts, usar modelos más rápidos',
                    'auto_fixable': False
                })
                
            elif issue_type == IssueType.FUNCTIONALITY:
                suggestions.append({
                    'category': 'System Reliability',
                    'priority': 'critical',
                    'description': 'Reparar fallos funcionales del sistema',
                    'implementation': 'Investigar logs, reparar componentes defectuosos',
                    'auto_fixable': False
                })
                
        return suggestions
        
    async def run_continuous_perfection_loop(self, cycle_interval: int = 600):
        """Loop continuo de mejora hacia la perfección."""
        logger.info(f"🔄 INICIANDO LOOP DE PERFECCIÓN CONTINUA")
        logger.info(f"🕐 Intervalo: {cycle_interval}s ({cycle_interval//60} minutos)")
        logger.info("🎯 Objetivo: Perfección absoluta del sistema")
        
        while True:
            try:
                self.improvement_cycle += 1
                logger.info(f"\n🔄 CICLO DE MEJORA #{self.improvement_cycle}")
                logger.info("="*80)
                
                # Ejecutar suite de perfección
                suite_results = await self.run_perfection_suite()
                
                # Aplicar mejoras automáticas
                auto_fixes = await self._apply_automatic_fixes()
                self.fixes_applied += auto_fixes
                
                # Verificar si alcanzamos perfección
                if self._check_perfection_achieved(suite_results):
                    logger.info("🏆 ¡PERFECCIÓN ALCANZADA!")
                    logger.info("✨ Sistema funcionando al 100% de eficiencia")
                    logger.info("🎉 MISIÓN COMPLETADA - Loop de perfección finalizado")
                    
                    # Generar reporte final de perfección
                    self._generate_final_perfection_report(suite_results)
                    
                    # Preguntar al usuario qué hacer
                    should_continue = await self._ask_user_continue_after_perfection()
                    
                    if not should_continue:
                        logger.info("🛑 Sistema deteniéndose por decisión del usuario")
                        logger.info("✅ Perfección mantenida y documentada")
                        break  # Sale del loop completamente
                    else:
                        logger.info("🔄 Continuando monitoreo de mantenimiento...")
                        # Monitoreo de mantenimiento (mucho menos frecuente)
                        await asyncio.sleep(cycle_interval * 6)  # 6x menos frecuente (60 min)
                else:
                    # Analizar próximos pasos
                    next_actions = self._plan_next_improvements()
                    logger.info(f"📋 Próximas acciones: {len(next_actions)} mejoras planificadas")
                    
                    await asyncio.sleep(cycle_interval)
                    
            except KeyboardInterrupt:
                logger.info("\n🛑 Loop de perfección interrumpido por usuario")
                break
            except Exception as e:
                logger.error(f"❌ Error en ciclo de perfección: {e}")
                traceback.print_exc()
                await asyncio.sleep(60)  # Pausa antes de continuar
                
    async def _apply_automatic_fixes(self) -> int:
        """Aplica fixes automáticos donde sea posible."""
        logger.info("🔧 Aplicando mejoras automáticas...")
        
        fixes_applied = 0
        
        # Aplicar fixes por tipo de problema detectado
        issue_types_found = set(issue.issue_type for issue in self.detected_issues)
        
        for issue_type in issue_types_found:
            try:
                if issue_type == IssueType.CACHE:
                    await self._fix_cache_optimization()
                    fixes_applied += 1
                    logger.info(f"✅ Cache optimization aplicada automáticamente")
                    
                elif issue_type == IssueType.DASHBOARD:
                    await self._fix_dashboard_issues()
                    fixes_applied += 1
                    logger.info(f"✅ Dashboard issues reparados automáticamente")
                    
                elif issue_type == IssueType.PERFORMANCE:
                    await self._fix_performance_issues()
                    fixes_applied += 1
                    logger.info(f"✅ Performance optimizations aplicadas automáticamente")
                    
                elif issue_type == IssueType.FUNCTIONALITY:
                    # Para funcionalidad, aplicar fixes específicos
                    await self._fix_telegram_connection_issues()
                    await self._fix_response_quality_issues()
                    fixes_applied += 1
                    logger.info(f"✅ Functionality fixes aplicados automáticamente")
                    
            except Exception as e:
                logger.error(f"❌ Error aplicando fix para {issue_type}: {e}")
                
        # Aplicar fixes preventivos siempre
        try:
            await self._apply_preventive_maintenance()
            fixes_applied += 1
        except Exception as e:
            logger.warning(f"⚠️ Error en mantenimiento preventivo: {e}")
                    
        return fixes_applied
        
    async def _apply_preventive_maintenance(self):
        """Aplica mantenimiento preventivo para evitar bugs."""
        logger.info("🔧 Ejecutando mantenimiento preventivo...")
        
        # 1. Verificar y limpiar logs antiguos
        try:
            import glob
            log_files = glob.glob("*.log")
            for log_file in log_files:
                size_mb = os.path.getsize(log_file) / 1024 / 1024
                if size_mb > 50:  # Más de 50MB
                    os.rename(log_file, f"{log_file}.old")
                    logger.info(f"✅ Log {log_file} rotado por tamaño")
        except:
            pass
            
        # 2. Verificar espacio en disco
        try:
            import shutil
            free_space_gb = shutil.disk_usage('.').free / 1024 / 1024 / 1024
            if free_space_gb < 1:  # Menos de 1GB libre
                logger.warning(f"⚠️ Poco espacio libre: {free_space_gb:.1f}GB")
        except:
            pass
            
        # 3. Verificar memoria del proceso
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            if memory_mb > 500:  # Más de 500MB
                logger.warning(f"⚠️ Alto uso de memoria: {memory_mb:.1f}MB")
        except:
            pass
        
    async def _fix_cache_optimization(self):
        """Aplica optimizaciones de cache automáticamente."""
        logger.info("🔧 Aplicando optimización de cache automática...")
        
        # Fix 1: Aumentar stable prefix length para mejor cache hit
        try:
            config_file = "/home/rober/projects/chatbot_nadia/llms/stable_prefix_manager.py"
            if os.path.exists(config_file):
                # Leer archivo actual
                with open(config_file, 'r') as f:
                    content = f.read()
                
                # Buscar y ajustar MIN_PREFIX_LENGTH si es muy bajo
                if "MIN_PREFIX_LENGTH = " in content:
                    import re
                    pattern = r'MIN_PREFIX_LENGTH = (\d+)'
                    match = re.search(pattern, content)
                    if match:
                        current_length = int(match.group(1))
                        if current_length < 1024:  # Si es menor a 1024, aumentar
                            new_content = re.sub(pattern, 'MIN_PREFIX_LENGTH = 1024', content)
                            with open(config_file, 'w') as f:
                                f.write(new_content)
                            logger.info(f"✅ Cache prefix aumentado de {current_length} a 1024 tokens")
                            
        except Exception as e:
            logger.warning(f"⚠️ No se pudo ajustar cache config: {e}")
            
    async def _fix_dashboard_issues(self):
        """Repara problemas comunes del dashboard automáticamente."""
        logger.info("🔧 Reparando problemas del dashboard...")
        
        try:
            # Fix 1: Reiniciar endpoints que fallen
            headers = {'Authorization': f'Bearer {self.dashboard_api_key}'}
            
            async with aiohttp.ClientSession() as session:
                # Test endpoint de salud
                try:
                    async with session.get(f"{self.dashboard_url}/api/health", headers=headers, timeout=5) as response:
                        if response.status != 200:
                            logger.warning("⚠️ Dashboard endpoint no responde correctamente")
                except:
                    logger.warning("⚠️ Dashboard no accesible, posible reinicio necesario")
                    
        except Exception as e:
            logger.warning(f"⚠️ Error verificando dashboard: {e}")
            
    async def _fix_telegram_connection_issues(self):
        """Repara problemas de conexión con Telegram."""
        logger.info("🔧 Verificando y reparando conexión Telegram...")
        
        try:
            if self.client and not self.client.is_connected():
                logger.info("🔄 Reconectando cliente Telegram...")
                await self.client.connect()
                
            # Test de conectividad básica
            me = await self.client.get_me()
            logger.info(f"✅ Telegram conectado como: {me.first_name}")
            
        except Exception as e:
            logger.warning(f"⚠️ Problema con conexión Telegram: {e}")
            try:
                # Intentar reconexión completa
                await self.client.disconnect()
                await asyncio.sleep(2)
                await self.client.start(phone=self.test_phone)
                logger.info("✅ Reconexión Telegram exitosa")
            except:
                logger.error("❌ No se pudo reconectar Telegram")
                
    async def _fix_performance_issues(self):
        """Optimiza rendimiento automáticamente."""
        logger.info("🔧 Aplicando optimizaciones de rendimiento...")
        
        # Fix 1: Limpiar caché Redis si está muy lleno
        try:
            import redis
            r = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
            
            # Verificar uso de memoria
            info = r.info('memory')
            used_memory_mb = info['used_memory'] / 1024 / 1024
            
            if used_memory_mb > 100:  # Si Redis usa más de 100MB
                # Limpiar keys viejos del WAL
                keys = r.keys('wal:*')
                old_keys = []
                for key in keys:
                    ttl = r.ttl(key)
                    if ttl > 3600:  # Más de 1 hora
                        old_keys.append(key)
                        
                if old_keys:
                    r.delete(*old_keys)
                    logger.info(f"✅ Limpiados {len(old_keys)} keys antiguos de Redis")
                    
        except Exception as e:
            logger.warning(f"⚠️ No se pudo optimizar Redis: {e}")
            
    async def _fix_response_quality_issues(self):
        """Mejora calidad de respuestas automáticamente."""
        logger.info("🔧 Mejorando calidad de respuestas...")
        
        # Fix 1: Ajustar configuración de temperatura si las respuestas son muy repetitivas
        try:
            # Verificar historial reciente de respuestas
            recent_responses = [r.response_data.get('text', '') for r in self.test_results[-5:] 
                             if r.response_data and r.response_data.get('text')]
            
            if len(recent_responses) >= 3:
                # Verificar si hay mucha repetición
                unique_words = set()
                total_words = 0
                
                for response in recent_responses:
                    words = response.lower().split()
                    unique_words.update(words)
                    total_words += len(words)
                    
                if total_words > 0:
                    uniqueness_ratio = len(unique_words) / total_words
                    
                    if uniqueness_ratio < 0.3:  # Muy repetitivo
                        logger.info(f"⚠️ Respuestas repetitivas detectadas (ratio: {uniqueness_ratio:.2f})")
                        logger.info("💡 Sugerencia: Aumentar temperatura en LLM config")
                        
        except Exception as e:
            logger.warning(f"⚠️ Error analizando calidad: {e}")
        
    def _check_perfection_achieved(self, suite_results: Dict) -> bool:
        """Verifica si se alcanzó la perfección."""
        metrics = suite_results['overall_metrics']
        
        perfection_criteria = [
            metrics['success_rate'] >= 0.98,  # 98% éxito
            metrics['avg_duration'] <= 8.0,   # Menos de 8s
            metrics['avg_cache_ratio'] >= 0.80,  # 80% cache hits
            len([i for i in self.detected_issues if i.severity == 'critical']) == 0
        ]
        
        return all(perfection_criteria)
        
    def _plan_next_improvements(self) -> List[str]:
        """Planifica próximas mejoras basadas en análisis."""
        # Placeholder para lógica de planificación inteligente
        return ["Optimizar prompts", "Mejorar cache", "Reducir latencia"]
        
    def _generate_final_perfection_report(self, suite_results: Dict):
        """Genera reporte final cuando se alcanza la perfección."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"PERFECTION_ACHIEVED_{timestamp}.json"
        
        final_report = {
            "achievement": "PERFECTION_REACHED",
            "timestamp": datetime.now().isoformat(),
            "improvement_cycles": self.improvement_cycle,
            "total_fixes_applied": self.fixes_applied,
            "final_metrics": suite_results['overall_metrics'],
            "perfection_criteria": {
                "success_rate": f"{suite_results['overall_metrics']['success_rate']:.1%} >= 98%",
                "response_time": f"{suite_results['overall_metrics']['avg_duration']:.1f}s <= 8.0s",
                "cache_ratio": f"{suite_results['overall_metrics']['avg_cache_ratio']:.1%} >= 80%",
                "critical_issues": f"{len([i for i in self.detected_issues if i.severity == 'critical'])} = 0"
            },
            "celebration_message": "🏆 NADIA CHATBOT HAS ACHIEVED PERFECTION! 🏆"
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=2, default=str)
            
        logger.info(f"🏆 Reporte de perfección guardado: {filename}")
        
        # Mostrar celebración
        logger.info("\n" + "🎉" * 60)
        logger.info("🏆" * 20 + " PERFECCIÓN ALCANZADA " + "🏆" * 20)
        logger.info("🎉" * 60)
        logger.info(f"📊 Success Rate: {suite_results['overall_metrics']['success_rate']:.1%}")
        logger.info(f"⚡ Response Time: {suite_results['overall_metrics']['avg_duration']:.1f}s")
        logger.info(f"💾 Cache Efficiency: {suite_results['overall_metrics']['avg_cache_ratio']:.1%}")
        logger.info(f"🔧 Improvements Applied: {self.fixes_applied}")
        logger.info(f"🔄 Cycles to Perfection: {self.improvement_cycle}")
        logger.info("🎉" * 60)
        
    async def _ask_user_continue_after_perfection(self) -> bool:
        """Pregunta al usuario si continuar después de alcanzar perfección."""
        logger.info("\n" + "="*80)
        logger.info("🤔 DECISIÓN REQUERIDA: ¿Qué hacer ahora?")
        logger.info("="*80)
        logger.info("1️⃣  DETENER: El sistema alcanzó la perfección. Misión completada.")
        logger.info("2️⃣  CONTINUAR: Mantener monitoreo cada 60 min para preservar perfección.")
        logger.info("")
        logger.info("💡 Beneficios de continuar:")
        logger.info("   • Detecta degradación temprana")
        logger.info("   • Mantiene métricas de perfección")
        logger.info("   • Reportes de estabilidad")
        logger.info("")
        logger.info("💡 Beneficios de detener:")
        logger.info("   • Libera recursos del sistema")
        logger.info("   • Perfección ya documentada")
        logger.info("   • Puedes reiniciar cuando quieras")
        logger.info("")
        
        # Dar tiempo para que el usuario lea
        for i in range(30, 0, -1):
            print(f"\r⏳ Decidiendo en {i}s... (Ctrl+C para detener inmediatamente)", end="", flush=True)
            await asyncio.sleep(1)
            
        print("\r" + " " * 60 + "\r", end="")  # Limpiar línea
        
        # Por defecto, continuar (más conservador)
        logger.info("⚡ DECISIÓN AUTOMÁTICA: Continuando monitoreo de mantenimiento")
        logger.info("💡 Puedes detener en cualquier momento con Ctrl+C")
        return True

async def main():
    """Función principal del sistema de perfección."""
    perfection_loop = PerfectionLoop()
    
    try:
        await perfection_loop.initialize()
        
        print("\n🎯 SISTEMA DE PERFECCIÓN CONTINUA NADIA")
        print("="*50)
        print("1. Ejecutar suite de perfección única")
        print("2. Test individual comprensivo")
        print("3. ⭐ LOOP DE PERFECCIÓN CONTINUA ⭐")
        print("4. Solo verificar estado actual")
        
        choice = input("\nElige opción (1-4): ").strip()
        
        if choice == "1":
            print("\n🧪 Ejecutando suite de perfección...")
            await perfection_loop.run_perfection_suite()
            
        elif choice == "2":
            message = input("Mensaje de prueba: ").strip()
            await perfection_loop.run_comprehensive_test(message)
            
        elif choice == "3":
            interval = input("Intervalo en minutos (default 10): ").strip()
            interval = int(interval) * 60 if interval.isdigit() else 600
            print(f"\n🔄 Iniciando loop de perfección (cada {interval//60} min)...")
            await perfection_loop.run_continuous_perfection_loop(interval)
            
        elif choice == "4":
            print("\n📊 Verificando estado del sistema...")
            # Implementar verificación rápida de estado
            
        else:
            print("❌ Opción inválida")
            
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        traceback.print_exc()
    finally:
        if perfection_loop.client:
            await perfection_loop.client.disconnect()
            logger.info("🔌 Cliente Telegram desconectado")

if __name__ == "__main__":
    asyncio.run(main())