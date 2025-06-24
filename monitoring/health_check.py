#!/usr/bin/env python3
import asyncio
import redis.asyncio as redis
import psutil
import json
from datetime import datetime
import os

class HealthChecker:
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.alerts = []
        
    async def check_all(self):
        """Ejecuta todos los health checks."""
        print(f"\n🏥 NADIA Health Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Reset alerts
        self.alerts = []
        
        # Run checks
        await self.check_redis_connection()
        await self.check_message_queues()
        await self.check_conversation_memory()
        await self.check_system_resources()
        
        # Summary
        if self.alerts:
            print(f"\n❌ PROBLEMAS ENCONTRADOS: {len(self.alerts)}")
            for alert in self.alerts:
                print(f"  - {alert}")
        else:
            print("\n✅ Sistema funcionando correctamente")
            
        return len(self.alerts) == 0
    
    async def check_redis_connection(self):
        """Verifica conexión con Redis."""
        try:
            r = await redis.from_url(self.redis_url)
            await r.ping()
            print("✅ Redis: Conectado")
            
            # Check memory usage
            info = await r.info()
            used_mb = info['used_memory'] / 1024 / 1024
            print(f"   Memoria usada: {used_mb:.1f}MB")
            
            if used_mb > 200:
                self.alerts.append(f"Redis usando mucha memoria: {used_mb:.1f}MB")
                
            await r.aclose()
        except Exception as e:
            print("❌ Redis: Error de conexión")
            self.alerts.append(f"Redis no disponible: {e}")
    
    async def check_message_queues(self):
        """Verifica que las colas no estén saturadas."""
        try:
            r = await redis.from_url(self.redis_url)
            
            # Check queue sizes
            wal_queue = await r.llen("nadia_message_queue")
            review_queue = await r.zcard("nadia_review_queue") 
            approved_queue = await r.llen("nadia_approved_messages")
            
            print(f"📊 Colas de mensajes:")
            print(f"   WAL Queue: {wal_queue} mensajes")
            print(f"   Review Queue: {review_queue} pendientes")
            print(f"   Approved Queue: {approved_queue} por enviar")
            
            # Alert if queues are too large
            if wal_queue > 100:
                self.alerts.append(f"WAL queue muy grande: {wal_queue}")
            if review_queue > 50:
                self.alerts.append(f"Review queue saturada: {review_queue}")
                
            await r.aclose()
        except Exception as e:
            self.alerts.append(f"Error verificando colas: {e}")
    
    async def check_conversation_memory(self):
        """Verifica que se estén guardando conversaciones."""
        try:
            r = await redis.from_url(self.redis_url)
            
            # Count conversation histories
            history_count = 0
            async for key in r.scan_iter(match="user:*:history"):
                history_count += 1
                
            print(f"💬 Conversaciones activas: {history_count}")
            
            # Sample check - get one history
            if history_count > 0:
                async for key in r.scan_iter(match="user:*:history"):
                    history_data = await r.get(key)
                    if history_data:
                        history = json.loads(history_data)
                        print(f"   Ejemplo: {len(history)} mensajes en historial")
                    break
            else:
                self.alerts.append("No hay conversaciones guardadas - ¿memoria desconectada?")
                
            await r.aclose()
        except Exception as e:
            self.alerts.append(f"Error verificando memoria: {e}")
    
    async def check_system_resources(self):
        """Verifica recursos del sistema."""
        try:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            print(f"💻 Recursos del sistema:")
            print(f"   CPU: {cpu}%")
            print(f"   RAM: {memory.percent}% ({memory.used/1024/1024/1024:.1f}GB / {memory.total/1024/1024/1024:.1f}GB)")
            print(f"   Disco: {disk.percent}% usado")
            
            if cpu > 80:
                self.alerts.append(f"CPU muy alto: {cpu}%")
            if memory.percent > 85:
                self.alerts.append(f"RAM crítica: {memory.percent}%")
            if disk.percent > 90:
                self.alerts.append(f"Disco casi lleno: {disk.percent}%")
                
        except Exception as e:
            self.alerts.append(f"Error verificando recursos: {e}")

async def main():
    checker = HealthChecker()
    healthy = await checker.check_all()
    
    # Exit code for scripts
    exit(0 if healthy else 1)

if __name__ == "__main__":
    asyncio.run(main())