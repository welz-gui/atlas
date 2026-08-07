# Roadmap de Implementação — Atlas

Documento vivo. Consolida o **roadmap estratégico** do plano (§9 e §10 de
[`PLANO_DE_IMPLEMENTACAO_v2.md`](PLANO_DE_IMPLEMENTACAO_v2.md)) com o **estado
real do código** e o **caminho de execução** de cada estágio.

- Última atualização: **2026-08-07**
- Base avaliada: branch `claude/projeto-embriao-revisao-ncpqry`, 199 testes
- Documentos irmãos: [`REVISAO_ADERENCIA_PLANO_v2.md`](REVISAO_ADERENCIA_PLANO_v2.md)
  (diagnóstico do embrião e backlog das Fases A–C)

---

## Como ler este documento

Há **dois eixos**, e confundi-los já custou tempo neste projeto:

| Eixo | O que é | Onde vive |
|---|---|---|
| **Estágios 0–7** | Recorte de **produto e negócio**. Cada um tem um portão comercial. | §9 e §10 do plano |
| **Fases A, B, C, D…** | Recorte de **execução técnica**. Blocos de trabalho de engenharia. | Este documento e a §6 da revisão |

Uma fase técnica pode atravessar estágios, e foi o que aconteceu: a Fase C
entregou peças dos Estágios 2 e 4 enquanto o Estágio 0 sequer começou. Isso não
foi erro de execução — foi consequência de o backlog ter nascido de uma revisão
de código, não de casos reais. Mas precisa estar escrito, porque muda o que
significa "estar pronto".

Cada estágio abaixo traz sempre a mesma estrutura:

1. **Objetivo** — o que o estágio entrega ao cliente
2. **Já existe** — o que está no código hoje, com caminho de arquivo
3. **Falta** — o recorte pendente
4. **Como implementar** — desenho concreto, não intenção
5. **Ferramentas** — o que usar e o que evitar
6. **Observações** — as armadilhas específicas deste estágio
7. **Portão de saída** — critério do §10 do plano
8. **Métricas** — o que instrumentar (§11)

---

## Estado atual em uma página

**Backend** (FastAPI + SQLAlchemy 2.0 + Alembic, 199 testes):

```
app/
├── ai/            provider (none|anthropic), retrieval (RAG lexical),
│                  schemas (structured outputs), service (grounding + proveniência)
├── api/v1/        auth, projects, regulatory, catalog, protocol, documents,
│                  jobs, plan, daily_log, ai, portal, health
├── core/          config, database, security (argon2id + matriz de permissões)
├── models/        18 tabelas — ver abaixo
├── regulatory/    catalog (Rule, RuleState, motor puro), importer, data/*.yaml
├── services/      storage, antivirus, retention, pdf_parser, regulatory_engine,
│                  pdf_report_generator, report_builder, project_versions
└── workers/       queue (inline|redis), tasks, worker
```

**Tabelas**: `organizations`, `users`, `projects`, `project_versions`,
`documents`, `regulatory_documents`, `regulatory_rules`,
`rule_validation_events`, `analysis_runs`, `validation_records`,
`protocol_processes`, `protocol_requirements`, `protocol_events`,
`ai_interactions`, `job_records`, `eap_items`, `task_items`, `daily_logs`.

**Frontend** (Next.js 14 App Router + TypeScript + Tailwind): `/login`, `/`,
`/projects`, `/approvals`, `/catalog`, `/protocol`, `/documents`, `/plan`,
`/daily-log`, `/ai`, `/portal`. PWA com service worker e fila offline.

**Mapa dos estágios:**

| Estágio | Situação | Bloqueado por |
|---|---|---|
| 0 — Concierge | ⬜ Não iniciado | — |
| 1 — Copiloto de Aprovação | 🟨 Código completo, não liberável | Catálogo não conferido; RLS inativa |
| 2 — Núcleo operacional | 🟨 ~60% construído | Uso em obra real; fotos e inspeções |
| 3 — Custos e campo nativo | ⬜ Nada | Portão 2 |
| 4 — Copiloto de IA | 🟨 ~30% construído | Portão 3 |
| 5 — BIM | ⬜ Nada | Portão 4 |
| 6 — Expansão regulatória | ⬜ Nada | Portão 5 |
| 7 — Preditiva | ⬜ Nada | Portão 6 |

---

## Invariantes — valem em toda fase, sem exceção

Qualquer implementação futura que quebre um destes itens deve ser rejeitada em
revisão de código, ainda que o produto peça o contrário. Todos têm teste.

