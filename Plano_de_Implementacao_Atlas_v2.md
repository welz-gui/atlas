# Atlas
## Plataforma Inteligente para Aprovação, Planejamento, Execução e Gestão de Empreendimentos

---

# Identidade do Projeto

## Nome

**Atlas**

## Conceito

Na mitologia, Atlas sustenta o mundo. Nesta plataforma, o objetivo é sustentar todo o ciclo de vida de um empreendimento, centralizando informações, decisões e conhecimento em um único ecossistema.

O Atlas conecta:

- Legislação e normas;
- Documentação;
- Projetos;
- Aprovação municipal;
- Orçamento;
- Quantitativos;
- Planejamento;
- Compras;
- Execução;
- Financeiro;
- Incorporação;
- Entrega;
- Pós-obra.

Seu propósito é transformar informações dispersas em decisões confiáveis.

## Missão

Reduzir retrabalho, antecipar problemas e permitir que engenheiros, construtores e incorporadores dediquem menos tempo procurando informações e mais tempo tomando decisões.

## Visão

Tornar-se a principal plataforma de referência para aprovação, planejamento, execução e gestão de empreendimentos, acompanhando o projeto desde a concepção até o pós-obra.

## Posicionamento

> **Atlas é o sistema operacional da construção.**

## Arquitetura da marca

**Atlas** (Plataforma)

- Atlas Approvals — Aprovação, conformidade e licenciamento
- Atlas Projects — Gestão documental e projetos
- Atlas Build — Gestão de obras
- Atlas Plan — Planejamento e cronogramas
- Atlas Cost — Orçamento, quantitativos e custos
- Atlas Field — Aplicativo de campo
- Atlas BIM — Modelos BIM e quantitativos
- Atlas AI — Assistente inteligente
- Atlas Develop — Incorporação imobiliária
- Atlas Insight — Dashboards e indicadores

---

# Plano de Implementação Atualizado — Copiloto Inteligente de Obras

## 1. Visão estratégica do produto

O **Copiloto Inteligente de Obras** será uma plataforma modular de gestão, conformidade, planejamento e inteligência para construção civil e incorporação.

O sistema deverá acompanhar o empreendimento ao longo de todo o ciclo:

**Viabilidade → projeto preliminar → pré-análise legal → revisões → protocolo → aprovação → orçamento → planejamento → execução → controle → entrega → pós-obra.**

A entrada comercial inicial será o **Copiloto de Aprovação**, voltado à pré-análise legal, urbanística e documental. A partir do projeto aprovado, a plataforma continuará sendo utilizada para:

- consolidar a linha de base oficial;
- atualizar quantitativos;
- gerar ou revisar orçamento;
- estruturar cronograma;
- controlar execução;
- acompanhar custos;
- gerir alterações;
- apoiar incorporação;
- registrar entrega e pós-obra.

Os módulos devem compartilhar o mesmo modelo de dados, mas poderão ser contratados separadamente:

1. Copiloto de Aprovação;
2. Gestão de Projetos e Documentos;
3. Gestão de Obras;
4. Custos e Planejamento;
5. Incorporação;
6. Copiloto de IA;
7. BIM e Quantitativos;
8. Pós-obra.

---

# 2. Tese central do produto

O produto não deverá competir inicialmente como “mais um ERP de obra”.

O diferencial inicial será resolver uma dor mais específica:

> Reduzir ciclos previsíveis de notificação, correção e reprotocolo, identificando previamente incompatibilidades normativas, documentais e técnicas.

Depois da aprovação, o projeto permanecerá dentro da plataforma como linha de base oficial, criando continuidade até a entrega.

Essa estratégia gera dois efeitos:

- entrada por uma dor específica e pouco atendida;
- retenção pela continuidade da gestão da obra.

---

# 3. Princípios de arquitetura

## 3.1. Multiempresa desde a origem

Toda entidade de negócio deverá possuir:

