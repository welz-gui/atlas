# Atlas

Plataforma para aprovação, planejamento, execução e gestão de empreendimentos.
A porta de entrada é o **Copiloto de Aprovação**: pré-análise urbanística
determinística, com trilha de auditoria.

> **Estágio atual: Fases A e B concluídas.**
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
| Fonte legal única | Motor e assistente leem o mesmo catálogo |
| Nenhuma alteração silenciosa | Parâmetro alterado cria versão nova; a anterior fica intacta |
| Análises são append-only | Cada avaliação cria um `AnalysisRun`; nada é sobrescrito |
| Regra não validada não vai para o cliente | Publicar exige documento **e** artigo conferidos (§7.5) |
| Isolamento entre organizações | Recurso de outro tenant responde 404, nunca 403 |
| Falha de rede não vira dado | O cliente HTTP lança erro; a interface o exibe |

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

O Redis está declarado no compose mas **ainda não é usado** — não há workers
(Fase C).

### Testes

```bash
cd backend && python -m pytest tests/ -q
```

---

## Papéis e permissões

| Papel | Pode |
|---|---|
| `owner` / `admin` | Tudo, incluindo gestão de usuários |
| `validator` | Publicar regras no catálogo regulatório |
| `engineer` | Projetos, versões, documentos, tramitação, obra |
| `inspector` | Campo: diário, tarefas, documentos |
| `client` | Somente leitura, restrito à própria organização |

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
| `POST` | `/api/v1/protocols/{id}/requirements` | Registra exigência do órgão |
| `GET` | `/api/v1/projects/{id}/prediction-accuracy` | Recall de bloqueios (§11) |
| `GET` | `/api/v1/documents/{id}/qrcode` | QR de verificação do documento |

Documentação interativa em `/docs`.

---

## Segurança

- Senha com **argon2id**; a senha em claro nunca é persistida nem registrada.
- `SECRET_KEY` é **obrigatória** quando `ENVIRONMENT=production`; em
  desenvolvimento, gera-se uma chave efêmera por processo.
- Isolamento por organização em toda consulta de negócio
  (`backend/app/api/deps.py`).
- **RLS no Postgres** como segunda linha de defesa. A migration de RLS cria as
  políticas; para terem efeito é preciso conectar com um usuário sem
  `BYPASSRLS` e definir, por transação:

  ```sql
  SET LOCAL atlas.organization_id = '<uuid da organização>';
  ```

  Sem isso a política nega tudo — falhar fechado é deliberado.
- Upload grava sob UUID, com allowlist de extensão e limite de tamanho.

---

## Limites conhecidos

Estado real do sistema, para que ninguém descubra isso tarde demais:

- **O catálogo não foi validado.** Nenhum parâmetro foi conferido contra a
  legislação de Lajeado. Laudos com regras pendentes saem marcados como uso
  interno.
- **RLS não está ativa por padrão** — falta o `SET LOCAL` por transação
  descrito acima. Hoje o isolamento depende do filtro de aplicação.
- **Sem MFA** e sem refresh token; a sessão expira em 7 dias.
- **Sem antivírus** no upload e sem política de retenção.
- **Sem OCR.** PDF digitalizado (imagem) não é extraível e retorna aviso.
- **Sem IFC, DXF ou BIM.**
- **O assistente não é um modelo de linguagem** — é busca por palavra-chave
  sobre o catálogo, e se apresenta como tal.
- **Sem filas.** Extração e laudo rodam de forma síncrona no request.
- **Sem PWA nem operação offline.**
- **Sem coletor nem monitor regulatório** (§7.2) — o catálogo é alimentado à
  mão.

O caminho para resolver cada um está em
[`docs/REVISAO_ADERENCIA_PLANO_v2.md`](docs/REVISAO_ADERENCIA_PLANO_v2.md).
