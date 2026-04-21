# Privacy Policy & Data Handling

> Как Dharma RAG обрабатывает пользовательские данные. Приватность — один из принципов проекта.

---

## Принципы

1. **Сбор минимум данных** — только то, что необходимо для работы
2. **Zero retention по умолчанию** — данные не хранятся дольше, чем нужно
3. **Прозрачность** — открытый код, вы видите всё
4. **Контроль пользователя** — право на удаление всегда работает
5. **Voice особо защищен** — медитация — состояние уязвимости

---

## Какие данные собираются

### Web (дhaрма-rag.org)

**Что собирается:**
- Текст запроса (для RAG)
- IP-адрес (для rate limiting, затем хэшируется)
- User-Agent (для статистики браузеров)
- Timestamp запроса

**Что НЕ собирается:**
- Имена, email, другая PII
- Cookies (кроме сессионного техкеша)
- Fingerprinting, tracking pixels
- Рекламные идентификаторы

### Telegram bot

**Что собирается:**
- Telegram user ID (для rate limiting)
- Текст команд и запросов

**Что НЕ собирается:**
- Номер телефона
- Имя, username (хранится только ID)
- История вне контекста текущей сессии

### Voice (Phase 3+)

**На устройстве (по умолчанию):**
- Аудио обрабатывается локально (Sherpa-ONNX STT)
- Транскрипт отправляется на сервер как текст

**В облаке (только если on-device недоступен):**
- Аудио stream отправляется в Deepgram/OpenAI
- Zero-retention режим включен у провайдера
- Аудио НЕ логируется на нашем сервере

### Mobile (Phase 2+)

**На устройстве:**
- История чата (опционально, в SQLite)
- Настройки темы, языка
- Кеш частых запросов

**Отправляется на сервер:**
- То же, что для Web

---

## Как данные используются

### Разрешено

- ✅ Обработка запроса в RAG pipeline
- ✅ Rate limiting
- ✅ Анонимные агрегированные метрики (кол-во запросов/день)
- ✅ Отладка ошибок (через logged stack traces без PII)
- ✅ Improvement system prompts (только с явного разрешения через thumbs up/down)

### Запрещено

- ❌ Продажа данных третьим сторонам
- ❌ Реклама на основе запросов
- ❌ Profile-building пользователей
- ❌ Передача властям без судебного ордера (если применимо в юрисдикции)
- ❌ Обучение моделей на пользовательских запросах без opt-in

---

## Хранение данных

### Retention periods

| Тип данных | Retention | Где |
|------------|-----------|-----|
| Текст запроса в кеше | 30 дней | Qdrant cache collection |
| IP-адрес (хэш) | 24 часа | Redis / память |
| Langfuse traces | 90 дней | Postgres |
| Логи приложения | 30 дней | Файловая система VPS |
| Voice audio | 0 | Не сохраняется |
| Voice transcripts в БД | 0 | Не сохраняется |

### Автоматическое удаление

Ежедневный cron:
```python
# scripts/cleanup.py
delete_cache_older_than(days=30)
delete_ip_logs_older_than(hours=24)
delete_langfuse_traces_older_than(days=90)
```

---

## Права пользователя (GDPR)

### Article 15 — Право доступа

Пользователь может запросить всю информацию о своих данных:
- Email на privacy@dharma-rag.org (создаётся при public launch)
- Response time: 30 дней
- Формат: JSON

### Article 17 — Право на удаление

Для Telegram bot: команда `/forget`
- Удаляет: все traces с вашим user_id
- Не удаляет: анонимные агрегированные метрики

Для веб: форма на `/privacy/delete` с указанием IP или session ID
- Удаляет: все traces связанные с указанным идентификатором

### Article 20 — Portability

Пользователь может экспортировать свои данные через `/privacy/export`.

---

## Voice-специфичные меры

Voice data считается **биометрическими данными** по GDPR и требует особой защиты.

### Архитектура по умолчанию

```
Пользователь ─── [локальный STT Sherpa-ONNX] ───► транскрипт
                                                      │
                                                      ▼
                                            [HTTPS] ───► сервер
                                                      │
                                               RAG pipeline
                                                      │
                                                      ▼
                                            [текст ответа] ───► устройство
                                                      │
                                                      ▼
                                            [локальный TTS Kokoro]
                                                      │
                                                      ▼
                                                   аудио
```

