"""Testes do comando flask executar-sql (divisão dos scripts .sql)."""
from salao.cli import _dividir_script


def test_scripts_do_projeto_sao_divididos_corretamente():
    for arquivo, esperado in (("database/schema.sql", 20), ("database/seed.sql", 13)):
        with open(arquivo, encoding="utf-8") as f:
            comandos = _dividir_script(f.read())
        assert len(comandos) == esperado
        assert all(c.split()[0] in ("SET", "DROP", "CREATE", "INSERT", "ALTER") for c in comandos)


def test_comentarios_e_use_sao_ignorados():
    script = """
    CREATE DATABASE x;  -- comentário após o ponto e vírgula
    USE x;
    -- comentário com ; dentro
    INSERT INTO t VALUES ('a'); -- fim
    """
    assert _dividir_script(script) == ["INSERT INTO t VALUES ('a')"]