| # | Invariante | Onde é sustentado |
|---|---|---|
| I1 | Ausência de dado nunca vira veredicto | `regulatory/catalog.py` → `nao_verificavel` |
| I2 | O sistema não inventa medidas | `services/pdf_parser.py` devolve `null` + aviso |
| I3 | Regras são dado, não código | tabela `regulatory_rules` |
| I4 | Fonte legal única — motor, assistente e IA leem o mesmo catálogo | `regulatory/catalog.py` |
| I5 | Nenhuma alteração silenciosa | `ProjectVersion` imutável; §14.15 do plano |
| I6 | Análises são append-only | `AnalysisRun` + `ValidationRecord` |
| I7 | Regra não validada não vai ao cliente | `is_publishable` (§7.5) |
| I8 | A IA propõe; quem publica é gente | `ai/service.py` → `rascunho_extraido_por_ia` |
| I9 | A IA não cita a lei; aponta para o catálogo | contrato pede `rule_key`, conferido |
| I10 | Ausência de verificação não é aprovação | `antivirus.py` → `nao_verificado` |
| I11 | Expurgo apaga o arquivo, nunca o registro | `retention.py` |
| I12 | Isolamento entre organizações responde 404 | `api/deps.py` |
| I13 | Falha de rede não vira dado | `lib/api.ts` lança `ApiError` |
| I14 | Registro offline não é registro salvo | `lib/offline.ts` → *pendente* |

> **Nota sobre I5 nos módulos futuros.** O §14.15 do plano diz "nenhuma
> alteração silenciosa em orçamento, cronograma ou quantitativos". Hoje o
> invariante existe só para parâmetros de projeto. Ao construir os Estágios 3 e
> 5, ele precisa ser **estendido**, não reinventado: o padrão de
> `ProjectVersion` (linha imutável + hash + motivo + autor) é o modelo a copiar.

---

# Estágio 0 — Concierge

> **Situação: não iniciado. É o gargalo real do projeto.**

### Objetivo

Prestar pré-análise **manual** paga, com projetos reais, para validar disposição
a pagar, extrair as regras que de fato importam e medir a taxa de acerto humana
antes de automatizar.

### Já existe

Nada de operação. Do lado técnico, porém, o Estágio 0 hoje tem uma vantagem que
não tinha no plano original: **a ferramenta de apoio já está pronta**. Um
analista pode cadastrar o empreendimento, versionar parâmetros, rodar o motor,
registrar o protocolo e vincular cada exigência do órgão à regra que deveria
tê-la previsto (`GET /projects/{id}/prediction-accuracy`).

### Falta

Tudo o que é operação: selecionar projetos, cobrar, acompanhar protocolo,
comparar análise contra exigências reais, estruturar as regras usadas.

### Como implementar

1. **Selecionar 5 a 10 projetos reais em Lajeado**, de tipologia repetitiva
   (residencial unifamiliar e geminado — as duas do catálogo semente).
2. **Usar o próprio Atlas como ferramenta de trabalho do analista.** Isso muda o
   Estágio 0 em relação ao plano: em vez de planilha, cada análise manual já
   nasce como `AnalysisRun` versionado. O corpus sai estruturado de graça.
3. **Conferir e publicar as regras conforme forem sendo usadas.** A tela
   `/catalog` já exige documento e artigo para publicar. Cada regra publicada
   aqui é uma regra que o Estágio 1 poderá entregar ao cliente.
4. **Registrar toda exigência que o órgão emitir** em
   `POST /protocols/{id}/requirements`, com `linked_rule_key` quando houver
   regra correspondente e `was_predicted` conforme o Atlas tenha ou não
   apontado antes. É isto que transforma recall em medição.
5. **Medir**: tempo por análise, ciclos de notificação, dias até alvará,
   falsos negativos críticos.

### Ferramentas

O Atlas em si. Nada a construir. Se algo faltar durante a operação, isso vira
backlog — e será backlog **derivado de caso real**, que é o ponto do estágio.

### Observações

- **Este estágio não pode ser pulado de novo.** O plano condiciona o
  desenvolvimento a ele (§15.15) e a razão é concreta: as 7 regras hoje no
  catálogo não vieram de nenhum projeto real. A mecânica está madura; o
  conteúdo é suposição.
- **Falso negativo crítico é a métrica que importa.** Precisão alta com um
  bloqueio não detectado é pior que precisão média sem nenhum: o cliente
  protocola confiando e é notificado.
- Não construa mais nada de produto durante este estágio. Se sobrar capacidade
  técnica, use na **Fase D** (dívidas de liberação), descrita adiante.

### Portão de saída (§10)

Projetos pagos, clientes recorrentes, taxa mínima de acerto, dor confirmada e
regras repetitivas suficientes para automação.

### Métricas (§11 — Aprovação)

Ciclos de notificação · dias até alvará · recall de bloqueios · precisão ·
cobertura · não verificáveis · **falsos negativos críticos**.

---

# Estágio 1 — Copiloto de Aprovação + Núcleo Documental

> **Situação: código completo. Não liberável até o catálogo ser conferido.**

### Objetivo

Organizações, usuários, empreendimento, documentos, versões, linha de base,
biblioteca regulatória de Lajeado, regras, checklist, relatório, tramitação,
validação humana, portal básico e QR Code.

### Já existe

| Item do plano | Onde |
|---|---|
| Organizações, usuários, papéis, permissões (§8.1) | `core/security.py`, `api/deps.py` |
| Cadastro de empreendimento completo (§8.2) | `models/domain.py::Project` |
| Gestão documental com versão, hash, QR, bloqueio de obsoleto (§8.3) | `endpoints/documents.py` |
| Pré-análise legal com evidência, fonte, não verificáveis (§8.4) | `services/regulatory_engine.py` |
| Tramitação: protocolo, exigências, prazos, histórico (§8.5) | `endpoints/protocol.py` |
| Controle de versões e linha de base oficial (§8.6, §3.2) | `services/project_versions.py` |
| Catálogo regulatório com estados e vigência (§7.3, §7.4) | `regulatory/catalog.py` |
| Validação humana com responsável identificado (§7.5) | `endpoints/catalog.py` |
| Relatório com ressalvas legais (§12) | `services/pdf_report_generator.py` |
| Portal do cliente (§8.22 — básico) | `endpoints/portal.py` |

