# Atlas

Plataforma para aprovação, planejamento, execução e gestão de empreendimentos.
A porta de entrada é o **Copiloto de Aprovação**: pré-análise urbanística
determinística, com trilha de auditoria.

> **Estágio atual: Fases A, B e C concluídas.**
> O catálogo regulatório ainda **não foi conferido** contra o texto legal
> publicado por nenhum município. Enquanto uma regra não for validada por um
> responsável identificado, os laudos que a aplicam saem marcados como uso
> interno. Ver [Limites conhecidos](#limites-conhecidos).

---

## Princípios que o código sustenta

Estes não são aspirações — são invariantes cobertos por teste:

| Princípio | Onde vive |
|---|---|
| Ausência de dado nunca vira veredicto | Parâmetro não informado é `nao_verificavel`, nunca `nao_conforme` |
| O sistema não inventa medidas | Extração sem evidência devolve `null` e um aviso |
| Regras são dado, não código | Tabela `regulatory_rules`, com estado, vigência e validador |
| Fonte legal única | Motor, assistente e IA leem o mesmo catálogo |
| Nenhuma alteração silenciosa | Parâmetro alterado cria versão nova; a anterior fica intacta |
| Análises são append-only | Cada avaliação cria um `AnalysisRun`; nada é sobrescrito |
| Regra não validada não vai para o cliente | Publicar exige documento **e** artigo conferidos (§7.5) |
| A IA propõe; quem publica é gente | Rascunho de IA nasce em `rascunho_extraido_por_ia`, fora do motor |
| A IA não cita a lei; aponta para o catálogo | Chave citada fora do contexto é descartada e registrada |
| Ausência de verificação não é aprovação | Upload sem antivírus fica `nao_verificado`, nunca "limpo" |
| Expurgo apaga o arquivo, nunca o registro | Documento expurgado mantém título, versão, hash e autor |
| Isolamento entre organizações | Recurso de outro tenant responde 404, nunca 403 |
| Falha de rede não vira dado | O cliente HTTP lança erro; a interface o exibe |
| Registro offline não é registro salvo | Item na fila aparece como *pendente*, com a hora em que foi escrito |

---

## Como rodar

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

alembic upgrade head            # cria o esquema
python seed.py                  # dados e usuários de demonstração
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

O `seed.py` imprime as credenciais de demonstração. Todos os papéis usam a
mesma senha, e o catálogo é semeado **em validação** — nenhuma regra publicada.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                     # http://localhost:3000
```

### Postgres, PostGIS e Redis

```bash
docker compose up -d
# aponte DATABASE_URL no .env e rode: alembic upgrade head
```

### Worker (opcional)

```bash
# .env: QUEUE_BACKEND=redis
python -m app.workers.worker --recover
```

Sem worker, os trabalhos executam no próprio processo da API — e o registro do
trabalho diz isso (`executed_inline`).

### Testes

```bash
cd backend && python -m pytest tests/ -q
```

---

## Papéis e permissões

| Papel | Pode |
|---|---|
| `owner` / `admin` | Tudo, incluindo gestão de usuários e retenção |
| `validator` | Publicar regras no catálogo; extrair rascunhos por IA |
| `engineer` | Projetos, versões, documentos, tramitação, obra |
| `inspector` | Campo: diário, tarefas, documentos |
| `client` | Somente o portal de acompanhamento (§8.22) |

A matriz vive em `backend/app/core/security.py`. O frontend espelha uma cópia
apenas para esconder botões — quem decide é sempre o servidor.

---

## Linha de base versionada

Os parâmetros urbanísticos pertencem a `ProjectVersion`, não ao projeto:

- alterar um parâmetro **cria uma versão nova**, com autor, motivo e hash;
- a versão anterior permanece intacta e continua consultável;
- os estados seguem o §3.2: `estudo_preliminar` → `revisao_interna` →
  `protocolada` → `notificada` → `corrigida` → `aprovada` →
  `alteracao_em_obra` → `as_built`;
- a **linha de base oficial** é uma versão `aprovada` marcada como tal, e é
  exclusiva — promover uma desmarca a anterior;
- toda análise registra qual versão avaliou.

---

## O catálogo regulatório

Regras vivem na tabela `regulatory_rules`. Os arquivos de
`backend/app/regulatory/data/*.yaml` são **semente de importação**, úteis para
versionar o cadastro inicial de um município em revisão de código:

```yaml
- rule_id: lajeado_recuo_frontal_z2
  title: Recuo Frontal Mínimo — Zona Z2
  state: em_validacao          # §7.4
  severity: bloqueio           # bloqueio -> nao_conforme; alerta -> atencao
  applies_to:
    zone: [Z2]
    building_type: [residencial_unifamiliar]
  check:
    field: front_setback
    operator: ">="
    value: 4.0
    unit: m
    tolerance: 0.02
  evidence_required: [implantacao, quadro_areas]
  source:
    document: Plano Diretor de Lajeado
    article: null              # nunca preencher sem conferir a lei
```

**Estados** (§7.4): `rascunho_extraido_por_ia`, `em_validacao`, `vigente`,
`suspensa`, `revogada`, `substituida`. O motor executa apenas `em_validacao` e
`vigente`; só `vigente` **com validador registrado** pode ir a laudo entregue
ao cliente.

**Para publicar uma regra** (tela `/catalog`, papel `validator`): cadastrar a
norma de origem, conferir o texto legal, informar o artigo e publicar. O
sistema recusa a publicação sem documento **e** artigo — sem eles a fonte
permanece não verificada. Cada transição fica registrada em
`rule_validation_events`, com quem fez e quando.

---

## Camada de IA

Desligada por padrão (`AI_PROVIDER=none`): sem provedor, o assistente responde
por busca determinística sobre o catálogo — e `GET /ai/status` declara isso, em
vez de a interface ter de supor.

Com `AI_PROVIDER=anthropic`, três invariantes governam o comportamento:

1. **A IA propõe; não publica.** Rascunho extraído de texto legal nasce em
   `rascunho_extraido_por_ia`, com o trecho literal de origem gravado para o
   validador conferir. Não há parâmetro que faça uma regra proposta por modelo
   chegar ao motor ou a um laudo.
2. **A IA não cita a lei; aponta para o catálogo.** O contrato de saída pede
   `rule_key`. Chave que não estava no contexto entregue é descartada, a
   resposta cai para a busca determinística, e a interação fica
   `grounded=false`.
3. **A IA não emite veredicto.** Conformidade vem do motor determinístico.

Toda chamada fica em `ai_interactions`: quem perguntou, qual modelo respondeu,
quais regras entraram como contexto, quais foram citadas, tokens e latência.
Consultável em `GET /ai/interactions` pelo papel `validator`.

---

## Operação de campo e PWA

O Atlas é instalável (`manifest.webmanifest` + service worker) e opera em obra
sem rede — para o que pode operar sem rede:

- **funciona offline:** diário de obra e tarefas. Vão para uma fila em
  IndexedDB e são reenviados quando a conexão volta. O item aparece como
  *pendente*, com a hora em que foi escrito, **nunca** como salvo;
- **não funciona offline:** análise, laudo, catálogo e assistente. O service
  worker tem lista explícita de rotas que jamais respondem do cache. Um
  veredicto calculado sobre catálogo desatualizado é pior que a ausência de
  veredicto.

A criação de diário e tarefa é idempotente por `client_token`, com escopo de
organização: reenviar depois de uma resposta perdida devolve o registro
original em vez de criar um segundo.

---

## API

Todos os endpoints de negócio exigem `Authorization: Bearer <token>` e operam
restritos à organização do usuário.

| Método | Rota | Observação |
|---|---|---|
| `POST` | `/api/v1/auth/signup` | Cria organização e usuário `owner` |
| `POST` | `/api/v1/auth/login` | Devolve o token |
| `POST` | `/api/v1/projects` | Cria empreendimento e a versão 1 |
| `POST` | `/api/v1/projects/{id}/versions` | Nova versão (não edita a atual) |
| `POST` | `/api/v1/projects/{id}/versions/{v}/baseline` | Elege linha de base (exige `aprovada`) |
| `POST` | `/api/v1/projects/{id}/evaluate` | Executa o catálogo, cria uma análise |
| `GET` | `/api/v1/projects/{id}/analysis-runs` | Histórico completo |
| `GET` | `/api/v1/projects/{id}/report/pdf` | **Somente leitura**; 409 se não houver análise |
| `GET` | `/api/v1/catalog/validation-queue` | Regras aguardando conferência |
| `POST` | `/api/v1/catalog/rules/{id}/validate` | Ato de validação técnica |
| `POST` | `/api/v1/projects/{id}/protocols` | Registra protocolo |
| `GET` | `/api/v1/projects/{id}/prediction-accuracy` | Recall de bloqueios (§11) |
| `GET` | `/api/v1/documents/{id}/download` | 410 se expurgado; 404 se sumiu |
| `POST` | `/api/v1/storage/purge-expired` | Retenção; simulação por padrão |
| `POST` | `/api/v1/projects/{id}/jobs/analysis` | Análise assíncrona (§6.7) |
| `GET` | `/api/v1/jobs/{id}` | Situação do trabalho |
| `GET` | `/api/v1/ai/status` | Declara se há modelo configurado |
| `POST` | `/api/v1/ai/rule-drafts` | Rascunhos de regra por IA (validator) |
| `GET` | `/api/v1/ai/interactions` | Proveniência das chamadas ao modelo |
| `GET` | `/api/v1/portal/projects` | Visão de acompanhamento do cliente (§8.22) |

Documentação interativa em `/docs`.

---

## Segurança

- Senha com **argon2id**; a senha em claro nunca é persistida nem registrada.
- `SECRET_KEY` é **obrigatória** quando `ENVIRONMENT=production`; em
  desenvolvimento, gera-se uma chave efêmera por processo.
- Isolamento por organização em toda consulta de negócio
  (`backend/app/api/deps.py`). Nos workers, que rodam sem `get_current_user`,
  o filtro é refeito à mão em cada executor.
- **RLS no Postgres** como segunda linha de defesa. A migration de RLS cria as
  políticas; para terem efeito é preciso conectar com um usuário sem
  `BYPASSRLS` e definir, por transação:

  ```sql
  SET LOCAL atlas.organization_id = '<uuid da organização>';
  ```

  Sem isso a política nega tudo — falhar fechado é deliberado.
- Upload grava sob chave opaca, com allowlist de extensão e limite de tamanho.
  Com `ANTIVIRUS_BACKEND=clamav` e `ANTIVIRUS_REQUIRED=true`, o que não pôde
  ser varrido é recusado.

---

## Limites conhecidos

Estado real do sistema, para que ninguém descubra isso tarde demais:

- **O catálogo não foi validado.** Nenhum parâmetro foi conferido contra a
  legislação de Lajeado. Laudos com regras pendentes saem marcados como uso
  interno, e o portal do cliente não exibe o resumo de conformidade.
- **RLS não está ativa por padrão** — falta o `SET LOCAL` por transação
  descrito acima. Hoje o isolamento depende do filtro de aplicação.
- **Sem MFA** e sem refresh token; a sessão expira em 7 dias.
- **Sem OCR.** PDF digitalizado (imagem) não é extraível e retorna aviso.
- **Sem IFC, DXF ou BIM.**
- **Sem coletor nem monitor regulatório** (§7.2) — o catálogo é alimentado à
  mão ou por rascunho de IA sobre texto colado.
- **RAG lexical, não vetorial.** Suficiente para catálogo municipal; trocar por
  pgvector não muda a interface `retrieve()`.
- **A fila offline não sincroniza fotos** — apenas diário e tarefas.
- **Antivírus e S3 não foram exercitados contra serviço real** nesta base;
  há teste de contrato, não de integração.

O caminho para resolver cada um está em
[`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## Como contribuir

Nada é desenvolvido em `master`. Cada frente de trabalho nasce em uma **worktree
própria**, com branch própria, e só chega em `master` por **Pull Request
analisado** em [`welz-gui/atlas`](https://github.com/welz-gui/atlas) — inclusive
documentação, inclusive correção de uma linha.

```bash
git fetch origin
git switch master && git pull --ff-only
git worktree add worktrees/<slug> -b feat/<slug> origin/master
```

O fluxo completo — sincronia com o remoto, o que o PR precisa carregar e o que
barra um PR na análise — está em
[`docs/ROADMAP.md` → *Como trabalhar*](docs/ROADMAP.md#como-trabalhar--worktrees-e-sincronia).

---

## Documentação

| Documento | O que traz |
|---|---|
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Estágios 0 a 7, o que já existe, como implementar cada um, ferramentas e armadilhas, e o fluxo de worktrees e PRs |
| [`docs/LGPD.md`](docs/LGPD.md) | Inventário de dado pessoal, o que o código faz e o que depende de decisão humana |
| [`docs/OPERACAO.md`](docs/OPERACAO.md) | Backup, restauração, segredos e deploy |
| [`docs/PLANO_DE_IMPLEMENTACAO_v2.md`](docs/PLANO_DE_IMPLEMENTACAO_v2.md) | O plano original, na íntegra |
| [`docs/REVISAO_ADERENCIA_PLANO_v2.md`](docs/REVISAO_ADERENCIA_PLANO_v2.md) | Diagnóstico do embrião e o backlog das Fases A, B e C |
