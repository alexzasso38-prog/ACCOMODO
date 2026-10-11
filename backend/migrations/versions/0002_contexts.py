"""Waitlist, billing and conversation schemas with the same tenant barriers."""
from alembic import op
from migrations.schema_0002 import Base
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None
NAMES={'waitlist_entries','deposit_policies','billing_plans','subscriptions','billing_documents','billing_lines','conversations','conversation_messages','provider_cost_rules'}
def upgrade():
    for table in Base.metadata.sorted_tables:
        if table.name not in NAMES: continue
        table.create(op.get_bind())
        if 'tenant_id' in table.c:
            op.execute(f'ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE {table.name} FORCE ROW LEVEL SECURITY')
            op.execute(f"CREATE POLICY tenant_isolation ON {table.name} USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)")
        op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON {table.name} TO tavolo_app')
    op.execute('REVOKE INSERT, UPDATE, DELETE ON billing_plans, provider_cost_rules FROM tavolo_app')
def downgrade(): raise RuntimeError('Rollback distruttivo disabilitato.')
