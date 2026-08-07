# Revisão de Aderência — Projeto Embrião Atlas vs. Plano de Implementação v2

Data da revisão: 2026-08-06
Commit revisado: `35f19e0`
Escopo: `backend/`, `frontend/`, `docker-compose.yml`, testes.

> **Situação em 2026-08-06 — Fases A, B e C concluídas.**
> Os 21 itens do backlog (§6) foram implementados. Os seis bloqueadores de
> risco legal do §4.1 e os desvios estruturais do §4.2 estão resolvidos e
> cobertos por teste de regressão (suíte: 8 → 199 testes). O diagnóstico abaixo
> é preservado como registro do estado original; as tabelas de status na §6
> indicam o que foi feito em cada fase.
>
> **O que ainda falta não é código, é operação.** Dois pontos travam a
> declaração do Estágio 1 e nenhum deles se resolve programando:
>
> 1. **A validação humana do catálogo.** Nenhuma regra foi conferida contra a
>    legislação publicada de Lajeado. O sistema já recusa publicar sem
>    documento e artigo, marca laudo como uso interno e omite o resumo no
>    portal do cliente — mas a conferência em si depende de um responsável
>    técnico sentar com a lei.
> 2. **A ativação da RLS.** As políticas existem; falta conectar com usuário
>    sem `BYPASSRLS` e definir `SET LOCAL atlas.organization_id` por transação.
>
> Some-se a isso o **Portão 0** (§14.1, §15.15): as regras hoje no catálogo não
> vieram de casos reais. A mecânica está pronta; o conteúdo continua incerto.

---

## 1. Sumário executivo

O embrião entrega um **protótipo vertical funcional e coerente** do Copiloto de Aprovação:
FastAPI + SQLAlchemy 2.0 + Next.js 14, com motor de regras de Lajeado/RS, laudo PDF,
upload com hash SHA-256, EAP/Kanban e diário de obra. A suíte de 8 testes passa.

Como demonstração, funciona. Como base para o Estágio 1 do plano, **ainda não atende**
aos princípios de arquitetura das seções 3.1 a 3.6, que são exatamente os pontos caros
de retrofit depois: multiempresa, linha de base versionada, regras como dado, e
auditabilidade.

Há também **três defeitos de risco legal** que devem ser corrigidos antes de qualquer
uso com cliente real (detalhados em §4.1): dados fabricados no extrator, afirmação de
validade oficial no laudo, e citações legais conflitantes entre o motor e a IA.

Veredito: **manter o código como esqueleto, refatorar o núcleo antes de somar features.**

---

## 2. Inventário do que foi executado

### Backend (`backend/`)

| Camada | Implementado |
|---|---|
| Config | `app/core/config.py` (Pydantic Settings), `app/core/database.py` (engine + `get_db`) |
| Modelos | `Organization`, `User`, `Project`, `Document`, `EAPItem`, `TaskItem`, `DailyLog`, `ValidationRecord` |
| Schemas | Pydantic v2 completos para os modelos acima |
| Endpoints | `health`, `projects` (org + projeto CRUD parcial), `regulatory` (evaluate / validations / report PDF), `documents` (upload + extract), `plan` (EAP + tasks), `ai` (chat), `daily_log` |
| Serviços | `regulatory_engine.py` (7 regras Lajeado), `pdf_parser.py` (regex sobre quadro de áreas), `pdf_report_generator.py` (ReportLab) |
| Dados | `seed.py` com organização, usuário, 2 projetos, EAP, tarefas, diários |
| Testes | 8 testes, todos passando (`pytest tests/ -q`) |

### Frontend (`frontend/`)

Next.js 14 App Router, Tailwind, lucide-react. 7 páginas: `/` (dashboard), `/projects`,
`/approvals`, `/documents`, `/plan`, `/daily-log`, `/ai`. Cliente HTTP tipado em
`lib/api.ts` com *fallback* silencioso em caso de backend indisponível.

### Infra

`docker-compose.yml` com `postgis/postgis:15-3.3` e `redis:7-alpine`.

---

## 3. O que está OK (manter)

1. **Separação motor determinístico × IA.** O plano (§3.3/§3.4) exige que a verificação
   legal seja regra estruturada e que a IA seja apenas assistiva. A arquitetura já separa
   `regulatory_engine.py` de `endpoints/ai.py`. O princípio está certo; falta o rigor.
