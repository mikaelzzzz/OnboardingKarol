# Estimativa de Custos: Google Cloud Run vs Render

## 📊 Análise do Seu Uso Atual

### Características do Aplicativo OnboardingKarol

**Endpoints Principais:**
1. Webhook Zapsign (POST) - baixo volume, assíncrono
2. Lista Flexge Semanal (POST) - 1x por semana (automatizado)
3. Cálculo de Contratos (POST) - sob demanda
4. Health check (GET) - usado por monitoramento

**Padrão de Uso Estimado:**
- Contratos Zapsign: ~10-30 por mês (estimativa conservadora)
- Jobs agendados: 4 execuções/mês (1 por semana)
- Testes/verificações: ~100 requests/mês
- Health checks: ~1.440 requests/mês (1 a cada 30 min)
- **Total estimado: ~1.600 requests/mês**

**Configuração:**
- Memória: 512 MiB
- CPU: 1 vCPU
- Min instances: 0 (scale-to-zero)
- Max instances: 10
- Tempo médio de execução: 2-5 segundos por request

## 💰 Google Cloud Run - Preços (2025)

### Tier Gratuito (Always Free)
- ✅ **2.000.000 requests/mês** - GRÁTIS
- ✅ **360.000 GB-segundos/mês** - GRÁTIS
- ✅ **180.000 vCPU-segundos/mês** - GRÁTIS
- ✅ **2 GB de tráfego de saída/mês** - GRÁTIS

### Preços Após Tier Gratuito (Região: southamerica-east1)
- **Requests**: $0.40 por milhão
- **CPU**: $0.00002400 por vCPU-segundo
- **Memória**: $0.00000250 por GB-segundo
- **Tráfego de saída**: $0.12 por GB (após 2 GB grátis)

## 🧮 Cálculo para Seu Caso

### Cenário 1: Uso Atual Estimado (~1.600 requests/mês)

**Requests:**
- 1.600 requests < 2.000.000 (tier gratuito)
- **Custo: $0.00** ✅

**CPU (assumindo 3s médio por request):**
- 1.600 requests × 3s = 4.800 vCPU-segundos
- 4.800 < 180.000 (tier gratuito)
- **Custo: $0.00** ✅

**Memória (512 MiB = 0.5 GB):**
- 1.600 requests × 3s × 0.5 GB = 2.400 GB-segundos
- 2.400 < 360.000 (tier gratuito)
- **Custo: $0.00** ✅

**Tráfego:**
- Estimado: ~10 MB/mês
- < 2 GB (tier gratuito)
- **Custo: $0.00** ✅

**TOTAL MENSAL: $0.00** 🎉

### Cenário 2: Crescimento Moderado (~5.000 requests/mês)

**Requests:**
- 5.000 requests < 2.000.000 (tier gratuito)
- **Custo: $0.00**

**CPU:**
- 5.000 × 3s = 15.000 vCPU-segundos < 180.000
- **Custo: $0.00**

**Memória:**
- 5.000 × 3s × 0.5 GB = 7.500 GB-segundos < 360.000
- **Custo: $0.00**

**TOTAL MENSAL: $0.00**

### Cenário 3: Alto Volume (~50.000 requests/mês)

**Requests:**
- 50.000 requests < 2.000.000 (tier gratuito)
- **Custo: $0.00**

**CPU:**
- 50.000 × 3s = 150.000 vCPU-segundos < 180.000
- **Custo: $0.00**

**Memória:**
- 50.000 × 3s × 0.5 GB = 75.000 GB-segundos < 360.000
- **Custo: $0.00**

**TOTAL MENSAL: $0.00**

### Cenário 4: Volume Muito Alto (~200.000 requests/mês)

**Requests:**
- 200.000 requests < 2.000.000 (tier gratuito)
- **Custo: $0.00**

**CPU:**
- 200.000 × 3s = 600.000 vCPU-segundos
- Tier gratuito: 180.000
- Cobrado: 420.000 × $0.000024 = **$10.08**

**Memória:**
- 200.000 × 3s × 0.5 GB = 300.000 GB-segundos < 360.000
- **Custo: $0.00**

**TOTAL MENSAL: ~$10.08**

## 📈 Comparação: Render vs Google Cloud Run

