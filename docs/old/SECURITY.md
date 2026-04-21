# Security Policy

## Supported Versions

Security fixes выпускаются для последней minor версии.

| Version | Supported |
|---------|-----------|
| 0.x.x (Pre-Alpha) | ✅ |

## Reporting a Vulnerability

**НЕ открывайте публичный Issue для уязвимостей.**

Напишите на: **security@dharma-rag.org** (создаётся при public launch)

До этого — email владельцу репозитория напрямую.

### Что включить в report

1. Тип уязвимости (XSS, SQL injection, RCE, и т.д.)
2. Полный путь воспроизведения
3. Потенциальное влияние
4. Предложенное исправление (если есть)

### Response timeline

- **24 часа:** acknowledgment получен
- **7 дней:** initial assessment + severity rating
- **30 дней:** patch разработан (для critical)
- **90 дней:** public disclosure (coordinated)

## Scope

### In scope
- Code execution vulnerabilities
- Authentication/authorization bypass
- Injection attacks (SQL, prompt, command)
- Sensitive data exposure
- Privacy violations

### Out of scope
- Social engineering
- Physical attacks
- DoS через legitimate API usage (не volumetric)
- Issues в third-party services (Anthropic, Qdrant) — сообщайте напрямую

## Responsible Disclosure

Мы следуем 90-day coordinated disclosure policy. Public credit в release notes если хотите.

## Known Security Considerations

### Prompt Injection
RAG systems уязвимы к prompt injection через документы корпуса.
**Mitigation:** strict system prompt, citation verification, sandboxed generation.

### API Key Exposure
Никогда не коммитьте `.env` файлы. `.gitignore` защищает, но проверяйте перед каждым push:
```bash
git diff --staged | grep -i "api_key\|secret"
```

### Voice Data
Audio — биометрические данные. См. [PRIVACY.md](PRIVACY.md) для mitigation.
