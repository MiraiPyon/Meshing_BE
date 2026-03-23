# Meshing_BE

## Quick start (1 minute)

```sh
make install
make bootstrap-env
make hooks
make up
make run
```

API health endpoints:

- `GET /api/v1/health`
- `GET /api/v1/health/db`

## Local setup

1. Create local environment file:

```sh
./scripts/bootstrap-env.sh
```

2. Update values in `docker/.env` with your local secrets.

3. Start database and tools:

```sh
docker compose --env-file docker/.env -f docker/docker-compose.yml up -d
```

## Developer commands

```sh
make test      # Run test suite
make lint      # Ruff lint checks
make format    # Black formatter
make check     # Lint + tests
make secret-scan # Scan staged changes for secrets
make ci        # Secret scan + lint + tests
make up        # Start compose services
make down      # Stop compose services
```

## Git secret guard

This repository uses a local git pre-commit hook to block accidental secret commits.

### Enable hooks

```sh
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit scripts/precommit-secret-scan.sh scripts/bootstrap-env.sh
```

### What is blocked

- Committing `docker/.env`
- Staged lines that look like real secrets (`SECRET=`, `PASSWORD=`, `API_KEY=`, `TOKEN=`, etc.)

If needed, replace values with placeholders in tracked files and keep real values only in untracked env files.
