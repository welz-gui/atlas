# Atlas

Plataforma para aprovação, planejamento, execução e gestão de empreendimentos.
A porta de entrada é o **Copiloto de Aprovação**: pré-análise urbanística
determinística, com trilha de auditoria.

> **Estágio atual: protótipo em desenvolvimento.**
> O catálogo regulatório ainda **não foi conferido** contra o texto legal
> publicado por nenhum município. Os laudos gerados saem marcados como uso
> interno e não devem ser entregues a clientes. Ver [Limites conhecidos](#limites-conhecidos).

---

## Princípios que o código sustenta

Estes não são aspirações — são invariantes cobertos por teste:

| Princípio | Onde vive |
|---|---|
| Ausência de dado nunca vira veredicto | Parâmetro não informado é `nao_verificavel`, nunca `nao_conforme` |
| O sistema não inventa medidas | Extração sem evidência devolve `null` e um aviso |
| Regras são dado, não código | `backend/app/regulatory/data/*.yaml`, com estado e vigência |
| Fonte legal única | Motor e assistente leem o mesmo catálogo |
| Análises são append-only | Cada avaliação cria um `AnalysisRun`; nada é sobrescrito |
| Regra não validada não vai para o cliente | `is_publishable` bloqueia a publicação (§7.5) |
| Falha de rede não vira dado | O cliente HTTP lança erro; a interface o exibe |

---

## Como rodar

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python seed.py                     # dados de demonstração
uvicorn app.main:app --reload      # http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                        # http://localhost:3000
```

### Postgres e Redis (opcional)

```bash
docker compose up -d
```

O `docker-compose.yml` sobe PostGIS e Redis. Hoje **a aplicação ainda não os
utiliza** — o padrão é SQLite e não há workers. Ligar o Postgres é trabalho da
Fase B (ver o documento de revisão).

### Testes

```bash
cd backend && python -m pytest tests/ -q
```

---

## Estrutura

```
backend/
  app/
    api/v1/endpoints/    projects, regulatory, documents, plan, ai, daily_log
    core/                config e sessão de banco
    models/domain.py     entidades SQLAlchemy
    regulatory/
      catalog.py         carregamento e execução de regras
      data/*.yaml        o catálogo regulatório (o dado que importa)
    schemas/domain.py    contratos Pydantic
    services/            motor de regras, extrator, gerador de laudo
  tests/
frontend/
  app/                   páginas (App Router)
  components/            estados de carregamento, erro e vazio
  lib/api.ts             cliente HTTP tipado
docs/
  REVISAO_ADERENCIA_PLANO_v2.md   revisão de aderência ao plano
```

---

## O catálogo regulatório

As regras vivem em `backend/app/regulatory/data/`, no formato do §7.6 do plano:

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
  validated_by: null
```

**Estados da regra** (§7.4): `rascunho_extraido_por_ia`, `em_validacao`,
`vigente`, `suspensa`, `revogada`, `substituida`.
O motor executa apenas `em_validacao` e `vigente`. Só `vigente` **com**
`validated_by` preenchido pode constar de laudo entregue ao cliente.

**Para promover uma regra a `vigente`:** conferir o texto legal, preencher
`source` (documento, artigo, URL, data de consulta), `effective_from` e
`validated_by`, e então alterar `state`.

---

## API

| Método | Rota | Observação |
|---|---|---|
| `POST` | `/api/v1/projects/{id}/evaluate` | Executa o catálogo e cria uma análise |
| `GET` | `/api/v1/projects/{id}/validations` | Verificações da análise mais recente |
| `GET` | `/api/v1/projects/{id}/analysis-runs` | Histórico completo |
| `GET` | `/api/v1/projects/{id}/report/pdf` | **Somente leitura** — renderiza análise existente; 409 se não houver |
| `POST` | `/api/v1/projects/{id}/documents/upload` | Grava sob UUID, valida extensão e tamanho |
| `POST` | `/api/v1/projects/{id}/documents/{doc}/extract` | Extração assistida |

Documentação interativa em `/docs`.

---

## Limites conhecidos

Estado real do protótipo, para que ninguém descubra isso tarde demais:

- **Não há autenticação.** Todos os endpoints são públicos e não filtram por
  organização. Não exponha esta aplicação na internet.
- **Não há RLS nem isolamento por tenant.**
- **O catálogo não foi validado.** Nenhum parâmetro foi conferido contra a
  legislação de Lajeado. Os laudos saem com tarja de uso interno.
- **Sem migrations.** O esquema é criado com `create_all`; mudanças de modelo
  exigem recriar o banco (`rm atlas_dev.db && python seed.py`).
- **Sem OCR.** PDF digitalizado (imagem) não é extraível e retorna aviso.
- **Sem IFC, DXF ou BIM.**
- **O assistente não é um modelo de linguagem** — é busca por palavra-chave
  sobre o catálogo, e se apresenta como tal.
- **Sem filas.** Extração e laudo rodam de forma síncrona no request.
- **Sem PWA nem operação offline.**

O caminho para resolver cada um está em
[`docs/REVISAO_ADERENCIA_PLANO_v2.md`](docs/REVISAO_ADERENCIA_PLANO_v2.md).
