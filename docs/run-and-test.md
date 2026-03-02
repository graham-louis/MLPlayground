Run & Test — Quick Commands
===========================

Full-stack (Docker recommended)
------------------------------
Create a `.env` with required secrets (example):

```sh
echo "NASS_API_KEY=your_key_here" >> .env
echo "NOAA_CDO_TOKEN=your_noaa_token" >> .env
```

Then start the stack:

```sh
docker compose up --build
```

Service URLs (local compose):

- Frontend: http://localhost
- API: http://localhost:8000/api/v1
- Swagger: http://localhost:8000/docs
- Adminer (DB UI): http://localhost:8080

Backend (local development)
---------------------------
Install and run locally:

```sh
cd backend
pip install -e .
fastapi dev app/main.py
```

Run backend tests:

```sh
cd backend
pytest
```

Frontend (local development)
----------------------------

```sh
cd frontend
npm install
npm run dev    # open http://localhost:5173
```

Frontend tests & lint
---------------------

```sh
cd frontend
npm test        # vitest run
npm run lint    # biome check src
```

Notes
-----
- If Postgres is required locally, either use the docker compose DB service or set `POSTGRES_*` env vars in `.env`.
- After adding new frontend routes, run a build once (`npm run build`) to regenerate `routeTree.gen.ts`.