2. **Estado `nao_verificavel` existe e é de primeira classe** (§7.7). A regra de
   acessibilidade retorna `None` → `nao_verificavel`. Alinhado ao plano.
3. **Hash SHA-256 no upload de documento** (`documents.py:33`) — §6.6 pede exatamente isso.
4. **Modelagem `ValidationRecord` com `expected`/`actual`/`source_citation`** — o esqueleto
   correto de um registro de conformidade auditável.
5. **Stack aderente ao §6.4/§6.1** nas escolhas de base: FastAPI + Pydantic + SQLAlchemy;
   Next.js + TypeScript + Tailwind.
6. **Monólito modular com `api/v1/endpoints` por domínio** — §6.4 pede monólito modular.
7. **Cobertura de teste no motor de regras** — o componente mais crítico é o único com
   testes de conformidade e não conformidade.
8. **Lajeado/RS como jurisdição piloto** com código IBGE `BR-RS-4311403` — §14.2.

---

## 4. O que precisa ser alterado

### 4.1 Bloqueadores — risco legal / de confiança (corrigir primeiro)

**B1. O extrator fabrica medidas quando a extração falha.**
`services/pdf_parser.py:118-128` — se o texto extraído for vazio ou curto, o parser
**injeta um quadro de áreas fictício** (`Área do Terreno: 450,00 m²`, `Recuo Frontal: 4,50 m`…)
e retorna como se fosse leitura do documento do cliente. Agravante: `pypdf` **não está em
`requirements.txt`**, então o `import` em `pdf_parser.py:105` sempre falha e todo PDF real
cai no caminho fabricado.
→ Remover o bloco de *fallback*. Extração sem evidência deve retornar
`status: nao_verificavel` e confiança 0, nunca um número.

**B2. O laudo PDF afirma validade oficial que não possui.**
`services/pdf_report_generator.py:160-161` imprime, fixo, `Linha de Base Oficial: SIM` e
*"Este laudo possui validade técnica para protocolo junto à Secretaria de Planejamento do
Município de Lajeado/RS"*. Isso é falso e contradiz o §12, que exige aviso de **não
substituição do responsável técnico**, limitação de responsabilidade, confiança e lista de
não verificáveis.
→ Remover a afirmação; adicionar bloco obrigatório de ressalvas; ler `is_official_baseline`
do projeto em vez de fixar `SIM`.

**B3. Citações legais conflitantes entre motor e IA.**
O mesmo parâmetro é atribuído a artigos diferentes nos dois módulos:

| Parâmetro | `regulatory_engine.py` | `endpoints/ai.py` |
|---|---|---|
| Recuo frontal | Plano Diretor, Art. 45 (l. 14) | Código de Edificações, Art. 42 (l. 22) |
| Recuo fundos | Plano Diretor, Art. 46 (l. 34) | Código de Edificações, Art. 45 (l. 24) |
| Taxa de ocupação | Tabela de Zoneamento Z2 (l. 24) | Plano Diretor, Art. 35 (l. 23) |
| Permeabilidade | Código de Edificações, Art. 38 (l. 44) | Código Ambiental, Art. 50 (l. 25) |
| Vagas | Código de Edificações, Art. 55 (l. 64) | Lei de Zoneamento, Art. 60 (l. 26) |

Além disso divergem na aplicabilidade (recuo de fundos: o motor aplica a toda Z2, a IA
diz "até 2 pavimentos") e no valor (permeabilidade: 15% no motor, "15% ou 20%" na IA).
Nenhum dos números foi verificado contra a legislação real.
→ Fonte única da verdade: as citações devem vir **do catálogo regulatório**, não de
strings duplicadas. Enquanto não houver validação humana da lei real, marcar as regras
como `rascunho` e bloquear sua emissão em laudo (§7.5).

**B4. O carimbo SHA-256 do laudo não autentica nada.**
`pdf_report_generator.py:154-155` calcula o hash de `id + timestamp + nº de validações`.
Não cobre o conteúdo do laudo nem os documentos de origem — é decorativo.
→ Hashear o conteúdo do PDF gerado e persistir o par (hash, versão do projeto, regras
aplicadas) para verificação posterior.

**B5. Path traversal no upload.**
`endpoints/documents.py:36` monta o caminho com `file.filename` cru
(`f"{project_id}_{version}_{file.filename}"`). Um nome como `../../etc/x` escapa do
diretório. Não há validação de tipo, tamanho nem antivírus (§6.6).
→ Sanitizar/normalizar nome, gravar sob UUID, validar MIME e limite de tamanho.

