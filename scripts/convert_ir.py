"""Convert OpenVINO IR artifacts in an isolated conversion environment."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def inspect_ir(xml_path: Path) -> dict[str, object]:
    root = ET.parse(xml_path).getroot()
    layers = root.find("layers")
    operator_counts: Counter[str] = Counter()
    operator_examples: dict[str, list[str]] = {}
    if layers is not None:
        for layer in layers.findall("layer"):
            operator = layer.attrib.get("type", "unknown")
            operator_counts[operator] += 1
            examples = operator_examples.setdefault(operator, [])
            if len(examples) < 3:
                examples.append(layer.attrib.get("name", ""))
    return {
        "xml": str(xml_path),
        "bin": str(xml_path.with_suffix(".bin")),
        "version": root.attrib.get("version"),
        "layer_count": sum(operator_counts.values()),
        "operator_counts": dict(sorted(operator_counts.items())),
        "operator_examples": dict(sorted(operator_examples.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("xml", type=Path)
    parser.add_argument("--source-onnx", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="per-model converter timeout in seconds (default: 600)",
    )
    args = parser.parse_args()
    if args.batch:
        if args.output_dir is None:
            parser.error("--batch requires --output-dir")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        reports = []
        for xml_path in sorted(args.xml.glob("*.xml")):
            if not xml_path.with_suffix(".bin").is_file():
                continue
            output = args.output_dir / f"{xml_path.stem}.onnx"
            result = convert_one(xml_path, output, timeout=args.timeout)
            reports.append(result)
        report_path = args.output_dir / "conversion-report.json"
        report_path.write_text(
            json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        successful = {"converted", "existing"}
        print(
            json.dumps(
                {
                    "count": len(reports),
                    "converted": sum(x["status"] in successful for x in reports),
                    "failed": sum(x["status"] == "failed" for x in reports),
                    "timeout": sum(x["status"] == "timeout" for x in reports),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.output is None:
        parser.error("single-model mode requires --output")
    if args.output_dir is not None:
        parser.error("--output-dir is only valid with --batch")
    result = convert_one(args.xml, args.output, args.source_onnx, timeout=args.timeout)
    args.output.with_suffix(args.output.suffix + ".report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if result["status"] not in {"converted", "existing", "source_onnx_selected"}:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    return 0


def convert_one(
    xml_path: Path,
    output: Path,
    source_onnx: Path | None = None,
    *,
    timeout: int = 600,
) -> dict[str, object]:
    report: dict[str, object] = {"status": "blocked", **inspect_ir(xml_path), "output": str(output)}
    if source_onnx:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_onnx, output)
        validation = validate_converted_model(output)
        report.update(
            {
                "status": "source_onnx_selected"
                if validation["status"] == "runtime-loadable"
                else "failed",
                "source_onnx": str(source_onnx),
                "validation": validation,
            }
        )
        return report
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file() and output.stat().st_size > 0:
        normalize_axes_constants(output)
        normalize_resize_sizes(output, xml_path)
        validation = validate_converted_model(output)
        report.update(
            {
                "status": "existing"
                if validation["status"] == "runtime-loadable"
                else "failed",
                "reason": "non_empty_output_exists",
                "validation": validation,
            }
        )
        return report
    try:
        wrapper = Path(__file__).with_name("run_openvino2onnx.py")
        completed = subprocess.run(
            [sys.executable, str(wrapper), str(xml_path), str(output), "--uncheck"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        report.update(
            {
                "status": "timeout",
                "timeout_seconds": timeout,
                "stdout": tail_text(exc.stdout),
                "stderr": tail_text(exc.stderr),
                "error": "converter_timeout",
            }
        )
        return report
    except FileNotFoundError:
        report.update(
            {
                "status": "failed",
                "error": "openvino2onnx is not installed; run uv sync --group conversion",
            }
        )
        return report
    report["command_returncode"] = completed.returncode
    report["stdout"] = completed.stdout[-4000:]
    report["stderr"] = completed.stderr[-4000:]
    if completed.returncode != 0 or not output.exists():
        report.update({"status": "failed", "error": "converter_failed"})
        return report
    normalize_axes_constants(output)
    normalize_resize_sizes(output, xml_path)
    report["validation"] = validate_converted_model(output)
    if report["validation"]["status"] != "runtime-loadable":
        report.update({"status": "failed", "error": "converted_model_validation_failed"})
        return report
    report["status"] = "converted"
    return report


def tail_text(value: str | bytes | None, limit: int = 4000) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return (value or "")[-limit:]


def validate_converted_model(output: Path) -> dict[str, object]:
    """Require both ONNX structural validation and an ORT-loadable graph."""
    try:
        import onnx
        import onnxruntime as ort

        model = onnx.load(str(output), load_external_data=False)
        onnx.checker.check_model(model)
        session = ort.InferenceSession(str(output), providers=["CPUExecutionProvider"])
        return {
            "status": "runtime-loadable",
            "onnx_checker": "passed",
            "ort_session": "created",
            "inputs": [
                {"name": value.name, "shape": value.shape, "type": value.type}
                for value in session.get_inputs()
            ],
            "outputs": [
                {"name": value.name, "shape": value.shape, "type": value.type}
                for value in session.get_outputs()
            ],
        }
    except Exception as exc:  # noqa: BLE001 - preserve validation evidence
        return {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }


def normalize_axes_constants(output: Path) -> None:
    """Make scalar axes tensors valid ONNX vectors for Squeeze/Unsqueeze."""
    import numpy as np
    import onnx
    from onnx import numpy_helper

    model = onnx.load(str(output), load_external_data=True)
    consumers: dict[str, list[object]] = {}
    for node in model.graph.node:
        for input_name in node.input:
            consumers.setdefault(input_name, []).append(node)
    changed = False
    for node in model.graph.node:
        if node.op_type != "Constant" or len(node.output) != 1:
            continue
        dependent_nodes = consumers.get(node.output[0], [])
        if not dependent_nodes or any(
            dependent.op_type not in {"Squeeze", "Unsqueeze"}
            for dependent in dependent_nodes
        ):
            continue
        attribute = next((item for item in node.attribute if item.name == "value"), None)
        if attribute is None:
            continue
        value = numpy_helper.to_array(attribute.t)
        if value.ndim != 0 or not np.issubdtype(value.dtype, np.integer):
            continue
        attribute.t.CopyFrom(numpy_helper.from_array(value.reshape(1)))
        changed = True
    if changed:
        onnx.save(model, str(output))


def normalize_resize_sizes(output: Path, xml_path: Path) -> None:
    """Expand IR spatial ``sizes`` to full-rank values for ORT.

    openvino2onnx 1.1 emits opset-19 Resize nodes with a two-element sizes
    constant and an axes attribute. ONNX Runtime currently rejects that graph
    even though the source IR is unambiguous. Replacing the spatial sizes with
    the exact output port dimensions and dropping ``axes`` preserves the IR
    operation while avoiding a converter/runtime compatibility edge case.
    """
    import numpy as np
    import onnx
    from onnx import numpy_helper

    ir_root = ET.parse(xml_path).getroot()
    output_shapes: dict[str, list[int]] = {}
    layers = ir_root.find("layers")
    if layers is not None:
        for layer in layers.findall("layer"):
            if layer.attrib.get("type") != "Interpolate":
                continue
            output_ports = layer.find("output")
            if output_ports is None:
                continue
            port = output_ports.find("port")
            if port is None:
                continue
            output_shapes[layer.attrib.get("name", "")] = [
                int(dim.text or "0") for dim in port.findall("dim")
            ]

    model = onnx.load(str(output), load_external_data=True)
    producers = {name: node for node in model.graph.node for name in node.output}
    changed = False
    for node in model.graph.node:
        if node.op_type != "Resize" or node.name not in output_shapes or len(node.input) < 4:
            continue
        sizes_node = producers.get(node.input[3])
        if sizes_node is None or sizes_node.op_type != "Constant":
            continue
        attribute = next((item for item in sizes_node.attribute if item.name == "value"), None)
        if attribute is None:
            continue
        source_sizes = numpy_helper.to_array(attribute.t)
        target_sizes = output_shapes[node.name]
        if source_sizes.size != 2 or len(target_sizes) <= 2:
            continue
        attribute.t.CopyFrom(
            numpy_helper.from_array(np.asarray(target_sizes, dtype=source_sizes.dtype))
        )
        kept_attributes = [item for item in node.attribute if item.name != "axes"]
        del node.attribute[:]
        node.attribute.extend(kept_attributes)
        changed = True
    if changed:
        onnx.save(model, str(output))


if __name__ == "__main__":
    raise SystemExit(main())
