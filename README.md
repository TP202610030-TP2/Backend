# Plataforma ASR Quechua — Backend

> Sistema de reconocimiento automático de voz (ASR) para el idioma **quechua**, construido como arquitectura de microservicios con Python/FastAPI y un modelo Whisper fine-tuneado para quechua.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Whisper](https://img.shields.io/badge/Whisper-Quechua_finetuned-412991?logo=huggingface&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white)

---

## ✅ Requisitos previos

| Herramienta | Versión | Notas |
|---|---|---|
| **Docker Desktop** | 24 + | Modo **Linux containers** en Windows |
| **Git** | 2.x | — |
| **RAM disponible** | 4 GB | Whisper-base fine-tuned usa ~1 GB en inferencia CPU |
| **Espacio en disco** | 4 GB | Imágenes Docker + modelo HuggingFace (~300 MB) |

> **Windows**: verificar que Docker Desktop esté en modo Linux containers antes de continuar.

---

## 🚀 Inicio rápido

### 1 · Clonar el repositorio

```bash
git clone <url-del-repo>
cd tp1-tp2/Backend
```

### 2 · Crear el archivo `.env`

Crear un archivo `.env` en la **raíz del proyecto** (`Backend/.env`):

```env
JWT_SECRET_KEY=reemplaza_esto_con_una_clave_de_al_menos_32_caracteres
```

Para generar una clave segura:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> Si no se define `JWT_SECRET_KEY`, se usará `changeme_in_production`. **No apto para ningún entorno compartido.**

### 3 · Build e inicio

```bash
docker compose up --build
```

La primera ejecución realiza automáticamente:

1. Construye las 6 imágenes Docker
2. Descarga el modelo **[QuechuaBase/whisper-base-qxp-finetuned](https://huggingface.co/QuechuaBase/whisper-base-qxp-finetuned)** desde HuggingFace — puede tardar varios minutos
3. Levanta las 4 bases de datos PostgreSQL y espera a que estén listas (`pg_isready`)
4. Ejecuta las migraciones **Alembic** (`alembic upgrade head`) en cada servicio
5. Inicia todos los servicios; el gateway espera a que los 4 pasen su healthcheck

### 4 · Verificar

```bash
docker compose ps
```

Todos los contenedores deben mostrar `(healthy)`:

```
backend-api-gateway-1             Up (healthy)   0.0.0.0:8000->8000/tcp
backend-auth-service-1            Up (healthy)   0.0.0.0:8001->8000/tcp
backend-user-service-1            Up (healthy)   0.0.0.0:8002->8000/tcp
backend-audio-processor-1         Up (healthy)   0.0.0.0:8003->8000/tcp
backend-asr-service-1             Up (healthy)   0.0.0.0:8004->8000/tcp
backend-transcription-manager-1   Up (healthy)   0.0.0.0:8005->8000/tcp
```

### 5 · Probar el API

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "service": "api-gateway",
  "version": "1.0.0"
}
```

📖 Swagger UI interactivo: **http://localhost:8000/api/docs**

---

## URLs de los servicios

| Servicio | URL (host) | Swagger UI |
|---|---|---|
| **API Gateway** *(público)* | http://localhost:8000 | http://localhost:8000/api/docs |
| Auth Service | http://localhost:8001 | http://localhost:8001/docs |
| User Service | http://localhost:8002 | http://localhost:8002/docs |
| Audio Processor | http://localhost:8003 | http://localhost:8003/docs |
| ASR Service | http://localhost:8004 | http://localhost:8004/docs |
| Transcription Manager | http://localhost:8005 | http://localhost:8005/docs |

> En producción, **solo el API Gateway** tiene ingress público. El resto son servicios internos.

### Endpoints principales (vía Gateway)

```
# Autenticación
POST   /api/v1/auth/register          Registro de usuario
POST   /api/v1/auth/login             Login → JWT
POST   /api/v1/auth/logout            Logout (invalida el token)
POST   /api/v1/auth/password-recovery Solicitar recuperación
POST   /api/v1/auth/password-reset    Resetear contraseña con token

# Perfil
GET    /api/v1/users/profile          Ver perfil  [JWT requerido]
PUT    /api/v1/users/profile          Actualizar perfil

# Dashboard
GET    /api/v1/dashboard              Perfil + resumen + estado de servicios

# Transcripción
POST   /api/v1/transcribe             Subir audio → transcripción ASR
GET    /api/v1/transcriptions         Historial paginado
GET    /api/v1/transcriptions/{id}    Detalle con word confidences
GET    /api/v1/transcriptions/{id}/download?format=txt|json|srt

# Transcripción asíncrona (v2) — 202 inmediato, el resultado se consulta luego
POST   /api/v1/jobs                   Encolar audio → {job_id, status_url}
GET    /api/v1/jobs/{job_id}          Estado: queued | processing | done | failed (+ texto)

# Streaming
WS     /ws/stream?token=<jwt>&sample_rate=<hz>   Streaming en tiempo real (WebSocket)
```

---

## Variables de entorno

### `.env` en la raíz del proyecto

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `JWT_SECRET_KEY` | **Sí** | `changeme_in_production` | Clave HMAC-SHA256 para firmar JWT (≥ 32 chars) |
| `STORAGE_URL` | No | `local` | URL de almacenamiento de audio |

### Configuración avanzada por servicio

Cada servicio acepta variables de entorno propias que se pueden sobreescribir en `docker-compose.yml` o en un `.env` local:

<details>
<summary>Ver variables completas por servicio</summary>

**auth-service**
| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://auth_user:auth_pass@auth-db:5432/auth_db` |
| `JWT_SECRET_KEY` | `changeme_in_production` |
| `JWT_EXPIRATION_HOURS` | `24` |
| `BCRYPT_ROUNDS` | `12` |
| `RATE_LIMIT_ATTEMPTS` | `5` |
| `RATE_LIMIT_WINDOW_MINUTES` | `15` |

**asr-service**
| Variable | Default |
|---|---|
| `MODEL_ID` | `QuechuaBase/whisper-base-qxp-finetuned` |
| `DEVICE` | `cpu` (`cuda` para GPU) |
| `AUTH_SERVICE_URL` | `http://auth-service:8000` |
| `TRANSCRIPTION_MANAGER_URL` | `http://transcription-manager:8000` |

Para cambiar el modelo HuggingFace:
```bash
# En docker-compose.yml, cambiar:
MODEL_ID=QuechuaBase/whisper-base-qxp-finetuned
```
</details>

---

## Ejecutar tests

Cada servicio tiene su propio conjunto de tests con pytest. Requiere **Python 3.11+** instalado localmente.

### Tests de un servicio

```bash
cd services/auth-service
pip install -r requirements.txt -r requirements-dev.txt
pytest --cov=app --cov-report=term-missing -v
```

### Todos los servicios (script)

```bash
for svc in auth-service user-service audio-processor asr-service transcription-manager api-gateway; do
  echo "=== $svc ==="
  (cd services/$svc && pip install -r requirements.txt -r requirements-dev.txt -q && pytest --tb=short -q)
done
```

### Tests E2E (gateway)

```bash
cd services/api-gateway
pytest tests/e2e/ -v
```

### Tests de propiedades con Hypothesis

```bash
# Audio Processor — metadatos de audio
cd services/audio-processor && pytest tests/property/ -v

# API Gateway — payloads de registro
cd services/api-gateway && pytest tests/property/ -v
```

---

## Estructura del proyecto

```
Backend/
├── docker-compose.yml              # Orquestación local completa
├── .env                            # Variables de entorno (no commitear)
│
├── services/
│   ├── api-gateway/                # 🔀 Punto de entrada único (puerto 8000)
│   │   ├── app/
│   │   │   ├── api/routes/         # auth, users, dashboard, transcriptions, streaming
│   │   │   └── core/               # config, exceptions, response envelope
│   │   └── tests/
│   │       ├── e2e/                # Tests de integración E2E (11 flows)
│   │       └── property/           # Tests de propiedades Hypothesis
│   │
│   ├── auth-service/               # 🔐 JWT, bcrypt, blocklist (puerto 8001)
│   │   ├── app/
│   │   │   ├── models/             # UserCredential, TokenBlocklist, PasswordRecoveryToken
│   │   │   ├── services/           # AuthService, RateLimiter
│   │   │   └── core/security.py   # JWT, bcrypt, SHA-256
│   │   └── alembic/                # Migraciones DB
│   │
│   ├── user-service/               # 👤 Registro y perfiles (puerto 8002)
│   │   ├── app/
│   │   │   ├── models/             # UserProfile, EmailChangeRequest
│   │   │   └── services/           # UserService
│   │   └── alembic/
│   │
│   ├── audio-processor/            # 🎵 Validación y conversión de audio (puerto 8003)
│   │   ├── app/
│   │   │   ├── models/             # AudioFile
│   │   │   └── services/           # AudioService, FfmpegService, MetadataService
│   │   └── alembic/
│   │
│   ├── asr-service/                # 🤖 Whisper + WebSocket streaming (puerto 8004)
│   │   └── app/services/           # WhisperService, StreamingService, DeviceManager, CodecService
│   │
│   ├── transcription-manager/      # 📄 Historial y descarga (puerto 8005)
│   │   ├── app/
│   │   │   ├── models/             # Transcription, WordConfidence
│   │   │   └── services/           # TranscriptionService, DownloadService
│   │   └── alembic/
│   │
│   └── monolith-baseline/          # 🧱 Control experimental E3 (puerto 8006)
│       └── app/                    # auth + audio + ASR + persistencia en un solo proceso
│
├── experiments/                    # 🧪 Herramientas de medición E1-E7 (ver experiments/README.md)
│   ├── common/                     # manifest, asr_client, stats, text_norm
│   └── e1_.../ e2_.../ e4_.../ e5_.../ e6_.../ e7_.../
│
├── docs/                           # 📚 Documentación de diseño por fase (mecanismo adaptativo, monolito, etc.)
│
└── contexto/
    └── tasks.md                    # Backlog y trazabilidad de historias de usuario
```

---

## Comandos útiles

```bash
# Ver logs de un servicio
docker compose logs -f auth-service

# Reiniciar un servicio sin reconstruir
docker compose restart user-service

# Reconstruir y reiniciar un servicio específico
docker compose up --build auth-service -d

# Parar todo (conserva los datos de las DBs)
docker compose down

# Parar todo y borrar datos (reset completo)
docker compose down -v

# Conectarse a una base de datos
docker compose exec auth-db psql -U auth_user -d auth_db

# Ver estado de migraciones
docker compose exec auth-service alembic current
docker compose exec auth-service alembic history
```

---

## Notas importantes

<details>
<summary><strong>Primera ejecución — modelo ASR Quechua</strong></summary>

El servicio `asr-service` descarga **[QuechuaBase/whisper-base-qxp-finetuned](https://huggingface.co/QuechuaBase/whisper-base-qxp-finetuned)** desde HuggingFace durante la primera construcción de la imagen. Este proceso puede tardar entre 2 y 10 minutos dependiendo de la conexión a internet.

El modelo es un **Whisper-base fine-tuneado para Puno Quechua (qxp)** usando datos de Mozilla Common Voice. Usa la librería `transformers` (no `openai-whisper`).

Las siguientes ejecuciones son instantáneas porque el modelo queda cacheado en el volumen Docker `/root/.cache/huggingface`.

Para cambiar el modelo (por ejemplo a otro fine-tune de quechua):
```bash
# En docker-compose.yml, bajo asr-service > environment:
- MODEL_ID=otro-usuario/otro-modelo-quechua
```

</details>

<details>
<summary><strong>Migraciones automáticas al iniciar</strong></summary>

Todos los servicios con base de datos ejecutan `alembic upgrade head` automáticamente antes de arrancar uvicorn. El `CMD` del Dockerfile es:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Si la base de datos no está lista, el contenedor falla y Docker lo reinicia gracias a `restart: on-failure`. Los healthchecks de PostgreSQL con `pg_isready` garantizan el orden correcto de arranque.

</details>

<details>
<summary><strong>Streaming WebSocket — protocolo y ejemplo con wscat</strong></summary>

**Protocolo:**

1. El cliente conecta a `ws://.../ws/stream?token=<jwt>&sample_rate=<hz>&encoding=<pcm|opus|mp3>`.
   - `sample_rate` es la frecuencia **real** del audio capturado (ej. `48000`, el nativo del `AudioContext` del navegador). Si se omite, el backend asume `16000`.
   - `encoding` por defecto es `pcm` — es el único valor que usa el frontend real. `opus`/`mp3` existen **solo** para el experimento E5 (`experiments/e5_streaming_codec/`), que mide cuantitativamente si la compresión realmente induce alucinaciones (ver `docs/04-streaming-codec.md`). Con `encoding != pcm` no hay transcripciones parciales en vivo, solo resultado final.
   - **Importante:** el audio debe capturarse con la **Web Audio API** (`AudioContext` + `ScriptProcessorNode`/`AudioWorkletNode`) para obtener PCM crudo. `MediaRecorder` (con su codec por defecto, normalmente Opus/WebM comprimido) **no es compatible** con `encoding=pcm` (el default) — el backend interpreta los bytes recibidos como PCM 16-bit mono crudo, y datos comprimidos sin declarar `encoding=opus` producen ruido/alucinaciones en la transcripción.
2. El cliente envía **frames binarios**: PCM 16-bit mono crudo, a la frecuencia indicada en `sample_rate`.
3. El servidor responde cada pocos segundos con un mensaje de texto parcial:
   ```json
   {"type": "partial", "text": "...", "timestamp": "..."}
   ```
4. Al terminar de grabar, el cliente envía un **frame de texto** con el valor `"stop"` (sin cerrar el socket) y espera el resultado final:
   ```json
   {
     "type": "final",
     "transcription_id": "...",
     "text": "...",
     "duration": 12.4,
     "confidence_scores": [{"word": "...", "confidence": 1.0, "start_time": 0.0, "end_time": 0.5, "sequence_number": 0}],
     "timestamp": "..."
   }
   ```
5. El servidor cierra la conexión después de enviar el resultado final.

```bash
# Instalar wscat
npm install -g wscat

# 1. Obtener JWT
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"password123"}' | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 2. Conectar al stream (sample_rate del AudioContext del navegador, normalmente 48000)
wscat -c "ws://localhost:8000/ws/stream?token=$TOKEN&sample_rate=48000"

# 3. Enviar chunks binarios de PCM 16-bit mono crudo (no Opus/WebM)
# 4. Enviar el texto "stop" para finalizar y recibir el resultado final
```

</details>
