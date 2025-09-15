# Shared Notes API

API REST per la gestione e condivisione di note tra utenti. L'applicazione è costruita con FastAPI e utilizza PostgreSQL come database principale e Redis per le sessioni.

## Caratteristiche Principali

- **Autenticazione JWT**: Sistema di autenticazione sicuro con access token e refresh token
- **Gestione Note**: Creazione, modifica, eliminazione e condivisione di note
- **Sistema Tag**: Organizzazione delle note tramite etichette
- **Condivisione**: Condivisione di note tra utenti con accesso in sola lettura
- **Ricerca**: Ricerca full-text nelle note e filtri per tag
- **API REST**: API ben documentata con OpenAPI/Swagger
- **Containerizzazione**: Deploy con Docker e Docker Compose

## Stack Tecnologico

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (persistenza principale)
- **Cache**: Redis (sessioni e cache)
- **ORM**: SQLAlchemy con supporto asincrono
- **Autenticazione**: JWT (JSON Web Tokens)
- **Migrazioni**: Alembic
- **Containerizzazione**: Docker

### Produzione - CloudFront (AWS)

- **API Endpoint**: https://d2w8ulo83u5tax.cloudfront.net/api/v1
- **Documentazione API Swagger**: https://d2w8ulo83u5tax.cloudfront.net/docs
- **Documentazione ReDoc**: https://d2w8ulo83u5tax.cloudfront.net/redoc
- **openapi.json**: https://d2w8ulo83u5tax.cloudfront.net/openapi.json

## Installazione e Setup

### Prerequisiti

- Docker e Docker Compose
- Python 3.11+ (per sviluppo locale)

### Setup con Docker

1. **Clona il repository**:
```bash
git clone git@github.com:rabbagliettiandrea/shared-notes-api.git
cd shared-notes-api
```

2. **Avvia i servizi**:
```bash
docker compose -f docker-compose.dev.yml up -d
```

3. **Attendi che tutti i servizi siano disponibili**
```bash
docker compose -f docker-compose.dev.yml ps
```

4. **Esegui le migrazioni sul DB**:
```bash
docker compose -f docker-compose.dev.yml exec api alembic upgrade head
```

5. **Verifica l'installazione**:
```bash
curl http://localhost:8000/health
```

## Utilizzo

### Avvio dell'Applicazione

L'API sarà disponibile su `http://localhost:8000`

## Testing

### Test con Postman

È disponibile una collection Postman completa in `docs/postman/` che include:
- Utenti di default (pippo, pluto, paperino)
- Note di esempio
- Test di condivisione
- Esempi di ricerca e filtri

Su Postman, è necessario importare selezionare il giusto environment che riporti la `base_url` corretta

### Documentazione API

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

### Endpoint Principali

#### Autenticazione
- `POST /api/v1/auth/register` - Registrazione utente
- `POST /api/v1/auth/login` - Login utente
- `POST /api/v1/auth/refresh` - Refresh token
- `POST /api/v1/auth/logout` - Logout utente

#### Utenti
- `GET /api/v1/users/me` - Informazioni utente corrente
- `GET /api/v1/users/search` - Ricerca utenti
- `GET /api/v1/users/{user_id}` - Dettagli utente

#### Note
- `GET /api/v1/notes/` - Lista note (proprie e condivise)
- `POST /api/v1/notes/` - Crea nuova nota
- `GET /api/v1/notes/{note_id}` - Dettagli nota
- `PUT /api/v1/notes/{note_id}` - Modifica nota
- `DELETE /api/v1/notes/{note_id}` - Elimina nota
- `POST /api/v1/notes/{note_id}/share` - Condividi nota
- `DELETE /api/v1/notes/{note_id}/share/{user_id}` - Rimuovi condivisione

### Esempi di Utilizzo

#### Registrazione
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}'
```

#### Login
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass123"
```

#### Creazione Nota
```bash
curl -X POST "http://localhost:8000/api/v1/notes/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "title": "La mia prima nota",
    "content": "Contenuto della nota",
    "tags": ["importante", "lavoro"]
  }'
```

## Configurazione

### Variabili d'Ambiente

L'applicazione utilizza diverse variabili d'ambiente per la configurazione. I valori di default sono definiti in `app/core/config.py` e vengono sovrascritti a seconda dell'ambiente di esecuzione.

| Variabile | Descrizione | Valore Default |
|-----------|-------------|----------------|
| `DATABASE_URL` | URL di connessione PostgreSQL | `postgresql://postgres:password@localhost:5433/shared_notes` |
| `REDIS_URL` | URL di connessione Redis | `redis://localhost:6380` |
| `SECRET_KEY` | Chiave segreta per la firma JWT | `dev-secret-key` |
| `ALGORITHM` | Algoritmo di firma JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_DAYS` | Durata access token (in giorni) | `7` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Durata refresh token (in giorni) | `14` |
| `DEBUG` | Abilita modalità debug | `True` |

**Configurazione per ambiente:**
- **Sviluppo**: Le variabili sono sovrascritte nel file `docker-compose.dev.yml`
- **Produzione**: Le variabili sono sovrascritte nel file `ecs-task-definition.prod.json`

### Migrazioni Database

```bash
# Crea nuova migrazione
alembic revision --autogenerate -m "Descrizione modifica"

# Applica migrazioni
alembic upgrade head

# Rollback migrazione
alembic downgrade -1
```

### Test Manuali

```bash
# Health check
curl http://localhost:8000/health

# Documentazione API
open http://localhost:8000/docs
```

## Deploy

### Deploy su produzione

Per effettuare il deploy in produzione è sufficiente fare push sul branch `main`. La GitHub Actions si attiverà automaticamente e gestirà l'intero processo di deployment.

La GitHub Actions fa il build dell'immagine Docker, la pubblica su Amazon ECR e aggiorna il servizio ECS con la nuova versione dell'applicazione.