### Falta

Três itens, e **nenhum é código de feature**:

1. **Conferir o catálogo contra a legislação publicada de Lajeado.** As 7 regras
   estão em `em_validacao` com `source.article: null`. Enquanto isso durar, todo
   laudo sai marcado como uso interno e o portal do cliente omite o resumo de
   conformidade — o sistema já se comporta corretamente; o que falta é o ato
   humano.
2. **Ativar a RLS.** As políticas existem
   (`alembic/versions/d259cb880f7b_*.py`); falta conectar com usuário sem
   `BYPASSRLS` e emitir `SET LOCAL atlas.organization_id` por transação.
3. **MFA** (§8.1, §12) — hoje inexistente.

### Como implementar (o que resta)

**RLS — o passo que exige código:**

```python
# app/core/database.py — listener de begin na sessão
from sqlalchemy import event, text

@event.listens_for(SessionLocal, "after_begin")
def _set_tenant(session, transaction, connection):
    org = current_organization_id()   # ContextVar preenchida em get_current_user
    if org:
        connection.execute(text("SET LOCAL atlas.organization_id = :org"), {"org": org})
```

A `ContextVar` é preenchida em `api/deps.py::get_current_user` e **precisa ser
limpa** ao fim do request. Nos workers, quem preenche é `run_job`, a partir de
`JobRecord.organization_id`. Testar contra Postgres real, não SQLite — a
política é no-op no SQLite e um teste verde ali não prova nada.

**MFA:** TOTP com `pyotp`, segredo cifrado em repouso, códigos de recuperação
de uso único hasheados como senha. Obrigatório para `owner`, `admin` e
`validator` — quem publica regra e quem gere usuários. Não force para
`inspector`: telefone de canteiro com MFA é atrito que empurra para senha
compartilhada.

### Ferramentas

`pyotp` (TOTP) · Postgres 15+ com PostGIS · Alembic · `pytest` com fixture
Postgres real para os testes de RLS (`testcontainers` ou serviço no CI).

### Observações

- **Não relaxe o `is_publishable` para "destravar" o portal.** A tentação vai
  aparecer na primeira demonstração comercial. O comportamento atual é o
  produto funcionando: ele se recusa a entregar número não conferido.
- O `prediction-accuracy` já existe e devolve `null` quando não há vínculo, em
  vez de estimar. Mantenha assim — recall inventado é pior que recall ausente.
- A migration de RLS falha fechado por desenho: sem `SET LOCAL`, nega tudo.
  Isso vai parecer bug na primeira execução. Não é.

### Portão de saída (§10 — Portão 1 → 2)

Clientes ativos, relatórios aceitos, motor com cobertura mínima e tempo de
análise reduzido.

---

# Estágio 2 — Núcleo operacional

> **Situação: ~60% construído, à frente do cronograma do plano.**

### Objetivo

EAP, tarefas, pendências, diário, fotos, inspeções, PWA, painel diário, portal
do cliente e **uso em obra real**.

### Já existe

| Item | Onde | Observação |
|---|---|---|
| EAP (§8.8) | `models::EAPItem`, `/plan` | Estrutura básica: código, nome, progresso, pai |
| Tarefas (§8.13) | `models::TaskItem`, Kanban em `/plan` | Sem dependências nem recorrência |
| Pendências | `ProtocolRequirement` | Vem da tramitação |
| Diário (§8.12) | `models::DailyLog`, `/daily-log` | Texto, clima, efetivo, ocorrências |
| PWA (§6.2) | `public/sw.js`, `lib/offline.ts` | Fila offline para diário e tarefas |
| Portal do cliente (§8.22) | `endpoints/portal.py` | Andamento, documentos, tramitação |

### Falta

| Item | Recorte |
|---|---|
| **Fotos e mídia (§8.14)** | Captura, compressão, classificação por ambiente/serviço, anotação, vínculo com diário e tarefa |
| **Inspeções e qualidade (§8.15)** | Checklists, critérios, tolerâncias, não conformidade, reinspeção, bloqueio controlado |
| **Áudio no diário (§3.7)** | O plano prevê áudio offline; hoje só texto |
| **Painel diário** | Visão de "o que importa hoje" por obra |
| **EAP completa (§8.8)** | Predecessoras, critérios de conclusão, entregáveis, responsáveis |
| **Tarefas completas (§8.13)** | Dependências, evidências, aprovação, recorrência, escalonamento |
| **Assinatura do diário (§8.12)** | Hoje o campo `status` diz "assinado" sem que nada assine |

### Como implementar

**Fotos e mídia** — é onde o storage abstraído da Fase C paga:

