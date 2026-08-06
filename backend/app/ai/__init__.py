"""Camada de IA do Atlas (§3.3, §6.8).

- `provider` — abstração sobre o modelo, com ausência declarada como padrão;
- `retrieval` — recuperação sobre o catálogo (o "R" do RAG);
- `schemas` — contratos de saída validados por Pydantic;
- `service` — orquestração, conferência de citações e proveniência.

A IA propõe; quem publica é uma pessoa (§7.5).
"""
