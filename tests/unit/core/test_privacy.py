from claims_agents.core.privacy import is_valid_cpf, mask_cpf, mask_phone, mask_text


def test_mask_cpf_keeps_last_two_digits() -> None:
    assert mask_cpf("123.456.789-09") == "***.***.***-09"
    assert mask_cpf("123") == "***"


def test_mask_phone() -> None:
    assert mask_phone("+5511900000001") == "(**) *****-0001"


def test_mask_text_hides_cpf_phone_and_email() -> None:
    text = "CPF 52998224725, tel +55 11 91234-5678, email ana.silva@exemplo.invalid"
    masked = mask_text(text)
    assert "52998224725" not in masked
    assert "91234-5678" not in masked
    assert "ana.silva@" not in masked
    assert "***.***.***-25" in masked
    assert "a***@exemplo.invalid" in masked


def test_cpf_check_digits() -> None:
    assert is_valid_cpf("529.982.247-25")
    assert not is_valid_cpf("529.982.247-24")
    assert not is_valid_cpf("111.111.111-11")
