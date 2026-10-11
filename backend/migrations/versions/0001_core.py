"""Initial demo schema with composite foreign keys, exclusion and forced RLS."""
from alembic import op
from migrations.schema_0001 import Base
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS btree_gist')
    Base.metadata.create_all(op.get_bind())
    op.execute("ALTER TABLE allocations ADD CONSTRAINT no_resource_overlap EXCLUDE USING gist (tenant_id WITH =, resource_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) WHERE (active)")
    op.execute('CREATE INDEX ix_reservations_venue_start ON reservations (tenant_id, venue_id, starts_at)')
    op.execute('CREATE INDEX ix_outbox_due ON outbox_events (tenant_id, status, available_at)')
    for table in Base.metadata.sorted_tables:
        if 'tenant_id' in table.c and table.name not in ('memberships','venue_routes'):
            op.execute(f'ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE {table.name} FORCE ROW LEVEL SECURITY')
            op.execute(f"CREATE POLICY tenant_isolation ON {table.name} USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)")
    op.execute('ALTER TABLE tenants ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE tenants FORCE ROW LEVEL SECURITY')
    op.execute("CREATE POLICY tenant_isolation ON tenants USING (id = nullif(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (id = nullif(current_setting('app.tenant_id', true), '')::uuid)")
    op.execute('GRANT USAGE ON SCHEMA public TO tavolo_app')
    op.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tavolo_app')
    # App cannot create routing or identity assignments, and cannot mutate schema.
    op.execute('REVOKE INSERT, UPDATE, DELETE ON tenants, venue_routes, users, memberships FROM tavolo_app')
    op.execute('REVOKE ALL ON alembic_version FROM tavolo_app')

def downgrade():
    raise RuntimeError('Rollback distruttivo disabilitato: utilizzare restore verificato.')