- `organization_id`;
- `project_id`, quando aplicável;
- autor;
- data;
- versão;
- estado;
- origem.

O sistema deve suportar desde o início múltiplas empresas, obras, usuários, municípios, tipologias e níveis de permissão.

## 3.2. Linha de base oficial

O sistema deverá distinguir:

- estudo preliminar;
- revisão interna;
- versão protocolada;
- versão notificada;
- versão corrigida;
- projeto aprovado;
- alteração em obra;
- projeto “as built”.

Quando o projeto for aprovado pelo órgão público, ele se tornará a **linha de base oficial**.

Orçamento, quantitativos e cronogramas deverão referenciar essa linha de base.

Qualquer alteração posterior deverá gerar uma **Proposta de Revisão Formal**, contendo origem, justificativa, elementos alterados, impactos, responsável, custo, prazo, documentos afetados e decisão.

## 3.3. IA assistiva

A IA poderá classificar, extrair, resumir, comparar, sugerir, priorizar, explicar e gerar rascunhos.

A IA não poderá publicar regras normativas, afirmar aprovação oficial, alterar orçamento automaticamente, modificar cronograma sem aprovação, emitir conclusão legal sem fonte ou substituir responsável técnico.

## 3.4. Regras determinísticas

Toda verificação legal ou urbanística deverá ser executada por regra estruturada.

A IA poderá encontrar e sugerir a regra, mas apenas regras validadas poderão ser aplicadas.

## 3.5. Auditabilidade

Toda análise deverá registrar arquivo de origem, versão, dado extraído, método, regra aplicada, fonte, vigência, modelo de IA, confiança, validador e resultado.

## 3.6. Entrada híbrida

O sistema deverá trabalhar com IFC, DXF, PDF vetorial, PDF digitalizado, imagens, planilhas e documentos textuais.

O IFC será o formato preferencial para extração automática. PDF e DXF deverão contar com medição assistida.

## 3.7. Operação de campo offline

As funções essenciais de campo devem funcionar offline: diário, fotos, áudios, checklists, tarefas, inspeções, recebimentos e apontamentos.

Funções de IA, análise normativa e consulta de documentos não baixados dependerão de conexão.

---

# 4. Estratégia de validação antes do desenvolvimento

## Estágio 0 — Serviço manual assistido

Antes de desenvolver o produto completo, deverá ser prestado um serviço de pré-análise manual.

### Objetivos

- validar disposição a pagar;
- identificar regras recorrentes;
- medir taxa de acerto humana;
- criar corpus de projetos;
- registrar notificações reais;
- mapear falsos positivos e falsos negativos;
- definir o formato do relatório.

### Atividades

1. Selecionar projetos reais.
2. Produzir relatórios manuais.
3. Cobrar pelo serviço.
4. Acompanhar o protocolo.
5. Comparar análise e exigências reais.
6. Estruturar regras utilizadas.
7. Registrar tempo gasto.
8. Registrar dificuldades de interpretação.
9. Medir o valor percebido.

### Saídas

- biblioteca inicial;
- dataset de validação;
- modelo do relatório;
- backlog real;
- primeiras regras;
- primeiros clientes.

### Portão de decisão

Avançar somente se houver projetos pagos, clientes recorrentes, taxa mínima de acerto, dor confirmada e regras repetitivas suficientes para automação.

---

# 5. Arquitetura geral

```text
Aplicação Web / PWA
        │
Aplicativo Mobile Futuro
        │
Portal do Cliente
        │
        ▼
API Principal — FastAPI
        │
 ┌──────┼────────┬──────────┬──────────┐
 ▼      ▼        ▼          ▼          ▼
Postgres Storage Workers Motor       Serviços
PostGIS  S3/R2  Redis   Normativo    BIM/IA
pgvector
```

---

# 6. Stack recomendada

## 6.1. Web

- Next.js;
- React;
- TypeScript;
- Tailwind CSS;
- shadcn/ui;
- TanStack Query;
- TanStack Table;
- React Hook Form;
- Zod;
- PDF.js;
- xeokit ou IFC.js;
- biblioteca de Gantt;
- mapas.

