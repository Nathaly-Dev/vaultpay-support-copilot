"""Mascara CPF, e-mail e telefone antes de o texto ir para o LLM ou para o banco (LGPD)."""

import re
from dataclasses import dataclass, field

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

# CPF com pontuação: 123.456.789-09
_CPF_FORMATTED = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")

# Telefone: só casa formatos que parecem telefone, para não apagar valores e prazos.
_PHONE = re.compile(
    r"(?<![\d(])"
    r"(?:"
    r"(?:\+55\s?)?\(\d{2}\)\s?9?\d{4}-?\d{4}"  # (11) 91234-5678
    r"|(?:\+55\s?)?\d{2}\s9\d{4}-?\d{4}"  # 11 91234-5678
    r"|\+55\s?\d{2}\s?9?\d{4}-?\d{4}"  # +55 11 91234-5678
    r"|9?\d{4}-\d{4}"  # 91234-5678 (sem DDD)
    r")"
    r"(?!\d)"
)

# 11 dígitos colados: pode ser CPF ou celular com DDD.
_ELEVEN_DIGITS = re.compile(r"(?<!\d)\d{11}(?!\d)")


@dataclass(frozen=True)
class MaskResult:
    text: str
    # Quantos de cada tipo foram mascarados (nunca os valores), seguro para log.
    found: dict[str, int] = field(default_factory=dict)


def mask_pii(text: str) -> MaskResult:
    found: dict[str, int] = {}

    def replace(label: str):
        def _sub(match: re.Match) -> str:
            found[label] = found.get(label, 0) + 1
            return f"[{label}]"

        return _sub

    def replace_eleven_digits(match: re.Match) -> str:
        digits = match.group()
        if _is_valid_cpf(digits):
            label = "CPF"
        elif _looks_like_mobile(digits):
            label = "TELEFONE"
        else:
            label = "CPF"  # na dúvida, mascara como o mais sensível
        found[label] = found.get(label, 0) + 1
        return f"[{label}]"

    # A ordem importa: e-mail primeiro, para o telefone não pegar números dentro dele.
    text = _EMAIL.sub(replace("EMAIL"), text)
    text = _CPF_FORMATTED.sub(replace("CPF"), text)
    text = _PHONE.sub(replace("TELEFONE"), text)
    text = _ELEVEN_DIGITS.sub(replace_eleven_digits, text)
    return MaskResult(text=text, found=found)


def _is_valid_cpf(digits: str) -> bool:
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for size in (9, 10):
        total = sum(int(d) * w for d, w in zip(digits[:size], range(size + 1, 1, -1), strict=True))
        check = (total * 10) % 11 % 10
        if check != int(digits[size]):
            return False
    return True


def _looks_like_mobile(digits: str) -> bool:
    # DDD (2 dígitos, não começa com 0) + 9 + 8 dígitos.
    return digits[0] != "0" and digits[2] == "9"
