from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import numpy as np

from scripts import probe_openvino_ir


class _Dimension:
    is_static = True

    def __init__(self, value: int) -> None:
        self.value = value

    def get_length(self) -> int:
        return self.value


class _Rank:
    is_dynamic = False

    def get_length(self) -> int:
        return 4


class _Shape:
    rank = _Rank()

    def __getitem__(self, index: int) -> _Dimension:
        return _Dimension((1, 3, 2, 2)[index])


class _ElementType:
    def to_dtype(self) -> type[np.float32]:
        return np.float32


class _Port:
    any_name = "input"
    partial_shape = _Shape()
    element_type = _ElementType()


class _OutputPort:
    any_name = "output"


def test_probe_compiles_before_materializing_inputs(tmp_path: Path, monkeypatch) -> None:
    xml_path = tmp_path / "model.xml"
    bin_path = tmp_path / "model.bin"
    xml_path.touch()
    bin_path.touch()
    state = {"compiled": False}
    input_port = _Port()
    output_port = _OutputPort()
    model = SimpleNamespace(inputs=[input_port])

    class Compiled:
        outputs: ClassVar[list[_OutputPort]] = [output_port]

        def __call__(self, inputs):
            assert inputs["input"].shape == (1, 3, 2, 2)
            return {output_port: np.zeros((1, 1, 2, 2), dtype=np.float32)}

    class Core:
        def read_model(self, *_):
            return model

        def compile_model(self, *_):
            state["compiled"] = True
            return Compiled()

    original = probe_openvino_ir._input_value

    def guarded_input(port):
        assert state["compiled"] is True
        return original(port)

    monkeypatch.setattr(probe_openvino_ir, "_input_value", guarded_input)
    record = SimpleNamespace(id="model", path=xml_path, weights_path=bin_path)

    result = probe_openvino_ir._probe_record(Core(), record, "CPU")

    assert result["status"] == "ready"


def test_probe_rejects_non_finite_outputs(tmp_path: Path) -> None:
    xml_path = tmp_path / "model.xml"
    bin_path = tmp_path / "model.bin"
    xml_path.touch()
    bin_path.touch()
    input_port = _Port()
    output_port = _OutputPort()
    model = SimpleNamespace(inputs=[input_port])

    class Compiled:
        outputs: ClassVar[list[_OutputPort]] = [output_port]

        def __call__(self, _inputs):
            return {output_port: np.full((1, 1, 2, 2), np.nan, dtype=np.float32)}

    class Core:
        def read_model(self, *_):
            return model

        def compile_model(self, *_):
            return Compiled()

    record = SimpleNamespace(id="model", path=xml_path, weights_path=bin_path)

    result = probe_openvino_ir._probe_record(Core(), record, "CPU")

    assert result["status"] == "failed"
    assert result["error"] == "non-finite outputs: output"


def test_probe_accepts_evidenced_retirement_when_a_fallback_exists(
    tmp_path: Path, monkeypatch
) -> None:
    retired = SimpleNamespace(
        id="retired",
        logical_id="logical",
        format="openvino_ir",
        status="retired-invalid-source",
    )
    fallback = SimpleNamespace(id="fallback")

    class Registry:
        records: ClassVar[dict[str, object]] = {"retired": retired}

        def require(self, _model_id):
            return retired

        def resolve(self, logical_id, *, allow_openvino):
            assert logical_id == "logical"
            assert allow_openvino is False
            return fallback

    monkeypatch.setattr(probe_openvino_ir.ModelRegistry, "from_yaml", lambda _: Registry())
    monkeypatch.setattr(
        probe_openvino_ir,
        "_probe_record",
        lambda *_: {"id": "retired", "status": "failed", "error": "non-finite"},
    )
    import openvino

    monkeypatch.setattr(openvino, "Core", lambda: object())

    report = probe_openvino_ir.run(tmp_path / "model.yaml", "CPU")

    assert report["ready"] == 0
    assert report["retired"] == 1
    assert report["failed"] == 0
    assert report["results"][0]["fallback_model_id"] == "fallback"