## 6.2. PWA inicial

Nos Estágios 1 e 2, a operação de campo poderá utilizar PWA para consulta de projeto, registros simples, fotos, tarefas, diário, checklists e notificações básicas.

## 6.3. Mobile nativo

O aplicativo nativo será implementado quando o uso de campo estiver validado.

Opções:

- Flutter;
- React Native/Expo.

A escolha dependerá da experiência da equipe, suporte à engine de sincronização, câmera, mídia, armazenamento local, offline e notificações.

Antes de desenvolver sincronização artesanal, avaliar PowerSync, ElectricSQL, WatermelonDB ou solução equivalente.

## 6.4. Backend

- FastAPI;
- Python;
- Pydantic;
- SQLAlchemy;
- monólito modular;
- workers separados.

## 6.5. Banco de dados

- PostgreSQL;
- Supabase inicialmente;
- PostGIS;
- pgvector;
- RLS;
- migrations SQL versionadas.

Evitar regras de negócio em funções proprietárias, abstrair storage e manter plano de saída para RDS ou Cloud SQL.

## 6.6. Armazenamento

- Supabase Storage inicialmente;
- S3 ou Cloudflare R2 como alternativa;
- hash SHA-256;
- antivírus;
- versionamento;
- política de retenção.

## 6.7. Filas

- Redis;
- Dramatiq ou Celery;
- workers Python.

Usos: OCR, transcrição, análise de documentos, processamento BIM, relatórios, indexação, monitoramento normativo e comparação de versões.

## 6.8. IA

- camada multi-provider;
- structured outputs;
- validação com Pydantic;
- RAG;
- pgvector;
- cache por hash;
- roteamento por tarefa;
- registro de proveniência.

## 6.9. BIM e CAD

- IfcOpenShell;
- xeokit ou IFC.js;
- ezdxf;
- PDF.js;
- OpenCV;
- Shapely;
- GDAL;
- PostGIS.

DWG será adiado até existir demanda paga e solução licenciada adequada.

---

# 7. Subsistema de Operação Regulatória

A inclusão de normas municipais não deverá depender permanentemente de cadastro manual.

O sistema deverá evoluir para um modelo semiautônomo.

## 7.1. Objetivo

Localizar, baixar, organizar, interpretar, validar e monitorar normas aplicáveis por município.

## 7.2. Componentes

### Coletor regulatório

Localiza fontes oficiais:

- prefeitura;
- Câmara;
- portal de legislação;
- diário oficial;
- portal de licenciamento;
- mapas municipais;
- geosserviços;
- Corpo de Bombeiros;
- órgãos estaduais;
- órgãos federais.

### Catálogo regulatório

Armazena:

- documento;
- número;
- tipo;
- órgão;
- URL;
- hash;
- data de consulta;
- vigência;
- revogação;
- documento substituído;
- município;
- estado;
- tema;
- versão.

### Extrator regulatório

Usa OCR e IA para identificar parâmetros, exceções, condições, artigos, tabelas, fórmulas, documentos obrigatórios e mapas referenciados.

### Validador técnico

O validador deverá confirmar fonte e vigência, revisar interpretação, registrar exceções, confirmar aplicabilidade e publicar ou rejeitar a regra.

### Motor de regras

Executa apenas regras em estado vigente.

### Monitor regulatório

Verifica novas leis, alterações, revogações, decretos, novos formulários, mudanças em páginas e mapas, links quebrados e fontes indisponíveis.

Quando houver alteração, a regra deverá ser marcada como potencialmente afetada, suspensa quando necessário e encaminhada para revisão.

## 7.3. Estados do documento regulatório

```text
descoberto
baixado
catalogado
em_processamento
processado
validado
substituido
revogado
indisponivel
```

## 7.4. Estados da regra