```python
class MediaAsset(Base):
    __tablename__ = "media_assets"
    id, organization_id, project_id
    storage_key, storage_backend        # reusa app/services/storage.py
    kind                                # foto | audio | video
    captured_at                         # do EXIF, não do upload
    latitude, longitude                 # do EXIF quando houver
    eap_item_id, task_id, daily_log_id  # vínculos opcionais
    ambiente, servico                   # classificação
    hash_sha256, size_bytes
    antivirus_status                    # mesmo contrato dos documentos
```

Compressão **no cliente** antes do upload (`browser-image-compression` ou
`canvas` puro): uma foto de 12 MP em rede de canteiro não sobe. Guarde a
original e uma miniatura; o portal do cliente serve a miniatura.

**Atenção ao EXIF:** `captured_at` deve vir do metadado da foto, não do momento
do upload — uma foto tirada offline às 9h e enviada às 18h precisa constar como
9h no diário. E **remova GPS antes de servir ao cliente** se a política de
privacidade da obra exigir; guarde no registro interno.

**Inspeções** — o modelo mental é o do catálogo regulatório, e vale reaproveitar
o vocabulário:

```python
class InspectionTemplate(Base):    # checklist versionado, como regra
    id, organization_id, name, version, state   # rascunho | vigente | revogada
class InspectionCriterion(Base):
    template_id, description, tolerance, evidence_required, severity
class Inspection(Base):
    project_id, template_id, template_version, eap_item_id
    inspector_id, performed_at, result           # conforme | nao_conforme | nao_verificavel
class InspectionFinding(Base):
    inspection_id, criterion_id, result, notes, media_asset_ids
    corrected_at, reinspection_id                # cadeia de reinspeção
```

Note o `nao_verificavel` e o `template_version`: são os mesmos princípios I1 e
I5 aplicados à qualidade. Uma inspeção precisa dizer **qual versão do checklist**
foi aplicada, senão a comparação entre inspeções de meses diferentes mente.

**Áudio offline:** `MediaRecorder` grava para IndexedDB; a fila de
`lib/offline.ts` ganha o tipo `media`, com envio por `multipart` e o mesmo
`client_token` de idempotência. Transcrição **não** entra aqui — é Estágio 4.

**Assinatura do diário:** hoje `status="assinado"` é literal falso. Ou implemente
assinatura de verdade (hash do conteúdo + identidade + timestamp, com o registro
tornando-se imutável depois), ou renomeie o estado para `fechado`. A segunda
opção é legítima e honesta; a primeira é a que o §8.12 pede.

### Ferramentas

`browser-image-compression` ou canvas · `exifr` (leitura de EXIF no cliente) ·
`MediaRecorder` API · `Pillow` no backend para miniaturas · TanStack Query
(o plano pede em §6.1 e ainda não está em uso — vale adotar agora, antes de as
telas de obra multiplicarem o estado manual).

### Observações

- **Este estágio só termina com obra real usando diariamente.** Código pronto
  não fecha o Estágio 2; adesão de campo fecha. O plano é explícito no Portão
  2 → 3.
- **Não construa quantitativos nem orçamento aqui**, por mais que a EAP peça.
  É Estágio 3 e depende de portão.
- A fila offline hoje cobre diário e tarefas. Ao adicionar mídia, o volume muda
  de ordem de grandeza — considere limite de tamanho da fila e política de
  descarte **explícita e visível** ao usuário, nunca silenciosa (I14).

### Portão de saída (§10 — Portão 2 → 3)

Obras usando diariamente, adesão de campo, informações úteis e baixa dependência
de planilhas.

### Métricas (§11 — Gestão)

Tempo de diário · adesão · tarefas concluídas · uso de versão vigente ·
planilhas paralelas.

---

# Estágio 3 — Custos, planejamento e campo nativo

> **Situação: nada construído. É o maior estágio do plano.**

### Objetivo

Quantitativos, orçamento, cronograma, compras, fornecedores, financeiro,
contratos, medições, incorporação, app nativo e engine de sincronização.

### Já existe

Nada dos módulos. A base que eles vão usar existe: multiempresa, versionamento,
linha de base, EAP, workers e storage.

### Falta

Módulos §8.9 a §8.11 e §8.16 a §8.21, §8.26, mais o app nativo (§6.3).

### Como implementar

**Ordem sugerida** — cada um habilita o seguinte:

```
Quantitativos (§8.9)
    └── Orçamento (§8.10)
            ├── Cronograma (§8.11) ─── físico-financeiro
            ├── Compras (§8.16) ── Fornecedores (§8.17) ── Estoque (§8.18)
            └── Contratos e medições (§8.20) ── Financeiro (§8.19)
                    └── Incorporação (§8.26)
```

**Quantitativos** — o ponto de atenção é a proveniência, e ela repete o padrão
já usado na extração de PDF:

```python
class Quantity(Base):
    project_version_id                  # SEMPRE amarrado à versão, nunca ao projeto
    eap_item_id, description, unit, amount
    origin        # manual | planilha | ifc | pdf_assistido
    evidence      # memória de cálculo, referência à prancha, elemento IFC
    loss_percent
    validated_by_id, validated_at
```

Um quantitativo sem origem declarada é um número órfão. `origin` não deve ter
valor padrão que esconda ignorância — se veio de planilha, diga planilha.

