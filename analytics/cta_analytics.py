# analytics/cta_analytics.py
"""Analytics for CTA performance and usage - English version."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CTAAnalytics:
    """Analiza performance de CTAs insertados manualmente."""

    @staticmethod
    async def get_cta_metrics(db_conn) -> Dict[str, Any]:
        """Get comprehensive CTA metrics."""

        # Basic CTA insertion stats
        basic_stats = await db_conn.fetch("""
            SELECT
                cta_data->>'type' as cta_type,
                COUNT(*) as total_inserted,
                AVG(quality_score) as avg_quality_score,
                COUNT(CASE WHEN quality_score >= 4 THEN 1 END) as high_quality_count
            FROM interactions
            WHERE cta_data IS NOT NULL
            GROUP BY cta_data->>'type'
            ORDER BY total_inserted DESC
        """)

        # CTA insertion by time period
        weekly_stats = await db_conn.fetch("""
            SELECT
                DATE_TRUNC('week', created_at) as week,
                cta_data->>'type' as cta_type,
                COUNT(*) as insertions
            FROM interactions
            WHERE cta_data IS NOT NULL
              AND created_at >= NOW() - INTERVAL '4 weeks'
            GROUP BY 1, 2
            ORDER BY 1 DESC, 3 DESC
        """)

        # Review time impact
        review_time_impact = await db_conn.fetch("""
            SELECT
                CASE
                    WHEN cta_data IS NOT NULL THEN 'with_cta'
                    ELSE 'without_cta'
                END as has_cta,
                AVG(review_time_seconds) as avg_review_time,
                COUNT(*) as count
            FROM interactions
            WHERE review_status = 'approved'
              AND review_time_seconds IS NOT NULL
            GROUP BY 1
        """)

        return {
            "basic_stats": [dict(row) for row in basic_stats],
            "weekly_trends": [dict(row) for row in weekly_stats],
            "review_time_impact": [dict(row) for row in review_time_impact],
            "generated_at": datetime.now().isoformat()
        }

    @staticmethod
    async def get_cta_templates_usage(db_conn) -> List[Dict[str, Any]]:
        """Analyze which CTA templates are used most frequently."""

        # This would require storing the actual CTA text used
        # For now, return type-based usage
        usage_stats = await db_conn.fetch("""
            SELECT
                cta_data->>'type' as cta_type,
                final_bubbles,
                COUNT(*) as usage_count,
                quality_score,
                created_at
            FROM interactions
            WHERE cta_data IS NOT NULL
              AND final_bubbles IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 50
        """)

        return [dict(row) for row in usage_stats]

    @staticmethod
    async def get_cta_quality_analysis(db_conn) -> Dict[str, Any]:
        """Analyze quality scores for messages with CTAs vs without."""

        comparison = await db_conn.fetch("""
            SELECT
                CASE
                    WHEN cta_data IS NOT NULL THEN 'with_cta'
                    ELSE 'without_cta'
                END as category,
                AVG(quality_score) as avg_quality,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY quality_score) as median_quality,
                MIN(quality_score) as min_quality,
                MAX(quality_score) as max_quality,
                COUNT(*) as total_interactions
            FROM interactions
            WHERE quality_score IS NOT NULL
              AND review_status = 'approved'
            GROUP BY 1
        """)

        # Quality distribution by CTA type
        cta_quality_dist = await db_conn.fetch("""
            SELECT
                cta_data->>'type' as cta_type,
                quality_score,
                COUNT(*) as count
            FROM interactions
            WHERE cta_data IS NOT NULL
              AND quality_score IS NOT NULL
            GROUP BY 1, 2
            ORDER BY 1, 2
        """)

        return {
            "quality_comparison": [dict(row) for row in comparison],
            "cta_quality_distribution": [dict(row) for row in cta_quality_dist]
        }

    @staticmethod
    async def export_cta_training_data(db_conn, output_format: str = "json") -> List[Dict[str, Any]]:
        """Export CTA data for training purposes."""

        training_data = await db_conn.fetch("""
            SELECT
                id,
                user_id,
                user_message,
                llm1_raw_response,
                llm2_bubbles,
                final_bubbles,
                edit_tags,
                quality_score,
                cta_data,
                constitution_risk_score,
                constitution_flags,
                created_at,
                review_time_seconds
            FROM interactions
            WHERE cta_data IS NOT NULL
              AND review_status = 'approved'
            ORDER BY created_at DESC
        """)

        formatted_data = []
        for row in training_data:
            row_dict = dict(row)
            # Parse JSON fields
            if row_dict.get('cta_data'):
                import json
                row_dict['cta_data'] = json.loads(row_dict['cta_data'])

            formatted_data.append(row_dict)

        return formatted_data

    @staticmethod
    def calculate_cta_effectiveness_score(
        quality_score: int,
        review_time: Optional[float],
        edit_tags: List[str]
    ) -> float:
        """Calculate a composite effectiveness score for CTA insertions."""

        # Base score from quality (1-5 scale -> 0-1 scale)
        quality_component = (quality_score - 1) / 4

        # Time efficiency component (faster reviews are better)
        time_component = 0.5  # Default neutral
        if review_time:
            # Normalize review time (assuming 60s average, penalty for >120s)
            time_component = max(0, min(1, 1 - (review_time - 30) / 120))

        # Edit complexity penalty (more edits = more work = lower efficiency)
        edit_penalty = min(0.3, len([tag for tag in edit_tags if not tag.startswith('CTA_')]) * 0.05)

        # Weighted combination
        effectiveness = (
            quality_component * 0.6 +  # Quality is most important
            time_component * 0.3 +     # Efficiency matters
            (1 - edit_penalty) * 0.1   # Simplicity bonus
        )

        return round(effectiveness, 3)
