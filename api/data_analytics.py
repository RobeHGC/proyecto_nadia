# api/data_analytics.py
"""Data Analytics endpoints for NADIA HITL dashboard."""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import asyncio

import redis.asyncio as redis
from fastapi import HTTPException, Query, Request, Response, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from database.models import DatabaseManager
from utils.config import Config
from .backup_manager import BackupManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

# Pydantic models
class AnalyticsDataRequest(BaseModel):
    page: int = Field(default=1, ge=1, le=1000)
    limit: int = Field(default=50, ge=10, le=500)
    sort_by: str = Field(default="created_at", pattern="^[a-zA-Z_][a-zA-Z0-9_]*$")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    search: Optional[str] = Field(default=None, max_length=200)
    date_from: Optional[str] = Field(default=None, pattern="^(\\d{4}-\\d{2}-\\d{2}|)$")
    date_to: Optional[str] = Field(default=None, pattern="^(\\d{4}-\\d{2}-\\d{2}|)$")
    user_id: Optional[str] = Field(default=None, max_length=50)
    customer_status: Optional[str] = Field(default=None, pattern="^(PROSPECT|LEAD_QUALIFIED|CUSTOMER|CHURNED|LEAD_EXHAUSTED|)$")
    
    @field_validator('search', 'date_from', 'date_to', 'user_id', 'customer_status', mode='before')
    @classmethod
    def convert_empty_to_none(cls, v):
        """Convert empty strings to None for optional fields."""
        return None if v == "" else v

class BackupRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100, pattern="^[a-zA-Z0-9_-]*$")
    include_data: bool = Field(default=True)
    compress: bool = Field(default=True)

class CleanDataRequest(BaseModel):
    date_from: Optional[str] = Field(default=None, pattern="^(\\d{4}-\\d{2}-\\d{2}|)$")
    date_to: Optional[str] = Field(default=None, pattern="^(\\d{4}-\\d{2}-\\d{2}|)$")
    user_ids: Optional[List[str]] = Field(default=None, max_items=100)
    test_data_only: bool = Field(default=False)
    confirm: bool = Field(default=False)
    
    @field_validator('date_from', 'date_to', mode='before')
    @classmethod
    def convert_empty_to_none(cls, v):
        """Convert empty strings to None for optional fields."""
        return None if v == "" else v