**Ключевое:** аудио никогда не покидает устройство по умолчанию.

### Fallback в облако

Если on-device STT недоступен (старое устройство, нет памяти):

1. **Запрос явного согласия** пользователя ("Your audio will be sent to Deepgram for transcription")
2. **Zero-retention режим** у провайдера (Deepgram API flag `no_delay=false`)
3. **Нет логирования** аудио на нашем сервере
4. **Транскрипт удаляется** сразу после формирования ответа

### Vulnerability context

Медитация — состояние ментальной уязвимости. Доп. меры:

- **Push-to-talk** по умолчанию (не always-on)
- **Чёткая индикация** записи (иконка + звуковой сигнал)
- **"Pause recording"** кнопка всегда доступна
- **Warning перед первой voice-сессией** — объяснение privacy

---

## Third-party services

Мы используем:

| Сервис | Для чего | Их privacy policy |
|--------|----------|-------------------|
| **Anthropic Claude** | LLM generation | [anthropic.com/privacy](https://anthropic.com/privacy) — по умолчанию API data не используется для training |
| **Deepgram** (Phase 3) | Cloud STT | [deepgram.com/privacy](https://deepgram.com/privacy) — zero-retention доступен |
| **ElevenLabs** (Phase 3) | Cloud TTS | [elevenlabs.io/privacy](https://elevenlabs.io/privacy) |
| **Cloudflare** | DNS, DDoS protection | [cloudflare.com/privacy](https://cloudflare.com/privacy) |
| **Hetzner** | Hosting | [hetzner.com/legal/privacy-policy](https://hetzner.com/legal/privacy-policy) — GDPR compliant, EU data center |

---

## DPIA (Data Protection Impact Assessment)

**Нужен:** да, для voice-функциональности (Phase 3+)

**Когда проводить:** перед public launch voice features

**Что оценивается:**
1. Nature and scope of processing (voice data of meditators)
2. Risks to rights and freedoms (emotional vulnerability)
3. Measures to address risks (on-device processing, zero retention)
4. Consultation с data subjects и DPO

**Шаблон:** [ICO DPIA template](https://ico.org.uk/media/for-organisations/documents/2553993/dpia-template.docx)

---

## Инциденты

### Что такое инцидент

- Утечка API ключей (публикация в git)
- Компрометация сервера
- Утечка дампа БД
- Массовый unauthorized access

### Response plan

1. **Detect** (0-1 час): через алерты или manual report
2. **Contain** (1-4 часа): сменить ключи, заблокировать доступ
3. **Assess** (4-24 часа): масштаб, затронутые данные
4. **Notify** (до 72 часов): если есть PII — уведомить пользователей + data protection authority
5. **Remediate** (24-72 часа): исправить уязвимость
6. **Post-mortem** (1-2 недели): публичный отчёт на GitHub

### Контакт для security research

- Email: security@dharma-rag.org (создаётся при public launch)
- PGP key: будет опубликован
- **Responsible disclosure:** 90 дней между репортом и публикацией

---

## Для европейских пользователей

Этот сервис размещён в Helsinki, Finland (Hetzner DC FI-HEL1) → попадает под GDPR.

**Data Protection Officer:** (при необходимости — когда >5 постоянных сотрудников или обработка в большом масштабе).

На Phase 1-2: solo developer, не обязан иметь DPO. Добавится при росте.

---

## Для пользователей вне EU

Мы следуем GDPR стандартам независимо от вашей локации, потому что:
- Это правильно
- Проще иметь один стандарт
- Многие юрисдикции движутся к похожим нормам (CCPA, LGPD, PIPL)

---

## Изменения этой политики

- Material changes → notification на главной странице + Telegram broadcast
- Grace period: 30 дней до вступления в силу
- История изменений: git history этого файла

---

## Контакты

- General privacy: privacy@dharma-rag.org
- Security: security@dharma-rag.org
- Data protection requests: dpo@dharma-rag.org

---

> "Satyam bruyat priyam bruyat, na bruyat satyam apriyam" —
> Говорите правду. Говорите приятно. Не говорите неприятной правды.
> (Manusmrti 4.138; приложимо и к privacy — правда о данных всегда.)