**B6. `evaluate_project` apaga o histórico de verificações.**
`regulatory_engine.py:83` faz `.delete()` de todos os `ValidationRecord` anteriores a cada
execução — e é chamado no `POST /projects`, no `PATCH /projects/{id}` e até no
`GET .../report/pdf`. Resultado: não existe histórico de análises, o que contraria
frontalmente o §3.5 (auditabilidade). Bônus: um `GET` com efeito colateral de escrita.
→ Verificações são *append-only*, agrupadas por uma entidade `AnalysisRun`
(projeto + versão + conjunto de regras + timestamp + validador).

### 4.2 Arquitetura — desvios dos princípios §3

**A1. Multiempresa incompleto (§3.1).**
Só `User` e `Project` têm `organization_id`. `Document`, `EAPItem`, `TaskItem`, `DailyLog`
e `ValidationRecord` têm apenas `project_id` (`models/domain.py:72-157`). Faltam, em quase
todas as entidades, os campos exigidos pelo plano: **autor, versão, estado, origem**.
Não há autenticação em nenhum endpoint, não há filtro por tenant, não há RLS.
→ É o retrofit mais caro se adiado. Deve entrar antes de qualquer módulo novo.

**A2. Linha de base não existe como entidade (§3.2).**
Há apenas `Project.is_official_baseline: bool` e `Project.status: str`. Os parâmetros
urbanísticos são mutados *in place* pelo `PATCH`, sem histórico. Não existem os estados
do plano (estudo preliminar → revisão interna → protocolada → notificada → corrigida →
aprovada → alteração em obra → as built), nem **Proposta de Revisão Formal**, nem grafo
de propagação de impacto (§8.7).
→ Criar `ProjectVersion` imutável; a linha de base é uma versão marcada, não um booleano.

**A3. Regras são código, não dado (§3.4, §7.3-7.6).**
As 7 regras são lambdas Python em `regulatory_engine.py:6-77`. Faltam por completo:
estados da regra (`rascunho_extraido_por_ia` … `revogada`), `effective_from/until`,
`validated_by`, `severity` (bloqueio/alerta), `tolerance`, `evidence_required`,
`jurisdiction` estruturada. `pyyaml` está em `requirements.txt` mas não é usado — o
exemplo YAML do §7.6 não foi implementado.
Consequência direta: **a regra de segurança §7.5 é inexequível** — não há como impedir que
uma regra em rascunho entre num laudo, porque regra não tem estado.
Vazamento de jurisdição: as regras de vagas e de acessibilidade usam `applies: lambda p: True`
(`regulatory_engine.py:65` e `:75`), logo se aplicam a qualquer município.

**A4. Auditabilidade rasa (§3.5).**
`ValidationRecord` não registra arquivo de origem, versão do documento, dado extraído,
método, vigência da regra, modelo de IA, confiança nem validador. `source_citation` é
texto livre, não referência ao catálogo.

**A5. A "IA" não é IA (§3.3, §6.8).**
`endpoints/ai.py` é uma cadeia de `if` sobre palavras-chave com dicionário fixo. Não há
camada multi-provider, structured outputs, validação Pydantic da saída, RAG, pgvector,
cache por hash, roteamento por tarefa nem registro de proveniência. E, como está, ela
**emite conclusão legal afirmativa com número de artigo** — proibido pelo §3.3.

**A6. Persistência fora do plano (§6.5).**
Default é SQLite (`config.py:22`). O `docker-compose.yml` sobe PostGIS e Redis, mas
**nada no código se conecta a eles**. Não há Supabase, PostGIS, pgvector, RLS. Não há
migrations versionadas — usa-se `Base.metadata.create_all` (`main.py:9`), o que o plano
descarta explicitamente ("migrations SQL versionadas").

**A7. Sem filas nem workers (§6.7).**
Extração e geração de laudo rodam síncronas no request. Redis está declarado e ocioso.

