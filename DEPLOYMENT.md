# 🚀 AWS ECS Deployment Guide - Shared Notes API

Questa guida ti aiuterà a deployare l'API Shared Notes su AWS ECS con infrastruttura completamente gestita.

## 🏗️ Architettura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Internet      │    │   ALB           │    │   ECS Fargate   │
│                 │───▶│                 │───▶│                 │
│   Users/Web     │    │   Load Balancer │    │   API Containers│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                       ┌─────────────────┐             │
                       │   RDS           │◀────────────┘
                       │   PostgreSQL    │
                       └─────────────────┘
                                
                       ┌─────────────────┐
                       │   ElastiCache   │◀────────────┘
                       │   Redis         │
                       └─────────────────┘
```

## 📋 Prerequisiti

- [ ] Account AWS attivo
- [ ] AWS CLI installato e configurato
- [ ] Docker installato e funzionante
- [ ] Repository GitHub con il codice
- [ ] Permessi IAM per creare risorse AWS
- [ ] VPC di default disponibile nella regione eu-central-1

## 🔧 Setup Completo

### 1. **Setup Infrastruttura AWS**

```bash
# Rendi eseguibile lo script
chmod +x setup-aws-infrastructure.sh

# Esegui lo script di setup (crea VPC, RDS, ElastiCache, etc.)
./setup-aws-infrastructure.sh
```

**Cosa crea questo script:**
- ✅ Utilizza VPC di default di AWS (più economico)
- ✅ Security Groups per ALB, ECS, RDS, ElastiCache
- ✅ RDS PostgreSQL instance
- ✅ ElastiCache Redis cluster
- ✅ AWS Secrets Manager per credenziali
- ✅ CloudWatch Log Groups

### 2. **Setup ECS Service**

```bash
# Rendi eseguibile lo script
chmod +x setup-ecs-service.sh

# Esegui lo script (crea ECS cluster, ALB, task definition)
./setup-ecs-service.sh
```

**Cosa crea questo script:**
- ✅ ECS Cluster con Fargate
- ✅ Application Load Balancer
- ✅ Target Group per health checks
- ✅ ECS Task Definition
- ✅ ECS Service

### 3. **Deploy Locale (Test)**

```bash
# Rendi eseguibile lo script
chmod +x deploy-local.sh

# Build e deploy dell'immagine Docker
./deploy-local.sh
```

## 🔐 Configurazione GitHub Secrets

Vai su: `https://github.com/TUO_USERNAME/shared-notes-api/settings/secrets/actions`

Aggiungi questi secrets:

### Obbligatori
- `AWS_ACCESS_KEY_ID`: La tua AWS Access Key
- `AWS_SECRET_ACCESS_KEY`: La tua AWS Secret Key
- `AWS_REGION`: `eu-central-1`

### Opzionali
- `AWS_PROFILE`: `rabbagliettiandrea` (se usi profili specifici)

## 🚀 Deploy Automatico

Il deploy avviene automaticamente quando:
- Push su branch `main`
- Pull request su `main`

### Processo di Deploy
1. **Build**: Crea immagine Docker
2. **Push**: Carica immagine su ECR
3. **Update**: Aggiorna ECS service
4. **Test**: Verifica che l'API risponda

## 🌐 URL del Servizio

Dopo il deploy, l'API sarà disponibile su:
```
http://shared-notes-alb-xxxxxxxxx.eu-central-1.elb.amazonaws.com
```

### Endpoints Disponibili
- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /docs` - API documentation (Swagger)
- `GET /redoc` - API documentation (ReDoc)
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/register` - Registrazione
- `GET /api/v1/notes/` - Lista note
- `POST /api/v1/notes/` - Crea nota

## 🔍 Monitoraggio

### AWS Console
- **ECS**: https://console.aws.amazon.com/ecs/home?region=eu-central-1#/clusters/shared-notes-cluster/services
- **ALB**: https://console.aws.amazon.com/ec2/home?region=eu-central-1#LoadBalancers
- **RDS**: https://console.aws.amazon.com/rds/home?region=eu-central-1#databases
- **ElastiCache**: https://console.aws.amazon.com/elasticache/home?region=eu-central-1#/redis

