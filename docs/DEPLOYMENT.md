# Deployment Guide

> Инструкции по деплою Dharma RAG в production. Создаётся в Phase 4 (день 50-56).

---

## Архитектура production

```
                    ┌──────────────────┐
   Internet ────►   │    Cloudflare    │  (DNS, DDoS protection, CDN)
                    └────────┬─────────┘
                             │ HTTPS
                    ┌────────▼─────────┐
                    │   Caddy 2.x      │  (reverse proxy, auto-SSL)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   FastAPI app    │  (8000)
                    │   uvicorn        │
                    └────┬─────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
       ┌──────▼──────┐      ┌──────▼──────┐
       │   Qdrant    │      │  Langfuse   │
       │   :6333     │      │   :3000     │
       └─────────────┘      └─────────────┘
```

---

## Платформа: Hetzner

### Phase 1: CX32 (€9/мес)

- **CPU:** 4 vCPU (Intel)
- **RAM:** 8 GB
- **Disk:** 80 GB NVMe
- **Traffic:** 20 TB/мес
- **Локация:** Helsinki (FI) — близко к разработчику и EU-friendly

### Phase 2: CCX33 (€60/мес) после ~1000 DAU

- **CPU:** 8 dedicated vCPU
- **RAM:** 32 GB
- **Disk:** 240 GB NVMe

### Phase 3: + GPU для voice (опционально)

- **GEX44** (€184/мес): RTX 4000 SFF Ada, 20 GB VRAM
- Или Modal.com on-demand

### Альтернативы

| Провайдер | Плюсы | Минусы |
|-----------|-------|--------|
| **Hetzner** ⭐ | Дешево, EU, надёжно | UI устаревший |
| Servers.com | Гибкие конфиги | Дороже |
| Linode (Akamai) | Хорошие дата-центры | Дороже |
| Vultr | Много локаций | Слабее RAM |
| ❌ Aeza | (исключено) | (исключено) |
| ❌ OVH | (исключено) | (исключено) |

---

## Initial Setup (день 50)

### 1. Заказать сервер