```text
rascunho_extraido_por_ia
em_validacao
vigente
suspensa
revogada
substituida
```

## 7.5. Regra de segurança

Nenhuma regra em rascunho poderá ser aplicada em relatório entregue ao cliente.

## 7.6. Exemplo de regra

```yaml
rule_id: lajeado_recuo_frontal_z2
jurisdiction: BR-RS-4311403
applies_to:
  building_type:
    - residencial_unifamiliar
    - residencial_geminado
  zone:
    - Z2
  conditions:
    - field: pavimentos
      operator: "<="
      value: 3
check:
  field: recuo_frontal
  operator: ">="
  value: 4.0
  unit: m
  tolerance: 0.02
severity: bloqueio
evidence_required:
  - implantacao
  - quadro_areas
source:
  document: "Plano Diretor"
  article: "Artigo correspondente"
effective_from: 2026-01-01
effective_until: null
validated_by: "Responsável técnico"
```

## 7.7. Estados da verificação

- conforme;
- não conforme;
- atenção;
- não aplicável;
- não verificável.

O estado **não verificável** deve aparecer com destaque.

## 7.8. Níveis de automação

### Nível 1 — Manual assistido

Cadastro inicial, regras estruturadas manualmente e município-piloto.

### Nível 2 — Extração assistida

Busca automática, download, OCR, sugestão de regra e validação humana.

### Nível 3 — Monitoramento autônomo

Detecção de alteração, comparação, criação de tarefa, suspensão preventiva e atualização após validação.

## 7.9. Expansão por rede de validadores

Futuramente, o sistema poderá operar com validadores locais, revisão dupla, remuneração por regra ou município, biblioteca certificada e compartilhamento de receita.

---

# 8. Módulos do sistema

## 8.1. Organizações e usuários

Empresas, filiais, equipes, usuários, perfis, permissões, convites, MFA, logs, auditoria, planos, limites e contratação modular.

## 8.2. Cadastro de empreendimento

Endereço, coordenadas, município, código IBGE, lote, quadra, matrícula, inscrição, zoneamento, proprietário, contratante, responsáveis, uso, área, pavimentos, unidades, tipologia e situação do licenciamento.

## 8.3. Gestão documental

Upload, classificação, OCR, tags, metadados, versionamento, estados, visualização, busca, aprovação, assinatura, hash, histórico, documento vigente, QR Code, distribuição e bloqueio de versão obsoleta.

## 8.4. Pré-análise legal

Seleção de jurisdição, regras aplicáveis, checklist documental, cálculo urbanístico, inconsistências, acessibilidade inicial, requisitos de PPCI, relatório, evidências, fontes, confiança, não verificáveis e validação humana.

## 8.5. Tramitação

Protocolo, número, data, status, notificações, exigências, tarefas, prazos, resposta, revisão, reanálise e histórico.

## 8.6. Controle de versões

Estados, comparação, sobreposição, alterações, autor, motivo, aprovação, publicação, linha de base, obsolescência e as built.

## 8.7. Grafo de propagação de impacto

Nós:

- elemento de projeto;
- quantitativo;
- item de orçamento;
- atividade;
- compra;
- contrato;
- medição;
- fluxo de caixa.

Arestas:

- automática;
- proposta;
- manual.

Fluxo:

1. detectar alteração;
2. localizar dependências;
3. marcar impactos;
4. gerar proposta;
5. calcular deltas;
6. aprovar item a item;
7. publicar nova versão.

## 8.8. EAP

Etapas, subetapas, pacotes, serviços, ambientes, unidades, entregáveis, responsáveis, predecessoras e critérios de conclusão.

## 8.9. Quantitativos

Manual, planilha, IFC, PDF assistido, memória de cálculo, perda, versão, origem, validação e comparação.

## 8.10. Orçamento

Insumos, composições, produtividade, equipamentos, mão de obra, custos, BDI, impostos, margem, curva ABC, cenários, orçamento-base, realizado, comprometido e custo final estimado.