**Orçamento** — insumos, composições, BDI, curva ABC. Base de preços: SINAPI
como referência inicial (dado público, atualizado mensalmente pela Caixa). Trate
a base de preços **como o catálogo regulatório**: dado versionado com vigência,
não constante em código. A mesma lição, o mesmo modelo.

**Cronograma** — Gantt, CPM, caminho crítico. Implementar CPM próprio é viável e
previsível (grafo acíclico dirigido + passagem para frente/para trás); o que
custa é a interface. Não escreva um Gantt do zero.

**Grafo de propagação de impacto (§8.7)** — este é o módulo que o plano chama de
central (§14.12), e ele nasce **aqui**, não depois:

```
Nós:    elemento de projeto · quantitativo · item de orçamento · atividade
        · compra · contrato · medição · fluxo de caixa
Arestas: automatica | proposta | manual
Fluxo:   detectar alteração → localizar dependências → marcar impactos
         → gerar proposta → calcular deltas → aprovar item a item
         → publicar nova versão
```

**"Aprovar item a item" é o coração e não pode ser abreviado.** Uma alteração de
projeto que recalcule orçamento sozinha viola o §14.15 e o invariante I5. O grafo
propõe; a pessoa aprova; a aprovação publica uma versão nova. Modele a proposta
como entidade (`ImpactProposal`) com estados, exatamente como `RegulatoryRule`.

**App nativo (§6.3)** — só depois de o uso de campo estar validado (Portão 2).
Antes de escrever sincronização artesanal, avaliar **PowerSync**, **ElectricSQL**
ou **WatermelonDB**, como o plano manda em §6.3. Sincronização bidirecional com
resolução de conflito é um problema resolvido; reimplementá-lo consome um
trimestre e produz bugs sutis de perda de dado.

### Ferramentas

**Backend:** `networkx` (grafo de impacto e CPM) · `pandas` (importação de
planilha) · SINAPI como base de preços.
**Frontend:** `frappe-gantt` ou `dhtmlx-gantt` (avaliar licença) · TanStack Table
para planilhas densas · `handsontable` só se a edição tipo-planilha for exigida
(licença comercial).
**Mobile:** Flutter ou React Native/Expo + PowerSync/ElectricSQL/WatermelonDB.

### Observações

- **Este é o estágio onde o produto vira ERP** — e o §2 do plano avisa que
  competir como "mais um ERP de obra" não é a estratégia. Construa o mínimo que
  sustenta a continuidade da linha de base, não a paridade de features.
- **Incorporação (§8.26) foi incluída para atender a Delta** (§14.13). Confirme
  que a demanda continua de pé antes de investir: VGV, patrimônio de afetação,
  distratos e RET são um subsistema inteiro.
- **Não deixe orçamento e cronograma referenciarem o projeto**; devem
  referenciar a **linha de base oficial** (§3.2). É a diferença entre um
  orçamento auditável e um orçamento que ninguém sabe de qual versão saiu.

### Portão de saída (§10 — Portão 3 → 4)

Dados estruturados suficientes, uso recorrente e custo operacional controlado.

### Métricas (§11 — Custos)

Desvio · compras emergenciais · custo comprometido · margem · previsão final.

---

# Estágio 4 — Copiloto de IA

> **Situação: ~30% construído. A infraestrutura está pronta; falta a aplicação.**

### Objetivo

Transcrição, reuniões, RAG, assistente, priorização, comparação de revisões,
extração de tarefas e relatórios.

### Já existe

| Item | Onde |
|---|---|
| Camada multi-provider (§6.8) | `ai/provider.py` — `none` \| `anthropic` |
| Structured outputs validados por Pydantic | `ai/schemas.py` |
| RAG sobre o catálogo | `ai/retrieval.py` (lexical) |
| Cache por hash | `ai/service.py` |
| Registro de proveniência | tabela `ai_interactions` |
| Assistente normativo | `POST /ai/chat` |
| Rascunho de regra por IA | `POST /ai/rule-drafts` (§7.8 Nível 2, parcial) |

### Falta

| Item | Recorte |
|---|---|
| **Transcrição e reuniões (§8.24)** | Gravação, transcrição, resumo, decisões, tarefas, ata |
| **Extração de tarefas** | De ata, de e-mail, de notificação do órgão |
| **Comparação de revisões** | Diff entre versões de projeto e entre pranchas |
| **Priorização / copiloto diário (§8.25)** | Prioridades, atrasos, riscos, recomendações |
| **Roteamento por tarefa (§6.8)** | Modelo barato para classificação, caro para extração |
| **pgvector** | Hoje a recuperação é lexical |
| **OCR** | PDF digitalizado não é extraível |

### Como implementar

**Transcrição** — trabalho de fila, nunca de request. Adicione o tipo em
`workers/tasks.py`:

```python
@register(JobType.TRANSCRICAO)
def transcribe(db, record):
    # áudio vem do storage (MediaAsset), resultado é append-only
```

Provedor: **Whisper** local (`faster-whisper`, roda em CPU aceitavelmente para
português) ou API. A transcrição bruta é dado; o resumo é interpretação. Guarde
os dois separados, com a transcrição imutável — uma ata revisada não pode apagar
o que foi dito.