- Регистрация на [hetzner.com/cloud](https://hetzner.com/cloud)
- Создать проект "dharma-rag"
- Запустить CX32:
  - OS: Ubuntu 24.04
  - SSH ключ: добавить ваш публичный
  - Локация: Helsinki

### 2. Базовая защита

```bash
# SSH в сервер
ssh root@<server-ip>

# Создать пользователя
adduser dharma
usermod -aG sudo dharma
mkdir /home/dharma/.ssh
cp ~/.ssh/authorized_keys /home/dharma/.ssh/
chown -R dharma:dharma /home/dharma/.ssh
chmod 700 /home/dharma/.ssh

# Запретить root SSH
nano /etc/ssh/sshd_config
# PermitRootLogin no
# PasswordAuthentication no
systemctl restart sshd

# Firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# Fail2ban
apt update && apt install -y fail2ban
systemctl enable --now fail2ban

# Auto updates
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

### 3. Установить Docker

```bash
# Войти как dharma
ssh dharma@<server-ip>

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker dharma
# Разлогинимся/залогинимся для применения

# Проверка
docker run hello-world
```

### 4. Установить Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

---

## Деплой приложения

### 1. Подготовка домена (день 52)

1. Купить домен (например, **dharma-rag.org**) — Namecheap, Porkbun
2. Добавить в Cloudflare:
   - Создать аккаунт на cloudflare.com
   - Add Site → ввести dharma-rag.org → Free plan
   - Изменить nameservers на регистраторе на Cloudflare
3. DNS записи:
   ```
   A    @         <hetzner-ip>    Proxy: ON
   A    api       <hetzner-ip>    Proxy: ON
   A    bot       <hetzner-ip>    Proxy: OFF (для Telegram webhook)
   ```

### 2. Caddyfile

```caddyfile
# /etc/caddy/Caddyfile

dharma-rag.org, www.dharma-rag.org {
    encode gzip zstd

    # Frontend
    handle /static/* {
        root * /var/www/dharma-rag/static
        file_server
    }

    # API
    handle /api/* {
        reverse_proxy localhost:8000
    }

    # SSE streaming для chat
    handle /api/query/stream {
        reverse_proxy localhost:8000 {
            transport http {
                read_timeout 5m
            }
        }
    }

    # Главная страница (Jinja2 + HTMX)
    handle {
        reverse_proxy localhost:8000
    }

    # Logs
    log {
        output file /var/log/caddy/dharma-rag.log {
            roll_size 100mb
            roll_keep 10
        }
    }
}

# Langfuse — только для админа через basic auth
langfuse.dharma-rag.org {
    basicauth {
        admin <hashed-password>
    }
    reverse_proxy localhost:3000
}
```

```bash
sudo systemctl reload caddy
```

### 3. Dockerfile приложения

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Зависимости
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Код
COPY src/ src/
COPY frontend/ frontend/

# Скачать модели заранее (чтобы не делать это при старте)
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-m3'); \
    SentenceTransformer('BAAI/bge-reranker-v2-m3')"

EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### 4. docker-compose.prod.yml

```yaml
services:
  app:
    image: ghcr.io/toneruseman/dharma-rag:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      QDRANT_URL: http://qdrant:6333
      LANGFUSE_HOST: http://langfuse:3000
      APP_ENV: production
      LOG_LEVEL: INFO
    env_file:
      - .env.prod
    depends_on:
      qdrant:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s

  qdrant:
    image: qdrant/qdrant:v1.12.4
    restart: unless-stopped
    ports:
      - "127.0.0.1:6333:6333"
    volumes:
      - qdrant_storage:/qdrant/storage
    environment:
      QDRANT__SERVICE__HTTP_PORT: 6333
      QDRANT__STORAGE__PERFORMANCE__MAX_OPTIMIZATION_THREADS: 2

  langfuse-db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD_FILE: /run/secrets/langfuse_db_password
      POSTGRES_DB: langfuse
    volumes:
      - langfuse_db_data:/var/lib/postgresql/data
    secrets:
      - langfuse_db_password

  langfuse:
    image: langfuse/langfuse:2
    restart: unless-stopped
    depends_on:
      - langfuse-db
    ports:
      - "127.0.0.1:3000:3000"
    env_file:
      - .env.langfuse

volumes:
  qdrant_storage:
  langfuse_db_data:

secrets:
  langfuse_db_password:
    file: ./secrets/langfuse_db_password.txt
```

### 5. CI/CD через GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/toneruseman/dharma-rag:latest

      - name: Deploy to Hetzner
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.HETZNER_HOST }}
          username: dharma
          key: ${{ secrets.HETZNER_SSH_KEY }}
          script: |
            cd /home/dharma/dharma-rag
            docker compose -f docker-compose.prod.yml pull app
            docker compose -f docker-compose.prod.yml up -d --no-deps app
            docker image prune -f
```

GitHub secrets:
- `HETZNER_HOST` — IP сервера
- `HETZNER_SSH_KEY` — приватный ключ SSH

---

## Backup стратегия

### Что бэкапим

1. **Qdrant collections** — критично
2. **Langfuse Postgres** — желательно
3. **Палийский глоссарий и configs** — в git, ОК
4. **Транскрипты** — на отдельный storage (Hetzner Storage Box €4/мес/1TB)

### Скрипт

```bash
#!/bin/bash
# /home/dharma/scripts/backup.sh

DATE=$(date +%Y%m%d)
BACKUP_DIR=/mnt/backup

# Qdrant snapshot
docker exec dharma-qdrant curl -X POST http://localhost:6333/snapshots
docker cp dharma-qdrant:/qdrant/snapshots/. $BACKUP_DIR/qdrant_$DATE/

# Postgres dump
docker exec dharma-langfuse-db pg_dump -U langfuse langfuse | gzip > $BACKUP_DIR/langfuse_$DATE.sql.gz

# Sync to Storage Box
rclone sync $BACKUP_DIR storagebox:dharma-rag-backups/

# Очистка локально (хранить 7 дней)
find $BACKUP_DIR -mtime +7 -delete
```

Cron:
```cron
0 3 * * * /home/dharma/scripts/backup.sh >> /var/log/backup.log 2>&1
```

---

## Мониторинг

### Health checks

- **Caddy:** автоматически проверяет upstream
- **App:** `/api/health` возвращает `{"status": "ok", "qdrant": "ok", "version": "0.4.0"}`
- **UptimeRobot:** бесплатный мониторинг каждые 5 мин

### Метрики

Phase 4 (день 53-55) — Prometheus + Grafana на том же VPS:

```yaml
# Добавить в docker-compose.prod.yml

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "127.0.0.1:9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "127.0.0.1:3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
```

### Алерты в Telegram

```python
# scripts/alert_telegram.py

def send_alert(severity, message):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": ADMIN_CHAT_ID,
            "text": f"🚨 {severity}: {message}"
        }
    )
```

Триггеры:
- error_rate > 1% за 5 минут
- latency p95 > 5s
- diskspace < 10%
- API down

---

## Масштабирование

### Признаки, что пора масштабировать

- CPU > 80% постоянно
- RAM > 90%
- Latency p95 > 3s
- Disk I/O bottleneck

### Шаги

1. **Vertical scale** (проще): CX32 → CCX33 (€9 → €60)
   - Hetzner: один клик в UI, ~2 мин downtime

2. **Read replicas** для Qdrant
3. **CDN** через Cloudflare (уже есть)
4. **App workers:** uvicorn --workers 4 → 8

### При >5000 DAU

- Отдельный сервер для Qdrant
- Redis для семантического кеша (вместо отдельной Qdrant коллекции)
- Load balancer (Cloudflare Load Balancing $5/мес)

---

## Disaster Recovery

### Сценарии

1. **VPS упал:** restore из backup на новый VPS, ~2 часа
2. **Qdrant corrupted:** restore из снапшота, ~30 мин
3. **Langfuse потерян:** не критично, метрики собираются заново
4. **Утечка ключей:** сменить ANTHROPIC_API_KEY, deploy, ~10 мин

### Runbooks

См. `docs/runbooks/`:
- `vps-recovery.md`
- `qdrant-restore.md`
- `key-rotation.md`

---

## Checklist перед деплоем

- [ ] Все тесты проходят (`pytest`)
- [ ] Eval не показывает регрессий (`python -m src.eval.compare`)
- [ ] Версия в pyproject.toml обновлена
- [ ] CHANGELOG.md обновлён
- [ ] Backup сделан перед migrations
- [ ] Migrations DB протестированы на staging (если есть)
- [ ] .env.prod не закоммичен
- [ ] Smoke test: `curl https://dharma-rag.org/api/health`
- [ ] Telegram bot отвечает на /start
- [ ] Алерты включены

---

## Полезные команды

```bash
# Логи приложения
docker compose logs -f app

# Перезапуск приложения
docker compose -f docker-compose.prod.yml restart app

# Войти в контейнер
docker exec -it dharma-app bash

# Qdrant операции
curl localhost:6333/collections
curl localhost:6333/collections/dharma_v1 -X DELETE

# Размер storage
du -sh /var/lib/docker/volumes/dharma-rag_qdrant_storage/_data/

# Проверить SSL
curl -I https://dharma-rag.org

# Использование диска
df -h
docker system df
```
