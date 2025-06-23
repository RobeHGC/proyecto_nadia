#!/usr/bin/env python3
"""
Monitor Visual de Testing en Tiempo Real
Sistema de visualización avanzado para el loop de perfección continua
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import asdict
import os
import sys

# Importar rich para visualización avanzada
try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.align import Align
    from rich.columns import Columns
    from rich.tree import Tree
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️ Rich no disponible. Instalarlo con: pip install rich")

# Importar el sistema de testing
from automated_e2e_tester import PerfectionLoop, TestResult, IssueDetected, TestStatus, IssueType

class VisualPerfectionMonitor:
    """Monitor visual avanzado para el sistema de perfección."""
    
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.perfection_loop = PerfectionLoop()
        
        # Estado del monitor
        self.test_history: List[TestResult] = []
        self.current_metrics: Dict[str, Any] = {}
        self.system_status = "initializing"
        self.last_update = datetime.now()
        
        # Configuración de visualización
        self.max_history_display = 10
        self.refresh_rate = 0.5  # 500ms
        
        # Colores y estilos
        self.status_colors = {
            TestStatus.PASSED: "green",
            TestStatus.FAILED: "red", 
            TestStatus.RUNNING: "yellow",
            TestStatus.PENDING: "blue",
            TestStatus.SKIPPED: "dim"
        }
        
        self.severity_colors = {
            "low": "green",
            "medium": "yellow", 
            "high": "red",
            "critical": "bold red"
        }
        
    async def initialize(self):
        """Inicializa el monitor y el sistema de testing."""
        if not RICH_AVAILABLE:
            print("❌ Rich requerido para monitor visual")
            return False
            
        self.console.print("🚀 Inicializando Monitor Visual de Perfección...", style="bold blue")
        
        try:
            await self.perfection_loop.initialize()
            self.system_status = "ready"
            self.console.print("✅ Sistema inicializado correctamente", style="bold green")
            return True
        except Exception as e:
            self.console.print(f"❌ Error inicializando: {e}", style="bold red")
            self.system_status = "error"
            return False
            
    def create_header_panel(self) -> Panel:
        """Crea el panel de encabezado con información del sistema."""
        now = datetime.now()
        uptime = now - self.perfection_loop.last_message_sent['timestamp'] if self.perfection_loop.last_message_sent else timedelta(0)
        
        header_text = Text()
        header_text.append("🤖 NADIA PERFECTION MONITOR ", style="bold cyan")
        header_text.append("v2.0\n", style="dim")
        header_text.append(f"Status: ", style="white")
        
        if self.system_status == "ready":
            header_text.append("🟢 OPERATIONAL", style="bold green")
        elif self.system_status == "running":
            header_text.append("🟡 TESTING", style="bold yellow")
        elif self.system_status == "error":
            header_text.append("🔴 ERROR", style="bold red")
        else:
            header_text.append("🔵 INITIALIZING", style="bold blue")
            
        header_text.append(f"\nTime: {now.strftime('%H:%M:%S')}")
        header_text.append(f"\nCycle: #{self.perfection_loop.improvement_cycle}")
        header_text.append(f"\nFixes Applied: {self.perfection_loop.fixes_applied}")
        
        return Panel(
            Align.center(header_text),
            title="🎯 SYSTEM STATUS",
            border_style="cyan"
        )
        
    def create_metrics_panel(self) -> Panel:
        """Crea panel con métricas en tiempo real."""
        if not self.current_metrics:
            return Panel("📊 No metrics available yet...", title="METRICS", border_style="yellow")
            
        metrics_table = Table(show_header=False, show_edge=False, pad_edge=False)
        metrics_table.add_column("Metric", style="cyan", width=20)
        metrics_table.add_column("Value", style="white", width=15)
        metrics_table.add_column("Target", style="dim", width=15)
        metrics_table.add_column("Status", width=10)
        
        # Success Rate
        success_rate = self.current_metrics.get('success_rate', 0)
        target_success = self.current_metrics.get('target_success_rate', 0.95)
        success_status = "✅" if success_rate >= target_success else "❌"
        metrics_table.add_row(
            "Success Rate",
            f"{success_rate:.1%}",
            f"{target_success:.1%}",
            success_status
        )
        
        # Response Time
        avg_duration = self.current_metrics.get('avg_duration', 0)
        target_duration = 10.0
        duration_status = "✅" if avg_duration <= target_duration else "❌"
        metrics_table.add_row(
            "Avg Response Time",
            f"{avg_duration:.1f}s",
            f"{target_duration:.1f}s",
            duration_status
        )
        
        # Cache Hit Rate
        cache_ratio = self.current_metrics.get('avg_cache_ratio', 0)
        target_cache = 0.75
        cache_status = "✅" if cache_ratio >= target_cache else "❌"
        metrics_table.add_row(
            "Cache Hit Rate",
            f"{cache_ratio:.1%}",
            f"{target_cache:.1%}",
            cache_status
        )
        
        # Total Tests
        total_tests = self.current_metrics.get('total_tests', 0)
        passed_tests = self.current_metrics.get('passed_tests', 0)
        metrics_table.add_row(
            "Tests Executed",
            f"{passed_tests}/{total_tests}",
            "All Pass",
            "✅" if passed_tests == total_tests else "❌"
        )
        
        return Panel(
            metrics_table,
            title="📊 PERFORMANCE METRICS",
            border_style="green"
        )
        
    def create_test_history_panel(self) -> Panel:
        """Crea panel con historial de tests."""
        if not self.test_history:
            return Panel("📝 No test history yet...", title="TEST HISTORY", border_style="blue")
            
        history_table = Table(show_header=True, header_style="bold magenta")
        history_table.add_column("Time", width=8)
        history_table.add_column("Test ID", width=15)
        history_table.add_column("Message", width=25)
        history_table.add_column("Duration", width=8)
        history_table.add_column("Status", width=8)
        history_table.add_column("Steps", width=10)
        
        # Mostrar últimos tests
        recent_tests = self.test_history[-self.max_history_display:]
        
        for test in recent_tests:
            timestamp = test.timestamp.strftime("%H:%M:%S")
            message_preview = test.message[:22] + "..." if len(test.message) > 25 else test.message
            duration_str = f"{test.duration:.1f}s"
            
            # Estado con color
            status_color = self.status_colors.get(test.status, "white")
            status_text = test.status.value.upper()
            
            # Pasos exitosos
            steps_passed = sum(test.steps.values())
            steps_total = len(test.steps)
            steps_str = f"{steps_passed}/{steps_total}"
            
            history_table.add_row(
                timestamp,
                test.test_id,
                message_preview,
                duration_str,
                f"[{status_color}]{status_text}[/]",
                steps_str
            )
            
        return Panel(
            history_table,
            title="📝 TEST HISTORY",
            border_style="blue"
        )
        
    def create_issues_panel(self) -> Panel:
        """Crea panel con problemas detectados."""
        issues = self.perfection_loop.detected_issues
        
        if not issues:
            return Panel(
                Align.center("🎉 No issues detected!\nSystem running perfectly!"),
                title="🚨 ISSUES",
                border_style="green"
            )
            
        issues_table = Table(show_header=True, header_style="bold red")
        issues_table.add_column("Time", width=8)
        issues_table.add_column("Type", width=12)
        issues_table.add_column("Severity", width=8)
        issues_table.add_column("Description", width=30)
        issues_table.add_column("Auto-Fix", width=8)
        
        # Mostrar últimos problemas
        recent_issues = issues[-10:]
        
        for issue in recent_issues:
            timestamp = issue.timestamp.strftime("%H:%M:%S")
            issue_type = issue.issue_type.value.title()
            
            # Severidad con color
            severity_color = self.severity_colors.get(issue.severity, "white")
            severity_text = f"[{severity_color}]{issue.severity.upper()}[/]"
            
            auto_fix = "✅" if issue.auto_fixable else "❌"
            
            issues_table.add_row(
                timestamp,
                issue_type,
                severity_text,
                issue.description[:27] + "..." if len(issue.description) > 30 else issue.description,
                auto_fix
            )
            
        return Panel(
            issues_table,
            title="🚨 DETECTED ISSUES",
            border_style="red"
        )
        
    def create_progress_panel(self, current_test: Optional[str] = None) -> Panel:
        """Crea panel de progreso del test actual."""
        if not current_test:
            return Panel(
                Align.center("⏳ Waiting for next test..."),
                title="⚡ CURRENT PROGRESS",
                border_style="yellow"
            )
            
        progress_text = Text()
        progress_text.append("🧪 Running Test: ", style="bold blue")
        progress_text.append(f"{current_test}\n", style="white")
        progress_text.append("⏳ Progress: ", style="blue")
        progress_text.append("Testing in progress...", style="yellow")
        
        return Panel(
            Align.center(progress_text),
            title="⚡ CURRENT PROGRESS",
            border_style="yellow"
        )
        
    def create_dashboard_layout(self, current_test: Optional[str] = None) -> Layout:
        """Crea el layout completo del dashboard."""
        layout = Layout()
        
        # Dividir en secciones
        layout.split_column(
            Layout(name="header", size=7),
            Layout(name="body"),
            Layout(name="footer", size=5)
        )
        
        # Dividir body en columnas
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        # Dividir columnas en secciones
        layout["left"].split_column(
            Layout(name="metrics", size=12),
            Layout(name="history")
        )
        
        layout["right"].split_column(
            Layout(name="progress", size=8),
            Layout(name="issues")
        )
        
        # Asignar paneles
        layout["header"].update(self.create_header_panel())
        layout["metrics"].update(self.create_metrics_panel())
        layout["history"].update(self.create_test_history_panel())
        layout["progress"].update(self.create_progress_panel(current_test))
        layout["issues"].update(self.create_issues_panel())
        
        # Footer
        footer_text = Text()
        footer_text.append("⌨️ Controles: ", style="bold")
        footer_text.append("Ctrl+C = Exit", style="dim")
        footer_text.append(" | ", style="dim")
        footer_text.append("Space = Pause", style="dim")
        footer_text.append(" | ", style="dim") 
        footer_text.append("R = Run Test", style="dim")
        
        layout["footer"].update(Panel(
            Align.center(footer_text),
            title="CONTROLS",
            border_style="dim"
        ))
        
        return layout
        
    async def update_data(self):
        """Actualiza los datos del monitor."""
        # Sincronizar datos del perfection loop
        self.test_history = self.perfection_loop.test_results
        
        # Calcular métricas actuales
        if self.test_history:
            total_tests = len(self.test_history)
            passed_tests = sum(1 for t in self.test_history if t.status == TestStatus.PASSED)
            
            self.current_metrics = {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'success_rate': passed_tests / total_tests if total_tests > 0 else 0,
                'avg_duration': sum(t.duration for t in self.test_history) / total_tests if total_tests > 0 else 0,
                'avg_cache_ratio': sum(t.metrics.get('cache_ratio', 0) for t in self.test_history) / total_tests if total_tests > 0 else 0,
                'target_success_rate': self.perfection_loop.success_rate_target,
            }
            
        self.last_update = datetime.now()
        
    async def run_visual_perfection_loop(self):
        """Ejecuta el loop de perfección con visualización en tiempo real."""
        if not RICH_AVAILABLE:
            self.console.print("❌ Rich requerido para monitor visual", style="bold red")
            return
            
        self.console.print("🎯 Iniciando Loop de Perfección Visual...", style="bold green")
        
        current_test = None
        
        with Live(
            self.create_dashboard_layout(),
            refresh_per_second=1/self.refresh_rate,
            screen=True
        ) as live:
            
            async def update_display():
                """Actualiza la visualización."""
                while True:
                    await self.update_data()
                    live.update(self.create_dashboard_layout(current_test))
                    await asyncio.sleep(self.refresh_rate)
                    
            async def run_testing_loop():
                """Ejecuta el loop de testing."""
                nonlocal current_test
                
                cycle = 0
                while True:
                    try:
                        cycle += 1
                        self.system_status = "running"
                        
                        # Ejecutar suite de perfección
                        current_test = f"Perfection Suite #{cycle}"
                        await self.perfection_loop.run_perfection_suite()
                        current_test = None
                        
                        # Aplicar mejoras automáticas
                        auto_fixes = await self.perfection_loop._apply_automatic_fixes()
                        
                        # Verificar perfección
                        if self.current_metrics.get('success_rate', 0) >= 0.98:
                            self.system_status = "perfect"
                            # Reducir frecuencia si sistema es perfecto
                            await asyncio.sleep(1200)  # 20 minutos
                        else:
                            self.system_status = "ready"
                            await asyncio.sleep(600)  # 10 minutos
                            
                    except Exception as e:
                        self.system_status = "error"
                        self.console.print(f"❌ Error en testing loop: {e}", style="bold red")
                        await asyncio.sleep(60)
                        
            # Ejecutar ambos loops concurrentemente
            await asyncio.gather(
                update_display(),
                run_testing_loop()
            )
            
    async def run_single_test_visual(self, message: str):
        """Ejecuta un test individual con visualización."""
        if not RICH_AVAILABLE:
            print(f"🧪 Ejecutando test: {message}")
            result = await self.perfection_loop.run_comprehensive_test(message)
            print(f"Resultado: {result.status.value}")
            return result
            
        current_test = f"Single Test: {message[:20]}..."
        
        with Live(
            self.create_dashboard_layout(current_test),
            refresh_per_second=2,
            screen=True
        ) as live:
            
            async def update_display():
                while True:
                    await self.update_data()
                    live.update(self.create_dashboard_layout(current_test))
                    await asyncio.sleep(0.5)
                    
            # Ejecutar test
            test_task = asyncio.create_task(
                self.perfection_loop.run_comprehensive_test(message)
            )
            display_task = asyncio.create_task(update_display())
            
            # Esperar que termine el test
            try:
                result = await test_task
                display_task.cancel()
                return result
            except Exception as e:
                display_task.cancel()
                raise e

async def main():
    """Función principal del monitor visual."""
    monitor = VisualPerfectionMonitor()
    
    # Verificar dependencias
    if not RICH_AVAILABLE:
        print("❌ Rich no disponible. Instalar con: pip install rich")
        print("🔄 Cayendo a modo texto básico...")
        # Aquí podrías implementar un modo básico sin rich
        return
        
    print("🎯 MONITOR VISUAL DE PERFECCIÓN NADIA")
    print("="*50)
    
    # Inicializar
    if not await monitor.initialize():
        print("❌ Error inicializando monitor")
        return
        
    print("\n🖥️ MODOS DE VISUALIZACIÓN:")
    print("1. 🔄 Loop de Perfección Continua Visual")
    print("2. 🧪 Test Individual con Visualización")
    print("3. 📊 Solo Mostrar Dashboard Actual")
    
    choice = input("\nElige modo (1-3): ").strip()
    
    try:
        if choice == "1":
            print("\n🔄 Iniciando loop visual...")
            await monitor.run_visual_perfection_loop()
            
        elif choice == "2":
            message = input("Mensaje de prueba: ").strip()
            print(f"\n🧪 Ejecutando test visual: {message}")
            result = await monitor.run_single_test_visual(message)
            print(f"\n✅ Test completado: {result.status.value}")
            
        elif choice == "3":
            print("\n📊 Mostrando dashboard...")
            await monitor.update_data()
            
            with Live(
                monitor.create_dashboard_layout(),
                refresh_per_second=1,
                screen=True
            ) as live:
                try:
                    while True:
                        await monitor.update_data()
                        live.update(monitor.create_dashboard_layout())
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    pass
                    
        else:
            print("❌ Opción inválida")
            
    except KeyboardInterrupt:
        print("\n🛑 Monitor interrumpido por usuario")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if monitor.perfection_loop.client:
            await monitor.perfection_loop.client.disconnect()
            print("🔌 Desconectado del sistema")

if __name__ == "__main__":
    asyncio.run(main())