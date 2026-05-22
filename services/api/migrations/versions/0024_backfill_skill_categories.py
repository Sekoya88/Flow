"""Backfill skill categories from name patterns.

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-22
"""

from alembic import op

revision: str = "0024"
down_revision: str = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE agent_skills SET category = CASE
          WHEN name ILIKE '%research%' OR name ILIKE '%academic%'
               OR name ILIKE '%source-eval%' OR name ILIKE '%web-search%' THEN 'Research'
          WHEN name ILIKE '%code%' OR name ILIKE '%debug%' OR name ILIKE '%json%'
               OR name ILIKE '%schema%' OR name ILIKE '%refactor%'
               OR name ILIKE '%explanation%' OR name ILIKE '%programming%' THEN 'Code'
          WHEN name ILIKE '%email%' OR name ILIKE '%meeting%' OR name ILIKE '%slack%'
               OR name ILIKE '%prompt%' OR name ILIKE '%writing%'
               OR name ILIKE '%creative%' OR name ILIKE '%ideation%' THEN 'Communication'
          WHEN name ILIKE '%cluster%' OR name ILIKE '%sentiment%' OR name ILIKE '%summar%'
               OR name ILIKE '%analys%' OR name ILIKE '%semantic%'
               OR name ILIKE '%classif%' OR name ILIKE '%similarity%'
               OR name ILIKE '%text-%' THEN 'Analysis'
          WHEN name ILIKE '%memory%' OR name ILIKE '%fact%' OR name ILIKE '%pattern%'
               OR name ILIKE '%preference%' OR name ILIKE '%context%'
               OR name ILIKE '%interpret%' OR name ILIKE '%learning%' THEN 'Memory'
          WHEN name ILIKE '%plan%' OR name ILIKE '%task%' OR name ILIKE '%goal%'
               OR name ILIKE '%timeline%' OR name ILIKE '%decompos%'
               OR name ILIKE '%project%' OR name ILIKE '%roadmap%' THEN 'Planning'
          ELSE category
        END
        WHERE category = 'General'
        """
    )


def downgrade() -> None:
    pass
