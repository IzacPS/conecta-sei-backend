# Database Setup - PostgreSQL + ParadeDB

## 🚀 Quick Start

### 1. Start PostgreSQL + ParadeDB

```bash
# Start only PostgreSQL
docker-compose up -d postgres

# Start PostgreSQL + pgAdmin (database management UI)
docker-compose --profile tools up -d
```

### 2. Verify Connection

```bash
# Check if PostgreSQL is running
docker-compose ps

# Connect via psql
docker-compose exec postgres psql -U automasei -d automasei

# Inside psql:
\dt  # List tables
\q   # Quit
```

### 3. Access pgAdmin (Optional)

- URL: http://localhost:5050
- Email: `admin@automasei.local`
- Password: `admin`

**Add Server in pgAdmin**:
- Host: `postgres` (container name)
- Port: `5432`
- Database: `automasei`
- User: `automasei`
- Password: `automasei_dev_password`

---

## 📊 Database Configuration

### Connection String

```python
# For SQLAlchemy
DATABASE_URL = "postgresql://automasei:automasei_dev_password@localhost:5432/automasei"

# For asyncpg
DATABASE_URL = "postgresql+asyncpg://automasei:automasei_dev_password@localhost:5432/automasei"
```

### Environment Variables

```bash
# .env file
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=automasei
POSTGRES_USER=automasei
POSTGRES_PASSWORD=automasei_dev_password
```

---

## 🔧 ParadeDB Features

ParadeDB extends PostgreSQL with:

1. **Full-Text Search** (Elasticsearch-like)
2. **Vector Search** (for embeddings)
3. **JSON Support** (native PostgreSQL JSONB)
4. **Hybrid Search** (combine text + vector)

### Example: Full-Text Search

```sql
-- Create search index
CREATE INDEX idx_process_search ON processes
USING paradedb.bm25(numero_processo, autoridade);

-- Search
SELECT * FROM processes
WHERE numero_processo @@@ 'search term';
```

### Example: JSON Columns

```sql
-- Store flexible data in JSONB
CREATE TABLE institutions (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    metadata JSONB DEFAULT '{}'
);

-- Query JSON
SELECT * FROM institutions
WHERE metadata->>'region' = 'São Paulo';
```

---

## 🗄️ Migration with Alembic

### Initialize Alembic

```bash
# Install dependencies
pip install alembic sqlalchemy psycopg2-binary

# Initialize Alembic
alembic init alembic

# Edit alembic.ini
# sqlalchemy.url = postgresql://automasei:automasei_dev_password@localhost:5432/automasei
```

### Create Migration

```bash
# Auto-generate migration from models
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🧹 Maintenance

### Stop Services

```bash
# Stop all
docker-compose down

# Stop and remove volumes (DELETE DATA)
docker-compose down -v
```

### View Logs

```bash
# PostgreSQL logs
docker-compose logs -f postgres

# All services
docker-compose logs -f
```

### Backup Database

```bash
# Dump database
docker-compose exec postgres pg_dump -U automasei automasei > backup.sql

# Restore database
docker-compose exec -T postgres psql -U automasei automasei < backup.sql
```

---

## 🚨 Important Notes

### Production MongoDB

⚠️ **DO NOT connect to production MongoDB from this project!**

- Production MongoDB is **OFF-LIMITS**
- Only reference its schema for model design
- All development uses local PostgreSQL

### Data Migration (Future)

When migrating data from MongoDB → PostgreSQL:
1. Create export script (read-only MongoDB connection)
2. Transform data to SQL format
3. Import into PostgreSQL
4. Validate data integrity
5. Switch application to PostgreSQL

---

## 📚 Resources

- **ParadeDB Docs**: https://docs.paradedb.com
- **PostgreSQL Docs**: https://www.postgresql.org/docs
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org
- **Alembic Docs**: https://alembic.sqlalchemy.org
