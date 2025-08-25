# Database Guide

This guide covers database design, migrations, and best practices for Routstr Core.

## Database Overview

Routstr uses:
- **SQLite** for local development and single-node deployments
- **PostgreSQL** (optional) for production scale
- **SQLModel** for ORM with type safety
- **Alembic** for schema migrations
- **Async SQLAlchemy** for non-blocking I/O

## Schema Design

### Core Tables

#### APIKey Table

```python
class APIKey(SQLModel, table=True):
    """API key with balance tracking"""
    
    # Primary key
    id: int | None = Field(default=None, primary_key=True)
    
    # Key data (indexed for fast lookups)
    key_hash: str = Field(index=True, unique=True)
    
    # Balance in millisatoshis (1 sat = 1000 msats)
    balance: int = Field(default=0)
    total_deposited: int = Field(default=0)
    total_spent: int = Field(default=0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    
    # Metadata (JSON field)
    metadata: dict = Field(
        default_factory=dict, 
        sa_column=Column(JSON)
    )
    
    # Relationships
    transactions: list["Transaction"] = Relationship(back_populates="api_key")
```

#### Transaction Table

```python
class Transaction(SQLModel, table=True):
    """Transaction log for audit trail"""
    
    # Primary key
    id: int | None = Field(default=None, primary_key=True)
    
    # Foreign key to API key
    api_key_id: int = Field(foreign_key="apikey.id", index=True)
    
    # Transaction details
    amount: int  # Can be negative for deductions
    balance_after: int  # Balance snapshot
    type: TransactionType  # Enum: deposit, usage, withdrawal
    description: str
    
    # Timestamp (indexed for range queries)
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        index=True
    )
    
    # Request details (optional)
    request_data: dict | None = Field(
        default=None,
        sa_column=Column(JSON)
    )
    
    # Relationships
    api_key: APIKey = Relationship(back_populates="transactions")
```

#### Withdrawal Table

```python
class Withdrawal(SQLModel, table=True):
    """Track withdrawal requests"""
    
    id: int | None = Field(default=None, primary_key=True)
    api_key_id: int = Field(foreign_key="apikey.id")
    
    # Withdrawal details
    amount: int
    token: str  # Encrypted eCash token
    mint_url: str
    
    # Status tracking
    status: WithdrawalStatus  # pending, completed, failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    
    # Error handling
    error_message: str | None = None
    retry_count: int = Field(default=0)
```

### Indexes

Critical indexes for performance:

```python
# In models
key_hash: str = Field(index=True, unique=True)  # Fast key lookup
timestamp: datetime = Field(index=True)  # Range queries

# Composite indexes (in migrations)
Index('idx_transactions_key_time', 'api_key_id', 'timestamp')
Index('idx_apikey_expires', 'expires_at').where(expires_at.isnot(None))
```

## Migrations

### Creating Migrations

#### Auto-generate from Model Changes

```bash
# After modifying SQLModel classes
make db-migrate

# Enter descriptive message
> Add withdrawal status field
```

#### Manual Migration

```bash
# Create empty migration
alembic revision -m "custom migration"

# Edit the generated file
```

#### Migration Template

```python
"""Add withdrawal status field

Revision ID: abc123
Revises: def456
Create Date: 2024-01-01 12:00:00

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers
revision = 'abc123'
down_revision = 'def456'

def upgrade() -> None:
    """Apply migration"""
    op.add_column(
        'withdrawal',
        sa.Column(
            'status',
            sa.String(),
            nullable=False,
            server_default='pending'
        )
    )
    
    # Add index
    op.create_index(
        'idx_withdrawal_status',
        'withdrawal',
        ['status']
    )

def downgrade() -> None:
    """Revert migration"""
    op.drop_index('idx_withdrawal_status', 'withdrawal')
    op.drop_column('withdrawal', 'status')
```

### Running Migrations

#### Development

```bash
# Apply all migrations
make db-upgrade

# Check current version
make db-current

# Rollback one version
make db-downgrade

# View history
make db-history
```

#### Production

Migrations run automatically on startup:

```python
# In routstr/core/main.py
def run_migrations():
    """Run database migrations on startup"""
    from alembic import command
    from alembic.config import Config
    
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
```

### Migration Best Practices

1. **Always Review Generated Migrations**
   - Check for data loss
   - Verify index creation
   - Test rollback

2. **Handle Data Migrations**
   ```python
   def upgrade():
       # Schema change
       op.add_column('apikey', sa.Column('status', sa.String()))
       
       # Data migration
       connection = op.get_bind()
       connection.execute(
           "UPDATE apikey SET status = 'active' WHERE expires_at IS NULL"
       )
   ```