class DataAnalyticsManager:
    def __init__(self):
        self.config = Config.from_env()
        self.db_manager = DatabaseManager(self.config.database_url)
        self.backup_manager = BackupManager()
        self.redis_client = None
        self._cache_ttl = 300  # 5 minutes
        
    async def ensure_db_initialized(self):
        """Ensure database connection pool is initialized."""
        if self.db_manager._pool is None:
            await self.db_manager.initialize()

    async def get_redis(self):
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.config.redis_url)
        return self.redis_client

    async def get_analytics_data(self, params: AnalyticsDataRequest) -> Dict[str, Any]:
        """Get paginated analytics data with filtering and sorting."""
        try:
            await self.ensure_db_initialized()
            # Build query with ALL HITL dimensions
            base_query = """
                SELECT 
                    -- GRUPO 1: Identificación y Estado
                    i.id, i.user_id, i.conversation_id, i.message_number,
                    i.customer_status,
                    i.review_status,
                    i.reviewer_id,
                    
                    -- GRUPO 2: Contenido del Mensaje
                    i.user_message, i.user_message_timestamp,
                    i.llm1_raw_response,
                    i.llm2_bubbles,
                    i.final_bubbles,
                    i.messages_sent_at,
                    i.edit_tags,
                    i.quality_score,
                    i.reviewer_notes,
                    
                    -- GRUPO 3: Tracking de Modelos IA
                    i.llm1_model, i.llm2_model,
                    i.llm1_tokens_used, i.llm2_tokens_used,
                    i.llm1_cost_usd, i.llm2_cost_usd,
                    (COALESCE(i.llm1_cost_usd, 0) + COALESCE(i.llm2_cost_usd, 0)) as total_cost_usd,
                    
                    -- GRUPO 4: Análisis de Constitution
                    i.constitution_risk_score,
                    i.constitution_flags,
                    i.constitution_recommendation,
                    
                    -- GRUPO 5: Proceso de Revisión Humana
                    i.review_started_at,
                    i.review_completed_at,
                    i.review_time_seconds,
                    
                    -- GRUPO 6: Estado del Cliente y CTA
                    i.ltv_usd,
                    i.cta_sent_count,
                    i.cta_response_type,
                    i.last_cta_sent_at,
                    i.conversion_date,
                    i.cta_data,
                    
                    -- GRUPO 7: Prioridad y Performance
                    i.priority_score,
                    
                    -- GRUPO 8: Timestamps
                    i.created_at, i.updated_at
                    
                FROM interactions i
                WHERE 1=1
            """
            
            query_params = []
            param_count = 0
            
            # Date filtering
            if params.date_from:
                param_count += 1
                base_query += f" AND i.created_at >= ${param_count}"
                query_params.append(f"{params.date_from} 00:00:00")
                
            if params.date_to:
                param_count += 1
                base_query += f" AND i.created_at <= ${param_count}"
                query_params.append(f"{params.date_to} 23:59:59")
                
            # User filtering
            if params.user_id:
                param_count += 1
                base_query += f" AND i.user_id = ${param_count}"
                query_params.append(params.user_id)
                
            # Customer status filtering
            if params.customer_status:
                param_count += 1
                base_query += f" AND i.customer_status = ${param_count}"
                query_params.append(params.customer_status)
                
            # Search filtering
            if params.search:
                param_count += 1
                base_query += f" AND (i.user_message ILIKE ${param_count} OR i.llm1_raw_response ILIKE ${param_count} OR array_to_string(i.final_bubbles, ' ') ILIKE ${param_count})"
                search_term = f"%{params.search}%"
                query_params.extend([search_term, search_term, search_term])
                param_count += 2
            
            # Count query
            count_query = f"SELECT COUNT(*) FROM ({base_query}) as filtered"
            
            # Add sorting and pagination
            base_query += f" ORDER BY i.{params.sort_by} {params.sort_order.upper()}"
            offset = (params.page - 1) * params.limit
            base_query += f" LIMIT {params.limit} OFFSET {offset}"
            
            # Execute queries
            async with self.db_manager._pool.acquire() as conn:
                # Get total count
                count_result = await conn.fetchrow(count_query, *query_params)
                total_count = count_result['count']
                
                # Get data
                rows = await conn.fetch(base_query, *query_params)
                
            # Format results
            data = []
            for row in rows:
                row_dict = dict(row)
                # Format datetime objects
                if row_dict.get('created_at'):
                    row_dict['created_at'] = row_dict['created_at'].isoformat()
                if row_dict.get('updated_at'):
                    row_dict['updated_at'] = row_dict['updated_at'].isoformat()
                # Parse JSON fields
                if row_dict.get('cta_data'):
                    try:
                        row_dict['cta_data'] = json.loads(row_dict['cta_data']) if isinstance(row_dict['cta_data'], str) else row_dict['cta_data']
                    except:
                        row_dict['cta_data'] = {}
                data.append(row_dict)
            
            return {
                "data": data,
                "pagination": {
                    "page": params.page,
                    "limit": params.limit,
                    "total": total_count,
                    "pages": (total_count + params.limit - 1) // params.limit
                },
                "filters_applied": {
                    "search": params.search,
                    "date_from": params.date_from,
                    "date_to": params.date_to,
                    "user_id": params.user_id
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics data: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def get_analytics_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics for dashboard charts."""
        try:
            await self.ensure_db_initialized()
            # Check cache first
            redis_client = await self.get_redis()
            cache_key = "analytics_metrics"
            cached = await redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
            
            async with self.db_manager._pool.acquire() as conn:
                # Messages per day (last 30 days)
                daily_messages = await conn.fetch("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM interactions 
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """)
                
                # CTA distribution
                cta_distribution = await conn.fetch("""
                    SELECT 
                        CASE 
                            WHEN cta_data->>'type' IS NOT NULL THEN cta_data->>'type'
                            ELSE 'none'
                        END as cta_type,
                        COUNT(*) as count
                    FROM interactions
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY cta_type
                """)
                
                # Quality scores distribution
                quality_scores = await conn.fetch("""
                    SELECT quality_score, COUNT(*) as count
                    FROM interactions
                    WHERE quality_score IS NOT NULL 
                    AND created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY quality_score
                    ORDER BY quality_score
                """)
                
                # Hourly activity heatmap
                hourly_activity = await conn.fetch("""
                    SELECT 
                        EXTRACT(HOUR FROM created_at) as hour,
                        COUNT(*) as count
                    FROM interactions
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY EXTRACT(HOUR FROM created_at)
                    ORDER BY hour
                """)
                
                # Customer conversion funnel
                conversion_funnel = await conn.fetch("""
                    SELECT 
                        i.customer_status as status,
                        COUNT(DISTINCT i.user_id) as user_count,
                        AVG(i.ltv_usd) as avg_ltv
                    FROM interactions i
                    WHERE i.customer_status IS NOT NULL
                    GROUP BY i.customer_status
                """)
                
                # Cost metrics
                cost_metrics = await conn.fetch("""
                    SELECT 
                        DATE(created_at) as date,
                        SUM(COALESCE(llm1_cost_usd, 0) + COALESCE(llm2_cost_usd, 0)) as daily_cost,
                        COUNT(*) as message_count
                    FROM interactions
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """)
            
            # Format data for frontend
            metrics = {
                "daily_messages": [
                    {"date": row['date'].isoformat(), "count": row['count']}
                    for row in daily_messages
                ],
                "cta_distribution": [
                    {"type": row['cta_type'], "count": row['count']}
                    for row in cta_distribution
                ],
                "quality_scores": [
                    {"score": row['quality_score'], "count": row['count']}
                    for row in quality_scores
                ],
                "hourly_activity": [
                    {"hour": int(row['hour']), "count": row['count']}
                    for row in hourly_activity
                ],
                "conversion_funnel": [
                    {
                        "status": row['status'], 
                        "user_count": row['user_count'],
                        "avg_ltv": float(row['avg_ltv']) if row['avg_ltv'] else 0
                    }
                    for row in conversion_funnel
                ],
                "cost_metrics": [
                    {
                        "date": row['date'].isoformat(),
                        "cost": float(row['daily_cost']) if row['daily_cost'] else 0,
                        "messages": row['message_count']
                    }
                    for row in cost_metrics
                ],
                "generated_at": datetime.utcnow().isoformat()
            }
            
            # Cache for 5 minutes
            await redis_client.setex(cache_key, self._cache_ttl, json.dumps(metrics))
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting analytics metrics: {e}")
            raise HTTPException(status_code=500, detail=f"Metrics error: {str(e)}")

    async def create_backup(self, request: BackupRequest) -> Dict[str, Any]:
        """Create a database backup."""
        try:
            backup_name = request.name or f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            backup_result = await self.backup_manager.create_backup(
                name=backup_name,
                include_data=request.include_data,
                compress=request.compress
            )
            
            return {
                "backup_id": backup_result["backup_id"],
                "name": backup_result["name"],
                "size_bytes": backup_result["size_bytes"],
                "created_at": backup_result["created_at"],
                "path": backup_result["path"]
            }
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            raise HTTPException(status_code=500, detail=f"Backup error: {str(e)}")

    async def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        try:
            return await self.backup_manager.list_backups()
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            raise HTTPException(status_code=500, detail=f"Backup listing error: {str(e)}")

    async def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """Restore from a specific backup."""
        try:
            result = await self.backup_manager.restore_backup(backup_id)
            
            # Clear analytics cache after restore
            redis_client = await self.get_redis()
            await redis_client.delete("analytics_metrics")
            
            return result
            
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            raise HTTPException(status_code=500, detail=f"Restore error: {str(e)}")

    async def delete_backup(self, backup_id: str) -> Dict[str, Any]:
        """Delete a specific backup."""
        try:
            result = await self.backup_manager.delete_backup(backup_id)
            return result
            
        except Exception as e:
            logger.error(f"Error deleting backup: {e}")
            raise HTTPException(status_code=500, detail=f"Delete backup error: {str(e)}")

    async def clean_data(self, request: CleanDataRequest) -> Dict[str, Any]:
        """Clean data with specified filters."""
        try:
            if not request.confirm:
                # Return preview of what would be deleted
                preview = await self._preview_cleanup(request)
                return {
                    "preview": True,
                    "records_to_delete": preview["count"],
                    "oldest_record": preview["oldest"],
                    "newest_record": preview["newest"],
                    "warning": "This is a preview. Set confirm=true to execute."
                }
            
            # Execute cleanup
            deleted_count = await self._execute_cleanup(request)
            
            # Clear cache
            redis_client = await self.get_redis()
            await redis_client.delete("analytics_metrics")
            
            return {
                "deleted_count": deleted_count,
                "executed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error cleaning data: {e}")
            raise HTTPException(status_code=500, detail=f"Cleanup error: {str(e)}")

    async def _preview_cleanup(self, request: CleanDataRequest) -> Dict[str, Any]:
        """Preview what would be deleted."""
        query = "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM interactions WHERE 1=1"
        params = []
        param_count = 0
        
        if request.date_from:
            param_count += 1
            query += f" AND created_at >= ${param_count}"
            params.append(f"{request.date_from} 00:00:00")
            
        if request.date_to:
            param_count += 1
            query += f" AND created_at <= ${param_count}"
            params.append(f"{request.date_to} 23:59:59")
            
        if request.user_ids:
            param_count += 1
            query += f" AND user_id = ANY(${param_count})"
            params.append(request.user_ids)
            
        if request.test_data_only:
            query += " AND (user_message ILIKE '%test%' OR array_to_string(final_bubbles, ' ') ILIKE '%test%')"
        
        async with self.db_manager._pool.acquire() as conn:
            result = await conn.fetchrow(query, *params)
            
        return {
            "count": result[0],
            "oldest": result[1].isoformat() if result[1] else None,
            "newest": result[2].isoformat() if result[2] else None
        }

    async def _execute_cleanup(self, request: CleanDataRequest) -> int:
        """Execute the actual cleanup."""
        query = "DELETE FROM interactions WHERE 1=1"
        params = []
        param_count = 0
        
        if request.date_from:
            param_count += 1
            query += f" AND created_at >= ${param_count}"
            params.append(f"{request.date_from} 00:00:00")
            
        if request.date_to:
            param_count += 1
            query += f" AND created_at <= ${param_count}"
            params.append(f"{request.date_to} 23:59:59")
            
        if request.user_ids:
            param_count += 1
            query += f" AND user_id = ANY(${param_count})"
            params.append(request.user_ids)
            
        if request.test_data_only:
            query += " AND (user_message ILIKE '%test%' OR array_to_string(final_bubbles, ' ') ILIKE '%test%')"
        
        async with self.db_manager._pool.acquire() as conn:
            result = await conn.execute(query, *params)
            # Extract number from "DELETE 123" response
            return int(result.split()[-1]) if result.split() else 0

    async def export_data(self, format_type: str, filters: Dict[str, Any]) -> StreamingResponse:
        """Export data in specified format."""
        try:
            if format_type not in ['csv', 'json', 'xlsx']:
                raise HTTPException(status_code=400, detail="Invalid format. Use csv, json, or xlsx")
            
            # Build query with filters
            query = """
                SELECT i.*
                FROM interactions i
                WHERE 1=1
            """
            
            params = []
            param_count = 0
            
            if filters.get('date_from'):
                param_count += 1
                query += f" AND i.created_at >= ${param_count}"
                params.append(datetime.strptime(f"{filters['date_from']} 00:00:00", "%Y-%m-%d %H:%M:%S"))
                
            if filters.get('date_to'):
                param_count += 1
                query += f" AND i.created_at <= ${param_count}"
                params.append(datetime.strptime(f"{filters['date_to']} 23:59:59", "%Y-%m-%d %H:%M:%S"))
            
            query += " ORDER BY i.created_at DESC"
            
            # Ensure database is initialized
            await self.ensure_db_initialized()
            
            async with self.db_manager._pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
            
            # Convert to appropriate format
            if format_type == 'json':
                return await self._export_json(rows)
            elif format_type == 'csv':
                return await self._export_csv(rows)
            elif format_type == 'xlsx':
                return await self._export_xlsx(rows)
                
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")

    async def _export_json(self, rows) -> StreamingResponse:
        """Export as JSON."""
        import io
        
        data = []
        for row in rows:
            row_dict = dict(row)
            # Format datetime objects
            for key, value in row_dict.items():
                if isinstance(value, datetime):
                    row_dict[key] = value.isoformat()
            data.append(row_dict)
        
        json_str = json.dumps(data, indent=2)
        buffer = io.StringIO(json_str)
        
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=nadia_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"}
        )

    async def _export_csv(self, rows) -> StreamingResponse:
        """Export as CSV."""
        import io
        import csv
        
        if not rows:
            raise HTTPException(status_code=404, detail="No data to export")
        
        output = io.StringIO()
        
        # Get all unique fieldnames from all rows
        all_fieldnames = set()
        row_dicts = []
        for row in rows:
            row_dict = dict(row)
            # Format datetime objects
            for key, value in row_dict.items():
                if isinstance(value, datetime):
                    row_dict[key] = value.isoformat()
                elif isinstance(value, list):
                    row_dict[key] = json.dumps(value)
            row_dicts.append(row_dict)
            all_fieldnames.update(row_dict.keys())
        
        # Create writer with all fieldnames
        writer = csv.DictWriter(output, fieldnames=sorted(all_fieldnames))
        writer.writeheader()
        
        # Write rows
        for row_dict in row_dicts:
            writer.writerow(row_dict)
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=nadia_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )

    async def _export_xlsx(self, rows) -> StreamingResponse:
        """Export as Excel file."""
        try:
            import io
            import openpyxl
            from openpyxl.utils.dataframe import dataframe_to_rows
            import pandas as pd
            
            # Convert to DataFrame
            data = []
            for row in rows:
                row_dict = dict(row)
                # Format datetime objects
                for key, value in row_dict.items():
                    if isinstance(value, datetime):
                        row_dict[key] = value.isoformat()
                    elif isinstance(value, list):
                        row_dict[key] = json.dumps(value)
                data.append(row_dict)
            
            df = pd.DataFrame(data)
            
            # Create Excel file
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='NADIA Data', index=False)
            
            buffer.seek(0)
            
            return StreamingResponse(
                iter([buffer.getvalue()]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=nadia_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"}
            )
            
        except ImportError:
            # Fallback to CSV if pandas/openpyxl not available
            logger.warning("pandas/openpyxl not available, falling back to CSV")
            return await self._export_csv(rows)

    async def get_raw_interaction(self, message_id: str) -> Dict[str, Any]:
        """Get raw interaction data directly from PostgreSQL without any transformations."""
        try:
            query = """
                SELECT *
                FROM interactions 
                WHERE id = $1::UUID
            """
            
            async with self.db_manager._pool.acquire() as conn:
                row = await conn.fetchrow(query, message_id)
                
            if not row:
                raise HTTPException(status_code=404, detail=f"Interaction {message_id} not found")
                
            # Convert to dict but keep everything as raw as possible
            raw_data = dict(row)
            
            # Add database schema information for debugging
            schema_info = {
                "_debug_info": {
                    "table": "interactions",
                    "query_executed": query,
                    "parameter": message_id,
                    "total_columns": len(raw_data),
                    "column_names": list(raw_data.keys())
                }
            }
            
            return {**raw_data, **schema_info}
            
        except Exception as e:
            logger.error(f"Error getting raw interaction {message_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def get_data_integrity_report(self) -> Dict[str, Any]:
        """Generate comprehensive data integrity report."""
        try:
            await self.ensure_db_initialized()
            async with self.db_manager._pool.acquire() as conn:
                # 1. SCHEMA CHECK: Get actual database schema
                schema_query = """
                    SELECT column_name, data_type, is_nullable, column_default, 
                           character_maximum_length, numeric_precision, numeric_scale
                    FROM information_schema.columns 
                    WHERE table_name = 'interactions' 
                      AND table_schema = 'public'
                    ORDER BY ordinal_position
                """
                actual_schema = await conn.fetch(schema_query)
                
                # Expected schema from our analytics queries
                expected_fields = {
                    'id': {'type': 'uuid', 'required': True},
                    'user_id': {'type': 'text', 'required': True},
                    'conversation_id': {'type': 'text', 'required': True},
                    'message_number': {'type': 'integer', 'required': True},
                    'customer_status': {'type': 'character varying', 'required': False},
                    'review_status': {'type': 'text', 'required': False},
                    'user_message': {'type': 'text', 'required': True},
                    'llm1_raw_response': {'type': 'text', 'required': False},
                    'final_bubbles': {'type': 'ARRAY', 'required': False},
                    'llm1_model': {'type': 'text', 'required': False},
                    'llm2_model': {'type': 'text', 'required': False},
                    'constitution_risk_score': {'type': 'double precision', 'required': False},
                    'cta_response_type': {'type': 'character varying', 'required': False},
                    'ltv_usd': {'type': 'numeric', 'required': False},
                    'cta_data': {'type': 'jsonb', 'required': False}
                }
                
                # Compare schemas
                actual_fields = {row['column_name']: dict(row) for row in actual_schema}
                schema_check = {
                    'missing_fields': [],
                    'unexpected_fields': [],
                    'type_mismatches': [],
                    'total_expected': len(expected_fields),
                    'total_actual': len(actual_fields)
                }
                
                for field, expected in expected_fields.items():
                    if field not in actual_fields:
                        schema_check['missing_fields'].append({
                            'field': field,
                            'expected_type': expected['type'],
                            'required': expected['required']
                        })
                    elif actual_fields[field]['data_type'] != expected['type']:
                        schema_check['type_mismatches'].append({
                            'field': field,
                            'expected_type': expected['type'],
                            'actual_type': actual_fields[field]['data_type']
                        })
                
                # 2. DATA QUALITY METRICS
                quality_queries = {
                    'total_records': "SELECT COUNT(*) as count FROM interactions",
                    'null_customer_status': "SELECT COUNT(*) as count FROM interactions WHERE customer_status IS NULL",
                    'first_messages': "SELECT COUNT(*) as count FROM interactions WHERE message_number = 1",
                    'approved_without_final': """
                        SELECT COUNT(*) as count FROM interactions 
                        WHERE review_status = 'approved' AND (final_bubbles IS NULL OR array_length(final_bubbles, 1) = 0)
                    """,
                    'missing_llm_models': """
                        SELECT COUNT(*) as count FROM interactions 
                        WHERE (llm1_model IS NULL OR llm2_model IS NULL) AND review_status != 'pending'
                    """,
                    'negative_message_numbers': "SELECT COUNT(*) as count FROM interactions WHERE message_number < 1",
                    'future_timestamps': "SELECT COUNT(*) as count FROM interactions WHERE created_at > NOW()",
                    'missing_user_messages': "SELECT COUNT(*) as count FROM interactions WHERE user_message IS NULL OR user_message = ''",
                    'orphaned_reviews': """
                        SELECT COUNT(*) as count FROM interactions 
                        WHERE review_status = 'reviewing' AND review_started_at < NOW() - INTERVAL '24 hours'
                    """,
                    'invalid_quality_scores': """
                        SELECT COUNT(*) as count FROM interactions 
                        WHERE quality_score IS NOT NULL AND (quality_score < 1 OR quality_score > 5)
                    """
                }
                
                quality_metrics = {}
                for metric_name, query in quality_queries.items():
                    result = await conn.fetchrow(query)
                    quality_metrics[metric_name] = result['count']
                
                # Calculate percentages
                total = quality_metrics['total_records']
                quality_percentages = {}
                if total > 0:
                    quality_percentages = {
                        'null_customer_status_pct': round((quality_metrics['null_customer_status'] / total) * 100, 2),
                        'first_messages_pct': round((quality_metrics['first_messages'] / total) * 100, 2),
                        'approved_without_final_pct': round((quality_metrics['approved_without_final'] / total) * 100, 2),
                        'missing_llm_models_pct': round((quality_metrics['missing_llm_models'] / total) * 100, 2)
                    }
                
                # 3. INTEGRITY ALERTS
                alerts = []
                
                # Schema alerts
                if schema_check['missing_fields']:
                    alerts.append({
                        'type': 'error',
                        'icon': '⚠️',
                        'title': 'Missing Database Fields',
                        'message': f"{len(schema_check['missing_fields'])} expected fields not found in database",
                        'details': schema_check['missing_fields']
                    })
                
                if schema_check['type_mismatches']:
                    alerts.append({
                        'type': 'warning',
                        'icon': '⚠️',
                        'title': 'Data Type Mismatches',
                        'message': f"{len(schema_check['type_mismatches'])} fields have unexpected data types",
                        'details': schema_check['type_mismatches']
                    })
                
                # Data quality alerts
                if quality_percentages.get('null_customer_status_pct', 0) > 50:
                    alerts.append({
                        'type': 'warning',
                        'icon': '⚠️',
                        'title': 'High NULL Customer Status',
                        'message': f"{quality_percentages['null_customer_status_pct']}% of records missing customer_status",
                        'recommendation': 'Run customer status migration or update existing records'
                    })
                
                if quality_metrics['approved_without_final'] > 0:
                    alerts.append({
                        'type': 'error',
                        'icon': '🚨',
                        'title': 'Approved Records Missing Final Bubbles',
                        'message': f"{quality_metrics['approved_without_final']} approved records have no final_bubbles",
                        'recommendation': 'These records were approved but never processed correctly'
                    })
                
                if quality_metrics['orphaned_reviews'] > 0:
                    alerts.append({
                        'type': 'warning',
                        'icon': '⏰',
                        'title': 'Stale Reviews',
                        'message': f"{quality_metrics['orphaned_reviews']} reviews stuck in 'reviewing' state for >24h",
                        'recommendation': 'Reset these reviews to pending status'
                    })
                
                # Success alerts
                if not alerts:
                    alerts.append({
                        'type': 'success',
                        'icon': '✅',
                        'title': 'Data Integrity Excellent',
                        'message': 'All schema and data quality checks passed',
                        'recommendation': 'Continue monitoring regularly'
                    })
                
                # 4. TRANSFORMATIONS CHECK
                transformations_applied = [
                    {
                        'field': 'created_at',
                        'transformation': 'datetime → ISO string',
                        'location': 'data_analytics.py:170-173',
                        'safe': True
                    },
                    {
                        'field': 'cta_data',
                        'transformation': 'JSON string → parsed object',
                        'location': 'data_analytics.py:175-180',
                        'safe': True
                    }
                ]
                
                return {
                    'timestamp': datetime.now().isoformat(),
                    'schema_check': schema_check,
                    'data_quality': {
                        'metrics': quality_metrics,
                        'percentages': quality_percentages
                    },
                    'alerts': alerts,
                    'transformations': transformations_applied,
                    'summary': {
                        'total_alerts': len(alerts),
                        'critical_issues': len([a for a in alerts if a['type'] == 'error']),
                        'warnings': len([a for a in alerts if a['type'] == 'warning']),
                        'schema_health': 'Good' if not schema_check['missing_fields'] else 'Issues Found',
                        'data_health': 'Good' if quality_metrics['approved_without_final'] == 0 else 'Issues Found'
                    }
                }
                
        except Exception as e:
            logger.error(f"Error generating integrity report: {e}")
            raise HTTPException(status_code=500, detail=f"Integrity check failed: {str(e)}")

# Global instance
analytics_manager = DataAnalyticsManager()