## 8.11. Cronograma

Gantt, CPM, predecessoras, marcos, calendários, produtividade, caminho crítico, linha de balanço, baseline, reprogramação, físico-financeiro e lookahead.

## 8.12. Diário de obra

Texto, áudio, fotos, equipe, clima, equipamentos, serviços, ocorrências, assinatura, aprovação e relatório.

## 8.13. Tarefas

Kanban, prazo, prioridade, responsável, dependências, evidências, aprovação, recorrência e escalonamento.

## 8.14. Fotos e mídia

Captura, compressão, classificação, ambiente, serviço, comparação, anotação, relatório e vínculo.

## 8.15. Inspeções e qualidade

Checklists, critérios, evidências, tolerâncias, aprovação, não conformidade, correção, reinspeção e bloqueio controlado.

## 8.16. Compras

Solicitação, aprovação, cotação, comparação, pedido, entrega, nota, devolução, pagamento e avaliação.

## 8.17. Fornecedores

Cadastro, categorias, documentos, propostas, desempenho, atrasos, qualidade e bloqueios.

## 8.18. Estoque

Entrada, saída, saldo, transferência, reserva, inventário, perdas, lote, localização e rastreabilidade.

## 8.19. Financeiro de obra

Contas, centros de custo, fluxo, competência, caixa, retenções, impostos, projeções, custo comprometido, custo realizado e margem.

## 8.20. Contratos e medições

Escopo, valor, prazo, retenção, reajuste, aditivo, medição, aprovação, pagamento e saldo.

## 8.21. Equipes e produtividade

Equipe, função, presença, horas, produção, produtividade, custo, medição e avaliação.

## 8.22. Portal do cliente

Andamento, fotos, cronograma, documentos, pagamentos, aprovações, escolhas, solicitações e histórico.

## 8.23. Alterações e aditivos

Solicitação, origem, impacto, custo, prazo, aprovação, assinatura e atualização.

## 8.24. Reuniões inteligentes

Gravação, transcrição, resumo, decisões, tarefas, prazos, participantes e ata.

## 8.25. Copiloto diário

Prioridades, atrasos, riscos, compras, pagamentos, inspeções, aprovações e recomendações.

## 8.26. Incorporação

Empreendimento comercial, unidades, estoque, tabela de venda, VGV, contratos, parcelas, correções, distratos, permutas, RET, patrimônio de afetação, índices, margem, TIR, exposição de caixa e velocidade de vendas.

## 8.27. Entrega e pós-obra

Vistoria, pendências, aceite, manual, garantias, as built, chamados, manutenção, SLA e histórico.

---

# 9. Roadmap consolidado

## Estágio 0 — Concierge

Pré-análise manual, projetos reais, cobrança, corpus, relatório, regras iniciais e validação de mercado.

## Estágio 1 — Copiloto de Aprovação + Núcleo Documental

Organizações, usuários, empreendimento, documentos, versões, linha de base, biblioteca regulatória de Lajeado, regras, checklist, relatório, tramitação, validação humana, portal básico e QR Code.

## Estágio 2 — Núcleo operacional

EAP, tarefas, pendências, diário, fotos, inspeções, PWA, painel diário, portal do cliente e uso em obra real.

## Estágio 3 — Custos, planejamento e campo nativo

Quantitativos, orçamento, cronograma, compras, fornecedores, financeiro, contratos, medições, incorporação, app nativo e engine de sincronização.

## Estágio 4 — Copiloto de IA

Transcrição, reuniões, RAG, assistente, priorização, comparação de revisões, extração de tarefas e relatórios.

## Estágio 5 — BIM e propagação avançada

IFC, visualizador, quantitativos, elementos, grafo de impacto, integração com orçamento, integração com cronograma e revisão automática proposta.

## Estágio 6 — Expansão regulatória

Novos municípios, coleta automática, monitoramento, rede de validadores, acessibilidade aprofundada, PPCI e novas tipologias.