**Extração de tarefas de ata** — reusa exatamente o padrão de
`extract_rule_drafts`: structured output Pydantic, saída em estado de rascunho,
pessoa aprova. Uma tarefa criada por IA que já nasce atribuída a alguém com
prazo é uma tarefa que ninguém aceitou.

**Comparação de revisões** — dois níveis:
1. **Paramétrico**: já é trivial hoje, `ProjectVersion` guarda tudo. Um diff de
   campos com `content_hash` para provar que a versão não mudou.
2. **Gráfico**: sobreposição de pranchas. `PDF.js` para render, `OpenCV` para
   alinhamento e diferença. Sem promessa de detecção semântica — mostre a
   diferença visual e deixe a leitura com o técnico.

**Roteamento por tarefa (§6.8)** — hoje `AI_MODEL` é uma constante única.
Evolua para mapa por finalidade:

```python
AI_MODELS = {
    "consulta_normativa": "claude-opus-5",     # precisa raciocinar sobre o catálogo
    "classificacao_documento": "claude-haiku-4-5",   # barato, alto volume
    "extracao_de_regra": "claude-opus-5",       # o erro aqui é caro
    "resumo_de_ata": "claude-sonnet-5",
}
```

Meça custo por análise e por obra (§11 — IA) desde a primeira chamada;
`ai_interactions` já guarda tokens de entrada e saída.

**pgvector** — só quando a busca lexical errar de forma medível. O gatilho: taxa
de consultas com `retrieved_rule_keys` vazio mas com regra pertinente no
catálogo. A interface `retrieve()` não muda; troque o corpo.

**OCR** — `ocrmypdf` (que embrulha o Tesseract) como worker. A saída precisa ser
marcada com `origin: ocr` e confiança; texto de OCR alimentando extração de
parâmetro sem essa marca reintroduz o problema que a Fase A resolveu.

### Ferramentas

`faster-whisper` ou API de transcrição · `ocrmypdf` + Tesseract (`por`) ·
`pgvector` + `sentence-transformers` (ou embeddings de API) · `OpenCV` para
sobreposição · `PDF.js` no cliente.

### Observações

- **Os invariantes I8 e I9 valem para todo recurso novo de IA.** Uma tarefa
  extraída de ata nasce como proposta; um resumo de reunião não vira decisão.
- **`ai_interactions` cresce rápido.** Defina retenção para o corpo das
  respostas (`response_json`) mantendo a proveniência — mesmo padrão do §6.6:
  expurga o conteúdo, preserva o registro.
- **Custo é métrica de produto, não de infraestrutura.** Uma análise que custa
  mais que a margem do serviço não é um problema técnico.

### Portão de saída (§10 — Portão 4 → 5)

Demanda real por BIM, disponibilidade de IFC e dados consistentes.

### Métricas (§11 — IA)

Taxa de aceitação · custo por obra · custo por análise · correções humanas ·
tempo economizado.

---

# Estágio 5 — BIM e propagação avançada

> **Situação: nada construído.**

### Objetivo

IFC, visualizador, quantitativos, elementos, grafo de impacto, integração com
orçamento e cronograma, revisão automática proposta.

### Como implementar

**Extração IFC** — `IfcOpenShell` em worker. O IFC é o formato preferencial do
§3.6 justamente porque traz o quantitativo com semântica: parede é parede, com
área e material. Extraia elementos para tabela própria (`bim_elements`), com
GUID do IFC como chave estável entre revisões — é o que permite dizer "esta
parede mudou" em vez de "algo mudou".

**Visualizador** — `xeokit` ou `IFC.js` no cliente. Converta para formato de
streaming (xeokit XKT) em worker; não sirva IFC bruto ao navegador.

**Grafo de impacto avançado** — se o grafo do Estágio 3 foi construído
corretamente, aqui é só acrescentar o nó `elemento de projeto` como origem das
arestas. Se não foi, este é o estágio em que a dívida cobra.

**DWG fica adiado** (§6.9) até haver demanda paga e licença adequada. `ezdxf`
cobre DXF, que é o caminho aberto.

### Ferramentas

`IfcOpenShell` · `xeokit` (converter XKT) ou `IFC.js` · `ezdxf` (DXF) ·
`Shapely`, `GDAL`, `PostGIS` para geometria.

### Observações

- **Não prometa quantitativo automático confiável.** Um IFC mal modelado produz
  quantitativo errado com aparência de precisão. Marque `origin: ifc` e exija
  validação humana, como todo o resto (I8).
- Processamento de IFC é pesado: worker dedicado, fila própria
  (`--queue bim`), e limite de tamanho explícito.

### Portão de saída (§10 — Portão 5 → 6)

Método regulatório validado, custo por município conhecido e rede de validação
possível.

---

# Estágio 6 — Expansão regulatória

> **Situação: nada construído. É o que transforma o produto em plataforma.**

### Objetivo

Novos municípios, coleta automática, monitoramento, rede de validadores,
acessibilidade aprofundada, PPCI e novas tipologias.

### Já existe