3. **Make Migrations Idempotent**
   ```python
   def upgrade():
       # Check if column exists
       inspector = sa.inspect(op.get_bind())
       columns = [col['name'] for col in inspector.get_columns('apikey')]
       
       if 'new_field' not in columns:
           op.add_column('apikey', sa.Column('new_field', sa.String()))
   ```

## Database Operations

### Connection Management

```python
# Database session factory
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependency injection
async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

### Query Patterns

#### Basic Queries

```python
# Get by primary key
api_key = await session.get(APIKey, key_id)

# Get by unique field
result = await session.execute(
    select(APIKey).where(APIKey.key_hash == hash_value)
)
api_key = result.scalar_one_or_none()

# Get multiple with filter
result = await session.execute(
    select(APIKey)
    .where(APIKey.balance > 0)
    .where(APIKey.expires_at > datetime.utcnow())
)
active_keys = result.scalars().all()
```

#### Joins and Relationships

```python
# Eager loading
result = await session.execute(
    select(APIKey)
    .options(selectinload(APIKey.transactions))
    .where(APIKey.id == key_id)
)
api_key = result.scalar_one()

# Join query
result = await session.execute(
    select(Transaction)
    .join(APIKey)
    .where(APIKey.key_hash == hash_value)
    .order_by(Transaction.timestamp.desc())
    .limit(10)
)
recent_transactions = result.scalars().all()
```

#### Aggregations

```python
# Sum total spent
result = await session.execute(
    select(func.sum(Transaction.amount))
    .where(Transaction.api_key_id == key_id)
    .where(Transaction.type == TransactionType.USAGE)
)
total_spent = result.scalar() or 0

# Count active keys
result = await session.execute(
    select(func.count(APIKey.id))
    .where(APIKey.balance > 0)
)
active_count = result.scalar()
```

### Transactions

#### Atomic Operations

```python
async def transfer_balance(
    session: AsyncSession,
    from_key: int,
    to_key: int,
    amount: int
):
    """Atomic balance transfer"""
    async with session.begin():
        # Lock rows to prevent race conditions
        from_api_key = await session.execute(
            select(APIKey)
            .where(APIKey.id == from_key)
            .with_for_update()
        )
        from_api_key = from_api_key.scalar_one()
        
        to_api_key = await session.execute(
            select(APIKey)
            .where(APIKey.id == to_key)
            .with_for_update()
        )
        to_api_key = to_api_key.scalar_one()
        
        # Check balance
        if from_api_key.balance < amount:
            raise InsufficientBalanceError()
        
        # Update balances
        from_api_key.balance -= amount
        to_api_key.balance += amount
        
        # Log transactions
        session.add(Transaction(
            api_key_id=from_key,
            amount=-amount,
            balance_after=from_api_key.balance,
            type=TransactionType.TRANSFER_OUT
        ))
        
        session.add(Transaction(
            api_key_id=to_key,
            amount=amount,
            balance_after=to_api_key.balance,
            type=TransactionType.TRANSFER_IN
        ))
        
        # Commit happens automatically
```

#### Optimistic Locking

```python
class APIKey(SQLModel, table=True):
    # Add version field
    version: int = Field(default=1)

async def update_with_version_check(
    session: AsyncSession,
    api_key: APIKey,
    new_balance: int
):
    """Update with optimistic locking"""
    result = await session.execute(
        update(APIKey)
        .where(APIKey.id == api_key.id)
        .where(APIKey.version == api_key.version)
        .values(
            balance=new_balance,
            version=APIKey.version + 1
        )
    )
    
    if result.rowcount == 0:
        raise ConcurrentModificationError()
```

## Performance Optimization

### Query Optimization

1. **Use Indexes Effectively**
   ```python
   # Good: Uses index
   where(APIKey.key_hash == value)
   
   # Bad: Function prevents index use
   where(func.lower(APIKey.key_hash) == value.lower())
   ```

2. **Limit Results**
   ```python
   # Always limit when possible
   query.limit(100)
   
   # Use pagination
   query.offset(page * page_size).limit(page_size)
   ```

3. **Select Only Needed Columns**
   ```python
   # Select specific columns
   result = await session.execute(
       select(APIKey.id, APIKey.balance)
       .where(APIKey.key_hash == hash_value)
   )
   ```

### Connection Pooling

```python
# Configure connection pool
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,          # Number of connections
    max_overflow=10,       # Extra connections when needed
    pool_timeout=30,       # Wait time for connection
    pool_recycle=3600,     # Recycle connections after 1 hour
    pool_pre_ping=True,    # Check connection health
)
```

### Batch Operations

```python
# Batch insert
async def bulk_create_transactions(
    session: AsyncSession,
    transactions: list[dict]
):
    """Efficient bulk insert"""
    await session.execute(
        insert(Transaction),
        transactions
    )
    await session.commit()