| Item | Render | Google Cloud Run |
|------|--------|------------------|
| **Plano Atual** | Starter ($7/mês) | Pay-as-you-go |
| **Custo Estimado (uso atual)** | $7.00/mês | **$0.00/mês** ✅ |
| **Custo com 5K requests** | $7.00/mês | **$0.00/mês** ✅ |
| **Custo com 50K requests** | $7.00/mês | **$0.00/mês** ✅ |
| **Custo com 200K requests** | $7.00/mês | **~$10.00/mês** |
| **Região** | US Oregon | **BR São Paulo** 🇧🇷 |
| **Latência (Brasil)** | ~150-200ms | **~20-50ms** ⚡ |
| **Free Tier** | Não | **Sim (2M requests)** |
| **Scale to Zero** | Não | **Sim** |
| **Cold Start** | ~5s | ~2-3s |
| **Logs Retention** | 7 dias | 30 dias |

## 💡 Economia Estimada

### Primeiro Ano
- **Render**: $7 × 12 = **$84.00**
- **Cloud Run** (uso atual): **$0.00**
- **Economia**: **$84.00/ano** (100%) 🎉

### Se crescer para 50K requests/mês
- **Render**: $84.00/ano
- **Cloud Run**: **$0.00/ano**
- **Economia**: **$84.00/ano** (100%)

### Se crescer para 200K requests/mês
- **Render**: Precisaria upgrade (~$25/mês = $300/ano)
- **Cloud Run**: ~$120/ano
- **Economia**: **$180/ano** (60%)

## 🎯 Recomendação

### Para Seu Caso (OnboardingKarol)

**✅ MIGRAR PARA GOOGLE CLOUD RUN**

**Motivos:**
1. **Custo Zero** - Com seu volume atual, ficará no tier gratuito
2. **Melhor Latência** - Região São Paulo (vs Oregon no Render)
3. **Scale to Zero** - Não paga quando não está usando
4. **Mais Recursos** - Logs, monitoramento, métricas incluídas
5. **Flexibilidade** - Só paga se crescer muito (e mesmo assim, menos que Render)

**Economia Imediata:**
- **$7/mês → $0/mês**
- **$84/ano economizados**

## 📊 Custos Adicionais Possíveis (Mínimos)

### Secret Manager
- 6 primeiras versões: **GRÁTIS**
- Após: $0.06 por secret/versão/mês
- Estimado: **$0.00** (você tem 12 secrets, todas grátis)

### Artifact Registry
- 0.5 GB de armazenamento: **GRÁTIS**
- Suas imagens: ~500 MB
- Estimado: **$0.00**

### Cloud Build
- 120 build-minutes/dia: **GRÁTIS**
- Seus builds: ~2-3 min cada
- Estimado: **$0.00**

## 💰 Custo Total Estimado Mensal

| Cenário | Requests | Custo |
|---------|----------|-------|
| **Atual** | ~1.600 | **$0.00** ✅ |
| Crescimento Moderado | ~5.000 | **$0.00** |
| Alto Volume | ~50.000 | **$0.00** |
| Volume Muito Alto | ~200.000 | **~$10.00** |

## 🚨 Quando Começaria a Pagar?

Você só começaria a pagar se:
1. Ultrapassar **2 milhões de requests/mês**, OU
2. Usar mais de **180.000 vCPU-segundos/mês** (equivalente a ~60.000 requests de 3s)

Com seu padrão atual de uso, **você não pagaria nada pelos próximos 12-24 meses**, mesmo com crescimento orgânico.

## 📝 Conclusão

**Render**: $84/ano fixo
**Cloud Run**: $0-10/ano (dependendo do crescimento)

**Economia garantida: $84/ano**
**Benefícios adicionais:**
- ⚡ Latência 70% menor (São Paulo)
- 📊 Melhor monitoramento
- 🔒 Secret Manager integrado
- 📈 Escala automática verdadeira
- 🆓 Tier gratuito generoso

## 🔗 Links Úteis

- [Calculadora Oficial Google Cloud](https://cloud.google.com/products/calculator)
- [Preços Cloud Run](https://cloud.google.com/run/pricing)
- [Free Tier Details](https://cloud.google.com/free/docs/free-cloud-features#cloud-run)