O **catálogo** (§7.2) e o **validador técnico** (§7.5) — construídos na Fase B —
e o **extrator** parcial (§7.8 Nível 2), da Fase C. Faltam os dois extremos do
subsistema: o coletor e o monitor.

### Falta

| Componente (§7.2) | Recorte |
|---|---|
| **Coletor regulatório** | Localizar fontes oficiais: prefeitura, Câmara, portal de legislação, diário oficial, geosserviços, Bombeiros |
| **Monitor regulatório** | Detectar novas leis, alterações, revogações, links quebrados |
| **PPCI** | Corpo de Bombeiros — norma estadual, lógica distinta do plano diretor |
| **Acessibilidade aprofundada** | NBR 9050 além da verificação documental atual |
| **Rede de validadores (§7.9)** | Revisão dupla, remuneração por regra, biblioteca certificada |

### Como implementar

**Coletor** — trabalho agendado por município:

```python
class RegulatorySource(Base):
    jurisdiction, kind        # prefeitura | camara | diario_oficial | geosservico
    url, selector             # como localizar o conteúdo na página
    last_checked_at, last_hash
    state                     # ativa | indisponivel | quebrada
```

O `last_hash` é o mecanismo do monitor: mudou o hash, a fonte mudou. **Fonte
indisponível é estado, não erro** — `RegulatoryDocumentState` já prevê
`indisponivel` (§7.3). Um link quebrado precisa aparecer na fila de trabalho de
alguém, não sumir em log.

**Monitor** — quando uma fonte muda, as regras derivadas dela viram
**potencialmente afetadas**. O §7.2 é explícito: marcar, suspender quando
necessário, encaminhar para revisão. Isso significa uma transição nova em
`ALLOWED_TRANSITIONS` (`vigente → suspensa` já existe) disparada por evento, com
`RuleValidationEvent` registrando que foi o monitor, não uma pessoa.

**Suspensão preventiva é decisão de produto com consequência:** uma regra
suspensa sai do motor e derruba a publicabilidade dos laudos que a usam. É o
comportamento correto — mas avise o cliente antes que ele descubra pelo laudo.

**Novo município** — o custo por município é a métrica que decide se o negócio
escala (§11 — Regulação). Instrumente desde o primeiro: tempo de cadastro, tempo
de manutenção, regras vigentes, cobertura.

### Ferramentas

`httpx` + `selectolax` ou `BeautifulSoup` (coleta) · `playwright` só para portais
que exigem JavaScript (custo alto, use por exceção) · agendamento pelos workers
já existentes (`--queue regulatorio`) · `difflib` / hash por seção para detectar
o que mudou dentro de um documento.

### Observações

- **Respeite `robots.txt` e termos de uso dos portais públicos.** Dado público
  não é dado de coleta irrestrita; ritmo agressivo derruba acesso e queima a
  fonte.
- **O coletor não publica nada.** Ele descobre e baixa; o extrator propõe; a
  pessoa valida (I8). O Nível 3 do §7.8 é "monitoramento autônomo", não
  "publicação autônoma".
- **PPCI é outro domínio.** Norma estadual do Corpo de Bombeiros, com lógica de
  saídas, carga de incêndio e compartimentação que não cabe no formato de regra
  paramétrica atual. Espere estender o schema de `check`.

### Portão de saída

Método regulatório validado, custo por município conhecido, rede de validação
operante.

### Métricas (§11 — Regulação)

Tempo de cadastro · tempo de manutenção · regras vigentes · alterações
detectadas · regras suspensas · cobertura por município.

---

# Estágio 7 — Inteligência preditiva

> **Situação: nada construído. Depende de volume de dado que ainda não existe.**

### Objetivo

Previsão de atraso, custo final, produtividade, risco, visão computacional,
tendências e benchmarking.

### Como implementar

Não comece por modelo. Comece por **dataset**: previsão de atraso exige
cronograma real versus executado em dezenas de obras; custo final exige
orçamento versus realizado com a mesma granularidade. Se os Estágios 2 e 3
gravarem esses dados com proveniência, o Estágio 7 é análise; se não, é
adivinhação com aparência estatística.

**Ordem sensata:** benchmarking (compara o que já se tem) → tendências →
previsão de atraso → custo final → visão computacional (a mais cara e a de menor
retorno inicial).

### Observações

- **Previsão é afirmação sobre o futuro e cai sob o mesmo regime dos
  invariantes.** Uma previsão precisa expor intervalo de confiança e base
  amostral. "Atraso previsto: 18 dias" sem dizer "com base em 4 obras" é o
  mesmo defeito do laudo que afirma validade oficial.
- **Benchmarking entre organizações é dado sensível.** Isolamento por tenant
  (I12) e LGPD (§12) valem aqui com força maior: agregado anonimizado, nunca
  comparação nominal sem consentimento explícito.

---

# Fases de execução — registro

### Fase A — Correções de risco ✅ (2026-08-06)

Seis bloqueadores de risco legal: dados fabricados no extrator, afirmação de
validade oficial no laudo, citações legais conflitantes, upload sem sanitização,
mocks no frontend, ausência de README. Suíte: 8 → 51.

### Fase B — Núcleo do Estágio 1 ✅ (2026-08-06)