# Batch update
await session.execute(
    update(APIKey)
    .where(APIKey.expires_at < datetime.utcnow())
    .values(active=False)
)
```

## Testing Database Code

### Test Database Setup

```python
@pytest.fixture
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=True  # Log SQL for debugging
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    yield engine
    
    await engine.dispose()
```

### Testing Queries

```python
async def test_balance_update(test_session):
    """Test atomic balance update"""
    # Create test data
    api_key = APIKey(key_hash="test", balance=1000)
    test_session.add(api_key)
    await test_session.commit()
    
    # Test update
    await deduct_balance(test_session, api_key.id, 100)
    
    # Verify
    await test_session.refresh(api_key)
    assert api_key.balance == 900
    
    # Verify transaction log
    result = await test_session.execute(
        select(Transaction)
        .where(Transaction.api_key_id == api_key.id)
    )
    transactions = result.scalars().all()
    assert len(transactions) == 1
    assert transactions[0].amount == -100
```

### Testing Migrations

```python
def test_migration_upgrade():
    """Test migration applies correctly"""
    # Create database at previous version
    alembic_cfg = Config("alembic.ini")
    command.downgrade(alembic_cfg, "-1")
    
    # Apply migration
    command.upgrade(alembic_cfg, "+1")
    
    # Verify schema changes
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('apikey')]
    assert 'new_column' in columns
```

## Database Maintenance

### Monitoring Queries

```sql
-- Slow queries (SQLite)
EXPLAIN QUERY PLAN
SELECT * FROM apikey WHERE balance > 0;

-- Table sizes
SELECT 
    name,
    COUNT(*) as row_count
FROM sqlite_master
WHERE type='table'
GROUP BY name;

-- Index usage
SELECT * FROM sqlite_stat1;
```

### Cleanup Tasks

```python
async def cleanup_expired_keys(session: AsyncSession):
    """Remove expired API keys"""
    result = await session.execute(
        delete(APIKey)
        .where(APIKey.expires_at < datetime.utcnow())
        .where(APIKey.balance == 0)
    )
    
    logger.info(f"Cleaned up {result.rowcount} expired keys")
    await session.commit()

async def vacuum_database(session: AsyncSession):
    """Optimize database file size (SQLite)"""
    await session.execute(text("VACUUM"))
```

### Backup Strategies

```python
async def backup_database(source_url: str, backup_path: str):
    """Create database backup"""
    if "sqlite" in source_url:
        # SQLite backup
        import shutil
        db_path = source_url.split("///")[1]
        shutil.copy2(db_path, backup_path)
    else:
        # PostgreSQL backup
        import subprocess
        subprocess.run([
            "pg_dump",
            source_url,
            "-f", backup_path
        ])
```

## PostgreSQL Migration

### Configuration

```python
# PostgreSQL connection
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/routstr"

# Additional PostgreSQL-specific settings
engine = create_async_engine(
    DATABASE_URL,
    server_settings={
        "jit": "off",
        "statement_timeout": "30s"
    }
)
```

### PostgreSQL-Specific Features

```python
# Use PostgreSQL arrays
from sqlalchemy.dialects.postgresql import ARRAY

class APIKey(SQLModel, table=True):
    allowed_models: list[str] = Field(
        default_factory=list,
        sa_column=Column(ARRAY(String))
    )

# Use JSONB for better performance
metadata: dict = Field(
    default_factory=dict,
    sa_column=Column(JSONB)
)

# Full-text search
from sqlalchemy.dialects.postgresql import TSVECTOR

search_vector = Column(TSVECTOR)
```

## Security Considerations

### SQL Injection Prevention

```python
# Always use parameterized queries
# Good
await session.execute(
    select(APIKey).where(APIKey.key_hash == key_hash)
)

# Bad - SQL injection risk
await session.execute(
    text(f"SELECT * FROM apikey WHERE key_hash = '{key_hash}'")
)
```

### Data Encryption

```python
from cryptography.fernet import Fernet

class EncryptedField(TypeDecorator):
    """Encrypt sensitive data at rest"""
    impl = String
    
    def __init__(self, key: bytes, *args, **kwargs):
        self.cipher = Fernet(key)
        super().__init__(*args, **kwargs)
    
    def process_bind_param(self, value, dialect):
        if value is not None:
            return self.cipher.encrypt(value.encode()).decode()
        return value
    
    def process_result_value(self, value, dialect):
        if value is not None:
            return self.cipher.decrypt(value.encode()).decode()
        return value
```

## Next Steps

- Review [Testing Guide](testing.md) for database testing
- Check [Guidelines](guidelines.md) for code standards
- See [Architecture](architecture.md) for system design
- Read [Setup Guide](setup.md) for development setup