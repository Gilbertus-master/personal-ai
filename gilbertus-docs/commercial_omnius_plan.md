# Omnius — Plan Komercjalizacji

## Model biznesowy

### SaaS Multi-Tenant
Każda firma = jeden tenant Omniusa. Izolacja danych, osobna DB, osobny Qdrant collection.

### Pricing (propozycja)
| Plan | Cena/msc | Zawiera |
|------|----------|---------|
| **Starter** | 2,000 PLN | 1 operator, 5k docs, email+Teams sync, /ask, tickety |
| **Business** | 5,000 PLN | 5 operatorów, 50k docs, + calendar, + Plaud audio, + RBAC |
| **Enterprise** | 15,000 PLN | Unlimited users, + governance, + custom prompts, + API keys, + audit |
| **Gilbertus** | Custom | Multi-company, cross-tenant, voice, scenario analyzer, market intel |

### Unit economics (szacunek per tenant)
- API costs (Haiku extraction): ~$30-50/msc per 10k docs
- Infra (Hetzner): ~€2-3/tenant (shared PostgreSQL + Qdrant)
- Embedding (OpenAI): ~$5-10/msc per 10k docs
- **Marża: ~80-85% na planie Business**

---

## Roadmap komercjalizacji

### Faza 0: Internal (teraz — Q2 2026)
- REH + REF jako pilot (6 miesięcy)
- Zbieranie feedbacku od Rocha i Krystiana
- Iteracja na produkcie

### Faza 1: Beta (Q3 2026)
- 2-3 zaprzyjaźnione firmy (sektor energetyczny)
- White-label branding
- Onboarding manual + self-service setup

### Faza 2: Launch (Q4 2026)
- Landing page + demo
- Self-service provisioning (Docker auto-deploy)
- Billing integration (Stripe)
- SLA + support tiers

### Faza 3: Scale (2027)
- Marketplace integracji (SAP, Salesforce, Dynamics)
- Vertical features (energia, finanse, prawo)
- Multi-region (EU compliance, GDPR)
- Partner program

---

## Wymagania techniczne (pre-launch)

### Must-have
- [ ] Automated tenant provisioning (create DB, Qdrant collection, seed RBAC)
- [ ] Billing/metering (API calls, storage, users)
- [ ] Self-service admin panel (manage users, config, sync)
- [ ] Health monitoring per tenant (alerting)
- [ ] Backup/restore per tenant
- [ ] Rate limiting per API key
- [ ] GDPR: data export, data deletion per tenant

### Nice-to-have
- [ ] Custom branding per tenant (logo, colors)
- [ ] Plugin system (custom sync sources)
- [ ] Webhook notifications
- [ ] SSO (SAML/OIDC beyond Azure AD)

---

## IP Box i compliance

### IP Box 5%
- Gilbertus + Omnius = kwalifikowane IP (autorskie prawo do programu)
- Dochody z licencji SaaS kwalifikują się do 5% PIT
- Ewidencja R&D: dev logi, git history, session summaries (gotowe)
- Nexus = 1.3 (maksymalny — 100% prac wewnętrznych)

### GDPR
- Dane przechowywane w EU (Hetzner DE/FI)
- Tenant isolation gwarantuje separację danych
- Audit log spełnia wymogi Article 30
- Data Processing Agreement (DPA) template potrzebny

### Umowy
- [ ] Regulamin usługi (ToS)
- [ ] Polityka prywatności
- [ ] DPA template
- [ ] SLA template
- [ ] NDA (dla pilotowych klientów)