**A8. Subsistema de Operação Regulatória (§7) — ausente por completo.**
Nenhum coletor, catálogo, extrator, validador ou monitor. Nem o Nível 1 ("manual
assistido") está fechado, porque o Nível 1 pressupõe regras cadastradas **como dado**.

### 4.3 Frontend

- **Mocks embutidos como estado inicial**: `MOCK_PROJECTS` (`app/approvals/page.tsx:25`,
  `app/projects/page.tsx:8`), `MOCK_EAP`/`MOCK_TASKS` (`app/plan/page.tsx:31,41`),
  `MOCK_DAILY_LOGS` (`app/daily-log/page.tsx:26`). Com o backend fora do ar, o usuário vê
  não conformidades inventadas sem qualquer indicação de que são fictícias. Somado ao
  *fallback* silencioso de `lib/api.ts`, isso é enganoso num produto de conformidade legal.
- **Dashboard `/` é 100% estático** — números fixos no JSX.
- **Lacunas de stack vs §6.1**: sem TanStack Query/Table, React Hook Form, Zod, shadcn/ui,
  PDF.js, Gantt, mapas.
- **Sem PWA** (§6.2): sem manifest, sem service worker, sem operação offline (§3.7).
- **Sem autenticação** na UI; sem seletor de organização.
- Sem `next.config.js`.

### 4.4 Higiene de repositório

- Artefatos versionados que deveriam ser ignorados: `backend/atlas_dev.db`,
  `backend/app/**/__pycache__/*.pyc`, `frontend/tsconfig.tsbuildinfo`.
- `.gitignore` ignora `backend/atlas.db`, mas o arquivo real é `atlas_dev.db`.
- Sem `README.md`, sem `.env.example`, sem `Dockerfile` do backend, sem CI, sem
  lint/format (ruff/black/eslint/prettier), sem `conftest.py`.
- `SECRET_KEY` com default hardcoded (`config.py:20`).
- Bug de regex em `pdf_parser.py` (linhas 27, 38, 49, 60, 71): a classe `([\d[\.\,]+)`
  contém um `[` espúrio.
- `occupancy_rate` é campo persistido **e** recalculado a partir de `built_area/lot_area`
  (`regulatory_engine.py:21-23`) — duas fontes da verdade divergentes (o seed grava 53,3).
- `side_setback` é coletado mas nenhuma regra o verifica.
- `atencao` é contado no relatório (`regulatory.py:23`) mas nenhuma regra o produz.

---

## 5. Matriz de aderência ao plano

| Seção do plano | Status | Observação |
|---|---|---|
| §3.1 Multiempresa | 🔴 Parcial | Sem auth, sem RLS, sem `organization_id` na maioria das entidades |
| §3.2 Linha de base | 🔴 Ausente | Apenas um booleano; sem versionamento nem revisão formal |
| §3.3 IA assistiva | 🟡 Divergente | Separação correta, mas a IA emite conclusão legal e não é IA |
| §3.4 Regras determinísticas | 🟡 Parcial | Determinístico ✔, mas como código e sem estados |
| §3.5 Auditabilidade | 🔴 Insuficiente | Histórico é apagado a cada avaliação |
| §3.6 Entrada híbrida | 🟡 Embrionário | Só PDF via regex; sem IFC, DXF, OCR |
| §3.7 Offline de campo | 🔴 Ausente | Sem PWA |
| §6.5 Banco | 🔴 Divergente | SQLite; sem migrations, PostGIS, pgvector, RLS |
| §6.6 Storage | 🟡 Parcial | Hash ✔; sem abstração, antivírus, versionamento, retenção |
| §6.7 Filas | 🔴 Ausente | Redis ocioso |
| §6.8 IA | 🔴 Ausente | Sem provider, RAG, proveniência |
| §7 Operação Regulatória | 🔴 Ausente | Nenhum dos seis componentes |
| §8.1 Organizações e usuários | 🟡 Modelo apenas | Sem perfis, permissões, convites, MFA, logs |
| §8.2 Cadastro de empreendimento | 🟡 Parcial | Faltam endereço, coordenadas, lote, quadra, matrícula, proprietário, responsáveis, unidades |
| §8.3 Gestão documental | 🟡 Parcial | Upload + hash ✔; sem OCR, tags, versionamento, QR Code, bloqueio de obsoleto |
| §8.4 Pré-análise legal | 🟢 Núcleo pronto | Melhor módulo do embrião; precisa de evidências e validação humana |
| §8.5 Tramitação | 🔴 Ausente | — |
| §8.6 Controle de versões | 🔴 Ausente | — |
| §8.7 Grafo de impacto | 🔴 Ausente | — |
| §8.8 EAP / §8.13 Tarefas / §8.12 Diário | 🟡 Estágio 2 antecipado | CRUD básico, fora da ordem do roadmap |
| §8.22 Portal do cliente | 🔴 Ausente | — |
| §12 Segurança | 🔴 Insuficiente | Sem auth, RLS, MFA, logs; laudo sem ressalvas legais |

---

## 6. Próximos passos

> O backlog desta seção está **esgotado** — as Fases A, B e C foram entregues.
> A continuidade (Estágios 2 a 7 do plano e a Fase D de liberação) vive em
> [`ROADMAP.md`](ROADMAP.md).

### Fase A — Correções de risco ✅ concluída

| # | Item | Status |
|---|---|---|
| 1 | Remover o *fallback* fabricado de `pdf_parser.py`; adicionar `pypdf`; corrigir os regex; retornar `nao_verificavel` sem evidência | ✅ |
| 2 | Reescrever o laudo: remover a afirmação de validade oficial; incluir as ressalvas do §12 | ✅ |
| 3 | Distinguir `atencao` e `nao_verificavel` de `nao_conforme` no PDF | ✅ |
| 4 | Sanitizar o upload (UUID no disco, allowlist de extensão, limite de tamanho) | ✅ |
| 5 | Tornar a avaliação *append-only*; tirar o efeito colateral do `GET` do laudo | ✅ |
| 6 | Unificar as citações legais numa fonte única; marcar como não verificadas | ✅ |
| 7 | Remover mocks do frontend; tornar visível o erro de backend indisponível | ✅ |
| 8 | Limpar o repositório, corrigir `.gitignore`, adicionar `README.md` e `.env.example` | ✅ |

Detalhes do que foi entregue além do enunciado dos itens:

- **Catálogo regulatório como dado** (`app/regulatory/`): as regras saíram do código
  para YAML versionado, com os estados do §7.4, vigência, severidade, tolerância e
  evidências exigidas. Foi o que tornou exequível a regra de segurança §7.5 — o campo
  `is_publishable` agora bloqueia laudo com regra não validada.
- **`AnalysisRun`**: cada avaliação é uma análise imutável, com contagens, versão do
  catálogo, versão do motor e hash de conteúdo. O `GET` do laudo passou a ser somente
  leitura e aceita `run_id` para reemitir análises históricas.
- **Parâmetros nulos**: os campos urbanísticos passaram a aceitar `NULL`. Antes, o
  padrão `0.0` fazia um cadastro novo reprovar em recuo — ausência de dado virava
  não conformidade.
- **Taxa de ocupação derivada**: deixou de ser coluna armazenada, eliminando a
  divergência entre o valor gravado e o recalculado.
- **Severidade `alerta`**: o contador `atencao`, que era código morto, passou a ser
  alcançável.
- **Vazamento de jurisdição corrigido**: as regras de vagas e acessibilidade não se
  aplicam mais a qualquer município.
- **Robustez do extrator**: normalização de números BR/EN e busca insensível a acentos
  preservando o trecho original como evidência.

Suíte de testes: **8 → 51**, com um teste de regressão para cada bloqueador do §4.1.

### Fase B — Núcleo do Estágio 1 ✅ concluída

| # | Item | Status |
|---|---|---|
| 9 | Autenticação e multitenancy: `organization_id` em todas as entidades, dependency de tenant, perfis e permissões (§8.1) | ✅ |
| 10 | Postgres + Alembic; política de RLS definida (§6.5) | ✅ (ativação da RLS pendente de operação) |
| 11 | Catálogo regulatório como dado, com estados de §7.3/§7.4, vigência e validador | ✅ |
| 12 | `ProjectVersion` imutável; linha de base oficial; análise referencia a versão | ✅ |
| 13 | Auditabilidade completa em `ValidationRecord` | ✅ (já entregue na Fase A) |
| 14 | Tela de validação humana (§15.12) | ✅ |
| 15 | Campos do §8.2 e gestão documental com versionamento, obsoleto e QR Code (§8.3) | ✅ |
| 16 | Tramitação (§8.5) | ✅ |

Decisões que valem registro:

- **Recurso de outro tenant responde 404, não 403.** Informar que o recurso existe
  mas está fora do alcance já é vazamento entre organizações.
- **A RLS é segunda linha de defesa, não a primeira.** As políticas existem na
  migration e negam tudo por padrão (`current_setting(..., true)` nulo ⇒ nega).
  Falta o `SET LOCAL atlas.organization_id` por transação e um usuário de banco
  sem `BYPASSRLS` — trabalho de infraestrutura, documentado no README.
- **Publicar regra exige documento *e* artigo conferidos.** Sem os dois, a fonte
  permanece não verificada e a regra não pode ser `vigente`. Sair de `vigente`
  retira a validação: uma regra suspensa deixa de ser publicável no mesmo ato.
- **A reimportação do YAML não sobrescreve regra publicada.** Quem publicou
  assumiu a responsabilidade técnica; um arquivo não pode desfazer isso
  silenciosamente.
- **Parâmetros urbanísticos saíram do projeto para a versão.** Foi o que tornou
  exequível o §14.15: não existe "salvar por cima" de uma medida.
- **A exigência do órgão pode ser vinculada à regra que deveria tê-la previsto.**
  É o que transforma o recall de bloqueios (§11) em medição, e não suposição — e o
  endpoint devolve `null` quando não há vínculo, em vez de estimar um número.

Suíte de testes: **51 → 110**.

### Fase C — Consolidação ✅

| # | Item | Situação | Onde |
|---|---|---|---|
| 17 | Storage abstraído, retenção e antivírus (§6.6) | ✅ | `app/services/storage.py`, `antivirus.py`, `retention.py` |
| 18 | Filas e workers assíncronos (§6.7) | ✅ | `app/workers/` |
| 19 | Camada de IA com RAG e proveniência (§3.3, §6.8) | ✅ | `app/ai/` |
| 20 | PWA e operação offline de campo (§6.2, §3.7) | ✅ | `frontend/public/sw.js`, `lib/offline.ts` |
| 21 | Portal do cliente (§8.22) | ✅ | `app/api/v1/endpoints/portal.py`, `app/portal/` |

Quatro decisões desta fase merecem registro, porque divergem do que o backlog
original supunha:

- **Sem Dramatiq nem Celery.** O registro do trabalho precisa existir no banco
  de qualquer forma, por auditabilidade (§3.5). Com o estado no Postgres, o que
  o broker carrega é um UUID — e para isso um framework de filas é peso morto.
  A consequência prática é boa: um Redis reiniciado não perde trabalho, porque
  não era ele que guardava o trabalho.

- **Sem pgvector.** A recuperação sobre o catálogo é lexical, com sinônimos do
  jargão de aprovação ("afastamento" → "recuo"). Para dezenas a poucas centenas
  de regras por jurisdição, recupera bem e não adiciona índice a manter. A
  interface `retrieve()` não muda quando isso deixar de bastar.

- **A IA não pode citar a lei.** O contrato de saída pede `rule_key`, não
  "art. 45", e toda chave é conferida contra o contexto entregue. Não bastava
  instruir o modelo a não inventar: era preciso que não houvesse por onde.

- **Offline é seletivo, e a exclusão é o ponto.** Diário e tarefas funcionam sem
  rede; análise, laudo, catálogo e assistente recusam. Um veredicto de
  conformidade calculado sobre catálogo desatualizado é pior que a ausência de
  veredicto — e o service worker tem lista explícita disso.

Suíte de testes: **110 → 199**.

### Observação sobre o Estágio 0

O plano é explícito (§14.1 e §15.15): começar pelo serviço manual e **iniciar o
desenvolvimento apenas após o Portão 0**. O embrião pulou essa etapa. Isso não invalida o
código — ele serve muito bem como protótipo de demonstração e como esqueleto técnico —
mas significa que **as regras hoje no motor não vieram de casos reais**. Recomendação:
rodar o concierge em paralelo à Fase A/B e usar as exigências reais de Lajeado para
popular o catálogo regulatório da Fase B. Sem isso, o motor continuará preciso na
mecânica e incerto no conteúdo.

---

## 7. Checklist mínimo para declarar o Estágio 1 iniciado

- [x] Autenticação e isolamento por organização em todos os endpoints
- [x] Postgres + migrations versionadas em uso real
- [x] Regras vivendo no catálogo, com estado e vigência
- [x] Motor executando somente regras executáveis; publicação exige `vigente`
- [x] Versão de projeto imutável + linha de base oficial
- [x] Histórico de análises preservado (append-only)
- [x] Laudo com ressalvas legais e sem afirmação de validade oficial
- [x] Tela de validação humana operante
- [x] Zero dados fabricados em qualquer caminho de código
- [ ] **Catálogo conferido contra a legislação publicada** — depende de
      responsável técnico, não de código
- [ ] **RLS ativa** — `SET LOCAL atlas.organization_id` por transação, com
      usuário sem `BYPASSRLS`
- [ ] **Portão 0** — regras vindas de casos reais de Lajeado
