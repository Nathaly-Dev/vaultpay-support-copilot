import pytest

from vaultpay_copilot.rag.pii import mask_pii

# Todos os números abaixo são fictícios (CPF de exemplo com dígitos verificadores válidos).


@pytest.mark.parametrize(
    "texto",
    ["123.456.789-09", "12345678909"],
    ids=["formatado", "colado"],
)
def test_mascara_cpf_valido(texto):
    result = mask_pii(f"Meu CPF é {texto}, posso parcelar?")

    assert result.text == "Meu CPF é [CPF], posso parcelar?"
    assert result.found == {"CPF": 1}


def test_cpf_valido_com_terceiro_digito_9_nao_vira_telefone():
    # Começa como um celular (DDD + 9...), mas os dígitos verificadores provam que é CPF.
    assert mask_pii("12934567800").text == "[CPF]"


def test_cpf_invalido_colado_tambem_e_mascarado():
    # Pode ser um CPF digitado errado; na dúvida, mascara (falha fechada).
    assert mask_pii("12345678900").text == "[CPF]"


def test_mascara_email():
    result = mask_pii("Escreva para ana.silva@example.com por favor")

    assert result.text == "Escreva para [EMAIL] por favor"
    assert result.found == {"EMAIL": 1}


def test_email_com_numeros_nao_vira_telefone():
    assert mask_pii("11912345678@example.com").text == "[EMAIL]"


@pytest.mark.parametrize(
    "telefone",
    [
        "(11) 91234-5678",
        "(11) 1234-5678",
        "(11)91234-5678",
        "11 91234-5678",
        "+55 11 91234-5678",
        "+5511912345678",
        "91234-5678",
        "1234-5678",
    ],
)
def test_mascara_telefone_em_varios_formatos(telefone):
    result = mask_pii(f"Me liguem em {telefone} hoje")

    assert result.text == "Me liguem em [TELEFONE] hoje"
    assert result.found == {"TELEFONE": 1}


def test_celular_colado_com_ddd_vira_telefone():
    assert mask_pii("11912345678").text == "[TELEFONE]"


def test_mascara_varios_dados_no_mesmo_texto():
    result = mask_pii("CPF 123.456.789-09, e-mail ana@example.com, tel (11) 91234-5678")

    assert result.text == "CPF [CPF], e-mail [EMAIL], tel [TELEFONE]"
    assert result.found == {"CPF": 1, "EMAIL": 1, "TELEFONE": 1}


def test_valor_original_nao_aparece_no_resultado_nem_no_contador():
    result = mask_pii("CPF 123.456.789-09 e ana@example.com")

    assert "123.456.789-09" not in result.text and "ana@example.com" not in result.text
    assert all(isinstance(v, int) for v in result.found.values())


def test_mascarar_duas_vezes_da_o_mesmo_resultado():
    uma_vez = mask_pii("CPF 123.456.789-09 tel (11) 91234-5678").text

    assert mask_pii(uma_vez).text == uma_vez


@pytest.mark.parametrize(
    "texto",
    [
        "O limite diário é de R$ 5.000,00.",
        "Entre 20h e 6h o limite é R$ 1.000,00.",
        "A análise leva até 10 dias úteis.",
        "Prazo de 30 dias corridos e 72 horas.",
        "Vigência desde 2026-01-01.",
        "Veja o Art. 2 da política.",
        "Um Pix de 12345678 reais?",
        "Cartão com final 1234.",
        "Posso cadastrar até 5 chaves?",
    ],
)
def test_nao_apaga_valores_prazos_e_datas(texto):
    result = mask_pii(texto)

    assert result.text == texto
    assert result.found == {}


def test_texto_sem_dados_pessoais_fica_igual():
    assert (
        mask_pii("Como faço para bloquear meu cartão?").text
        == "Como faço para bloquear meu cartão?"
    )
