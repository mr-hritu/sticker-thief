1. set the current head: alembic stamp <revision>
2. create a new revision: alembic revision -m "added type column to pack table"
3. upgreade the migration script
4. upgrade: alembic upgrade head