## Estágio 7 — Inteligência preditiva

Previsão de atraso, custo final, produtividade, risco, visão computacional, tendências e benchmarking.

---

# 10. Critérios de decisão por estágio

## Portão 0 → 1

Projetos pagos, recorrência, taxa mínima de previsão e dor confirmada.

## Portão 1 → 2

Clientes ativos, relatórios aceitos, motor com cobertura mínima e tempo de análise reduzido.

## Portão 2 → 3

Obras usando diariamente, adesão de campo, informações úteis e baixa dependência de planilhas.

## Portão 3 → 4

Dados estruturados suficientes, uso recorrente e custo operacional controlado.

## Portão 4 → 5

Demanda real por BIM, disponibilidade de IFC e dados consistentes.

## Portão 5 → 6

Método regulatório validado, custo por município conhecido e rede de validação possível.

---

# 11. Métricas

## Aprovação

- ciclos de notificação;
- dias até alvará;
- recall de bloqueios;
- precisão;
- cobertura;
- não verificáveis;
- falsos negativos críticos.

## Gestão

- tempo de diário;
- adesão;
- tarefas concluídas;
- uso de versão vigente;
- planilhas paralelas.

## Custos

- desvio;
- compras emergenciais;
- custo comprometido;
- margem;
- previsão final.

## IA

- taxa de aceitação;
- custo por obra;
- custo por análise;
- correções humanas;
- tempo economizado.

## Regulação

- tempo de cadastro;
- tempo de manutenção;
- regras vigentes;
- alterações detectadas;
- regras suspensas;
- cobertura por município.

---

# 12. Segurança

- RLS;
- MFA;
- criptografia;
- backups;
- restauração;
- logs;
- retenção;
- LGPD;
- gestão de segredos;
- antivírus;
- auditoria;
- proveniência;
- segregação;
- limites por plano.

Para relatórios normativos:

- aviso de não substituição do responsável técnico;
- fonte;
- confiança;
- lista de não verificáveis;
- validação;
- limitação de responsabilidade;
- avaliação de seguro E&O;
- revisão jurídica contratual.

---

# 13. Equipe recomendada

## Inicial

- Product Owner/engenheiro;
- full-stack sênior;
- backend/IA;
- designer parcial;
- especialista normativo;
- QA parcial.

## Expansão

- mobile;
- BIM/CAD;
- DevOps;
- implantação;
- Customer Success;
- financeiro/incorporação;
- rede de validadores.

---

# 14. Decisões recomendadas

1. Começar por serviço manual.
2. Lajeado como município-piloto.
3. Pré-análise como porta de entrada.
4. Manter núcleo documental e linha de base desde o início.
5. Gestão de obra entra após validação.
6. Sistema modular e vendável por módulos.
7. PWA inicialmente; app nativo após uso de campo comprovado.
8. IFC preparado, mas BIM avançado adiado.
9. IA apenas assistiva.
10. Regras publicadas somente após validação humana.
11. Busca e monitoramento normativo semiautônomos.
12. Grafo de impacto como módulo central.
13. Camada de incorporação incluída para atender a Delta.
14. Desenvolvimento por portões de decisão.
15. Nenhuma alteração silenciosa em orçamento, cronograma ou quantitativos.

---

# 15. Próximos passos concretos

1. Selecionar os primeiros projetos do serviço concierge.
2. Definir modelo padrão do relatório.
3. Catalogar exigências anteriores de Lajeado.
4. Criar planilha inicial de regras.
5. Definir tipologias atendidas.
6. Medir tempo atual de análise.
7. Medir ciclos de notificação.
8. Validar disposição a pagar.
9. Criar backlog do Estágio 1.
10. Criar modelo de dados regulatório.
11. Definir o primeiro conjunto de regras.
12. Especificar a tela de validação humana.
13. Definir política de publicação e revisão.
14. Prototipar coleta e monitoramento das normas.
15. Iniciar desenvolvimento apenas após o Portão 0.
