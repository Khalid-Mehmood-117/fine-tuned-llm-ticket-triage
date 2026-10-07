"""The committed training notebook must have no outputs and no hard-coded secrets."""

import json
import re
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "train.ipynb"


def load():
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def test_notebook_has_no_outputs():
    for cell in load()["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == []
            assert cell["execution_count"] is None


def test_notebook_has_no_tokens():
    text = NOTEBOOK.read_text(encoding="utf-8")
    assert not re.search(r"hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}", text)


def test_settings_cell_comes_first_and_reads_token_from_secrets():
    code_cells = ["".join(c["source"]) for c in load()["cells"] if c["cell_type"] == "code"]
    assert 'HF_TOKEN_SECRET = "HF_TOKEN"' in code_cells[0]
    assert "ADAPTER_REPO = " in code_cells[0]
    assert any("userdata.get(HF_TOKEN_SECRET)" in c for c in code_cells)


def test_install_cell_removes_torchao_before_peft_is_imported():
    code_cells = ["".join(c["source"]) for c in load()["cells"] if c["cell_type"] == "code"]
    install = code_cells[1]
    assert '"uninstall", "-y", "-q", "torchao"' in install
    assert 'find_spec("torchao") is not None' in install
    imports_peft = re.compile(r"^\s*(from|import)\s+(peft|trl|triage\.qwen_local)\b", re.MULTILINE)
    assert not imports_peft.search(install)
    first_peft_import = next(i for i, c in enumerate(code_cells) if imports_peft.search(c))
    assert first_peft_import > 1