### CloudWatch Logs
```bash
# Visualizza logs in tempo reale
aws logs tail /ecs/shared-notes-api --follow --profile rabbagliettiandrea --region eu-central-1

# Visualizza logs degli ultimi 30 minuti
aws logs tail /ecs/shared-notes-api --since 30m --profile rabbagliettiandrea --region eu-central-1
```

### Comandi Utili

```bash
# Status del servizio
aws ecs describe-services \
  --cluster shared-notes-cluster \
  --services shared-notes-api-service \
  --profile rabbagliettiandrea \
  --region eu-central-1

# Scale del servizio
aws ecs update-service \
  --cluster shared-notes-cluster \
  --service shared-notes-api-service \
  --desired-count 3 \
  --profile rabbagliettiandrea \
  --region eu-central-1

# Restart del servizio
aws ecs update-service \
  --cluster shared-notes-cluster \
  --service shared-notes-api-service \
  --force-new-deployment \
  --profile rabbagliettiandrea \
  --region eu-central-1
```

## 🛠️ Troubleshooting

### Problema: Service non si avvia
```bash
# Controlla task definition
aws ecs describe-task-definition --task-definition shared-notes-api

# Controlla logs
aws logs describe-log-streams --log-group-name /ecs/shared-notes-api
```

### Problema: Database connection error
- Verifica che RDS sia disponibile
- Controlla security groups
- Verifica secrets in AWS Secrets Manager

### Problema: Redis connection error
- Verifica che ElastiCache sia disponibile
- Controlla security groups
- Verifica secrets in AWS Secrets Manager

### Problema: ALB health check failed
- Verifica che il container risponda su porta 8000
- Controlla security groups
- Verifica target group configuration

## 💰 Costi Stimati (mensili)

- **ECS Fargate**: ~$15-30 (2 tasks)
- **RDS PostgreSQL**: ~$25-50 (db.t3.micro)
- **ElastiCache Redis**: ~$15-30 (cache.t3.micro)
- **ALB**: ~$20-25
- **Data Transfer**: ~$5-15
- **CloudWatch**: ~$5-10
- **VPC**: $0 (usa VPC di default)

**Totale stimato**: ~$85-150/mese (risparmio di ~$20-30/mese usando VPC di default)

## 🔄 Aggiornamenti

### Deploy di Nuove Versioni
```bash
# 1. Modifica il codice
# 2. Commit e push
git add .
git commit -m "Update API"
git push origin main

# 3. Il deploy avviene automaticamente via GitHub Actions
```

### Rollback
```bash
# Torna alla versione precedente
aws ecs update-service \
  --cluster shared-notes-cluster \
  --service shared-notes-api-service \
  --task-definition shared-notes-api:PREVIOUS_REVISION \
  --profile rabbagliettiandrea \
  --region eu-central-1
```

## 🔒 Sicurezza

### Best Practices Implementate
- ✅ Secrets gestiti con AWS Secrets Manager
- ✅ Security Groups con accesso minimo
- ✅ VPC con subnets private per database
- ✅ HTTPS ready (aggiungere certificato SSL)
- ✅ Container non-root user
- ✅ Health checks automatici

### Aggiunte Raccomandate
- [ ] Certificato SSL per HTTPS
- [ ] WAF per protezione web
- [ ] Backup automatici RDS
- [ ] Monitoring avanzato con CloudWatch
- [ ] Auto-scaling basato su CPU/memory

## 📞 Supporto

Se hai problemi:
1. Controlla i logs di CloudWatch
2. Verifica lo status del servizio ECS
3. Controlla i security groups
4. Verifica i secrets in AWS Secrets Manager
5. Consulta la documentazione AWS

---

**Nota**: Ricorda di aggiornare `config.js` nel frontend con l'URL dell'ALB prima del deploy del frontend!