Autenticação argon2id, multiempresa com 404 entre tenants, Postgres + Alembic,
catálogo em banco com estados, `ProjectVersion` imutável, linha de base oficial,
validação humana, cadastro completo, tramitação com recall. Suíte: 51 → 110.

### Fase C — Consolidação ✅ (2026-08-07)

Storage abstraído com retenção e antivírus, filas com banco como fonte da
verdade, camada de IA com RAG e proveniência, PWA com fila offline, portal do
cliente. Suíte: 110 → 199.

**Quatro decisões que divergiram do plano, com a razão:**

| Decisão | Plano dizia | Fizemos | Por quê |
|---|---|---|---|
| Filas | Dramatiq ou Celery (§6.7) | Redis puro + estado no Postgres | O registro precisa existir no banco por auditabilidade (§3.5); com o estado lá, o broker carrega um UUID e um framework é peso morto. Redis reiniciado não perde trabalho |
| RAG | pgvector (§6.8) | Recuperação lexical com sinônimos | Dezenas de regras por jurisdição; índice vetorial seria infra a manter sem ganho medido. `retrieve()` não muda quando trocar |
| Citação legal | — | IA devolve `rule_key`, nunca artigo | Não bastava instruir o modelo a não inventar; era preciso que não houvesse por onde |
| Offline | "funções essenciais de campo" (§3.7) | Lista explícita do que **recusa** offline | Veredicto sobre catálogo desatualizado é pior que ausência de veredicto |

---

# Fase D — Liberação do Estágio 1 (proposta)

Recorte para rodar **em paralelo ao Estágio 0**, sem construir feature nova.
Tudo aqui é dívida que impede liberar o que já existe.

| # | Item | Esforço | Por quê agora |
|---|---|---|---|
| D1 | **Ativar RLS** com `SET LOCAL` por transação + fixture Postgres real no CI | M | Segunda linha de defesa que hoje não defende nada |
| D2 | **MFA (TOTP)** para `owner`, `admin`, `validator` | M | §8.1 e §12; quem publica regra precisa de segundo fator |
| D3 | **Conferir e publicar o catálogo de Lajeado** | G | Operação, não código. É o que libera laudo e portal |
| D4 | **Assinatura real do diário** ou renomear `assinado` → `fechado` | P | Hoje o estado afirma algo que não aconteceu |
| D5 | **Instrumentar métricas §11** (aprovação e IA) em endpoint próprio | M | Sem isso o Portão 0 → 1 é opinião |
| D6 | **Teste de integração real** de storage S3 e clamd | P | Hoje há teste de contrato, não de integração |
| D7 | **Retenção de `ai_interactions`** e `job_records` | P | Ambas crescem sem limite |
| D8 | **Adotar TanStack Query** no frontend | M | §6.1; antes de as telas de obra multiplicarem estado manual |

**Não entra na Fase D:** fotos, inspeções, quantitativos, orçamento. São
Estágios 2 e 3 e dependem de portão.

---

# Dívidas técnicas conhecidas

| Dívida | Impacto | Onde |
|---|---|---|
| RLS inativa | Isolamento depende só do filtro de aplicação | `alembic/.../d259cb880f7b` |
| Sem MFA, sem refresh token | Sessão de 7 dias, fator único | `core/security.py` |
| Sem OCR | PDF digitalizado não é extraível | `services/pdf_parser.py` |
| Sem IFC/DXF/BIM | §3.6 parcial | — |
| Coletor e monitor ausentes | Catálogo alimentado à mão | §7.2 |
| RAG lexical | Degrada com catálogo grande | `ai/retrieval.py` |
| Fila offline sem mídia | Fotos não sincronizam | `lib/offline.ts` |
| S3 e clamd sem teste de integração | Contrato testado, integração não | `tests/test_storage.py` |
| `ai_interactions` e `job_records` sem retenção | Crescimento sem limite | — |
| `EAPItem` sem predecessoras | EAP incompleta para §8.8 | `models/domain.py` |
| Diário "assinado" sem assinatura | Estado afirma o que não houve | `models::DailyLog` |
| Sem TanStack Query/Table, sem shadcn/ui | Divergência do §6.1 | `frontend/` |

---

# O que **não** fazer agora

Registrado porque cada item já foi tentação em algum momento:

1. **Não relaxar `is_publishable`** para destravar demonstração comercial.
2. **Não construir orçamento** antes do Portão 2 — é o caminho de virar ERP
   genérico, que o §2 descarta.
3. **Não escrever sincronização mobile artesanal** — avalie PowerSync/Electric
   primeiro (§6.3).
4. **Não trocar por pgvector** sem medir falha da busca lexical.
5. **Não deixar a IA publicar nada**, em nenhuma circunstância, por nenhum
   parâmetro de configuração (I8).
6. **Não pular o Estágio 0 de novo.**

---

# Referências

- [`PLANO_DE_IMPLEMENTACAO_v2.md`](PLANO_DE_IMPLEMENTACAO_v2.md) — plano original
- [`REVISAO_ADERENCIA_PLANO_v2.md`](REVISAO_ADERENCIA_PLANO_v2.md) — diagnóstico
  do embrião, Fases A–C detalhadas
- [`../README.md`](../README.md) — como rodar, princípios, limites conhecidos
