from scripts.convert_ir import inspect_ir, tail_text


def test_tail_text_decodes_timeout_bytes() -> None:
    assert tail_text(b"prefix-\xff-error", limit=8) == "-�-error"


def test_ir_inspection_is_bounded_and_summarized(tmp_path) -> None:
    xml = tmp_path / "model.xml"
    xml.write_text(
        "<net version='10'><layers>"
        "<layer id='0' name='input' type='Parameter' version='opset1'/>"
        "<layer id='1' name='conv' type='Convolution' version='opset1'/>"
        "</layers></net>",
        encoding="utf-8",
    )

    report = inspect_ir(xml)

    assert report["layer_count"] == 2
    assert report["operator_counts"] == {"Convolution": 1, "Parameter": 1}
    assert "layers" not in report
