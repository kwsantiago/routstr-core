# proxy

a reverse proxy that you can plug in front of any openai compatible api endpoint
to handle payments using the cashu protocol (Bitcoin L3)

## Database Migrations

Alembic is used to manage the database schema for the `ApiKey` model defined in
`router/db.py`. Before running the application for the first time or after
pulling updates, apply the migrations with:

```bash
alembic upgrade head
```

The configuration reads the `DATABASE_URL` environment variable to determine the
database connection.
