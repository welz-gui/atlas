"""O bloco de recall do relatório do Estágio 0 segue o contrato do §11:
sem base amostral o número é ausente — nunca 0, nunca 100%."""

from stage0_report import SEM_BASE, requirement_lines


def _sem_exigencia():
    return {
        "requirements_total": None,
        "requirements_linked_to_rules": None,
        "blocking_recall_percent": None,
        "critical_false_negatives": None,
    }


def test_sem_exigencia_nenhuma_o_recall_e_ausente_e_nao_cem_por_cento():
    texto = "\n".join(requirement_lines(_sem_exigencia()))

    assert texto.count(SEM_BASE) == 4
    assert "100" not in texto


def test_exigencia_que_nenhuma_regra_poderia_prever_nao_vira_recall():
    """Há exigência, mas nenhuma vinculada a regra: total existe, recall e falso negativo, não."""
    linhas = requirement_lines({**_sem_exigencia(), "requirements_total": 3, "requirements_linked_to_rules": 0})

    assert "3" in linhas[0]
    assert SEM_BASE not in linhas[0]
    assert SEM_BASE in linhas[2] and SEM_BASE in linhas[3]


def test_com_base_os_numeros_saem_como_vieram():
    linhas = requirement_lines(
        {
            "requirements_total": 5,
            "requirements_linked_to_rules": 4,
            "blocking_recall_percent": 75.0,
            "critical_false_negatives": 1,
        }
    )

    assert linhas[0].endswith("5") and linhas[1].endswith("4")
    assert linhas[2].endswith("75.0%")
    assert linhas[3].endswith("1")
    assert not any(SEM_BASE in linha for linha in linhas)