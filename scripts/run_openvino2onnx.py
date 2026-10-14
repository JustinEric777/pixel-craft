"""Run openvino2onnx with a compatibility shim for modern ONNX packages."""

from __future__ import annotations

import runpy
import sys
import types


def install_onnx_mapping_shim() -> None:
    import onnx

    try:
        from onnx import _mapping
    except ImportError:
        return
    mapping = sys.modules.get("onnx.mapping")
    if mapping is None:
        mapping = types.ModuleType("onnx.mapping")
        mapping.TENSOR_TYPE_MAP = _mapping.TENSOR_TYPE_MAP
        sys.modules["onnx.mapping"] = mapping
    onnx.mapping = mapping


def install_fake_quantize_compatibility() -> None:
    """Accept OpenVINO FakeQuantize levels such as 255 without patching the package."""
    import numpy as np
    from onnx.helper import make_node
    from onnx.mapping import TENSOR_TYPE_MAP
    from openvino2onnx.domain.intel.openvino.passes import make_constant
    from openvino2onnx.domain.intel.openvino.passes.op.fake_quantize import FakeQuantize

    def replace(self, graph, ori_node):
        levels = int(self.get_attribute(ori_node, "levels") or 256)
        nbits = int(np.ceil(np.log2(max(levels, 2))))
        if nbits not in (8, 16, 32):
            raise ValueError(f"unsupported FakeQuantize levels={levels} (nbits={nbits})")
        is_weight_quantizer = "weight" in ori_node.name.lower()

        def quant_range(value):
            return self.get_value_or_die(value).squeeze()

        input_low = quant_range(ori_node.input[1])
        input_high = quant_range(ori_node.input[2])
        output_low = quant_range(ori_node.input[3])
        output_high = quant_range(ori_node.input[4])

        try:
            scale_type = graph.tensor_type(ori_node.output[0])
            scale_prec = TENSOR_TYPE_MAP[scale_type].np_dtype
        except ValueError:
            scale_prec = np.float32
        zero_prec = np.iinfo(f"uint{nbits}").dtype
        scales = ((input_high - input_low) / (levels - 1)).astype(scale_prec)
        zero_points = np.rint((levels - 1) * input_low / (input_low - input_high))
        zero_points = zero_points.astype(zero_prec)
        scale_node = make_constant(f"{ori_node.name}/QuantizeLinear_y_scale", scales)
        zp_node = make_constant(
            f"{ori_node.name}/QuantizeLinear_y_zero_point", zero_points
        )
        quantize_linear = make_node(
            "QuantizeLinear",
            inputs=[ori_node.input[0], scale_node.output[0], zp_node.output[0]],
            outputs=[f"{ori_node.name}/QuantizeLinear_output0"],
            name=f"{ori_node.name}/QuantizeLinear",
        )
        self += [scale_node, zp_node, quantize_linear]

        scales = ((output_high - output_low) / (levels - 1)).astype(scale_prec)
        zero_points = np.rint((levels - 1) * output_low / (output_low - output_high))
        zero_points = zero_points.astype(zero_prec)
        scale_node = make_constant(f"{ori_node.name}/DequantizeLinear_y_scale", scales)
        zp_node = make_constant(
            f"{ori_node.name}/DequantizeLinear_y_zero_point", zero_points
        )
        self += [scale_node, zp_node]
        dequantize_attributes = {"axis": 0} if is_weight_quantizer and scales.ndim == 1 else {}
        return make_node(
            "DequantizeLinear",
            inputs=[quantize_linear.output[0], scale_node.output[0], zp_node.output[0]],
            outputs=ori_node.output,
            name=ori_node.name,
            **dequantize_attributes,
        )

    FakeQuantize.replace = replace


def install_topk_compatibility() -> None:
    """Map OpenVINO's index sort to unsorted ONNX TopK for K=1 argmax graphs."""
    import numpy as np
    from onnx.helper import make_node
    from onnx.onnx_pb import TensorProto
    from openvino2onnx.domain.intel.openvino.passes import cast_in, cast_out, make_constant
    from openvino2onnx.domain.intel.openvino.passes.op.topk import TopK

    def replace(self, graph, ori_node):
        if graph.tensor_type(ori_node.input[1]) == TensorProto.INT32:
            self += cast_in(ori_node, 1, TensorProto.INT64)
        k_shape = make_constant(f"{ori_node.name}/Kshape", np.array([1], dtype=np.int64))
        reshape_k = make_node(
            "Reshape",
            inputs=[ori_node.input[1], k_shape.output[0]],
            outputs=[f"{ori_node.name}/Reshape/K"],
            name=f"{ori_node.name}/Reshape",
        )
        ori_node.input[1] = reshape_k.output[0]
        self += [k_shape, reshape_k]
        if self.get_attribute(ori_node, "index_element_type") == "i32":
            self += cast_out(ori_node, 1, TensorProto.INT32)
        axis = int(self.get_attribute(ori_node, "axis"))
        mode = self.get_attribute(ori_node, "mode")
        return make_node(
            "TopK",
            inputs=ori_node.input,
            outputs=ori_node.output,
            name=ori_node.name,
            axis=axis,
            largest=1 if mode == "max" else 0,
            sorted=0,
        )

    TopK.replace = replace


def install_strided_slice_compatibility() -> None:
    """Treat empty OpenVINO begin/end masks as an all-zero mask."""
    from openvino2onnx.domain.intel.openvino.passes.op.strided_slice import StridedSlice

    original_replace = StridedSlice.replace

    def replace(self, graph, ori_node):
        for attribute in ori_node.attribute:
            if attribute.name in {"begin_mask", "end_mask"} and not attribute.s:
                attribute.s = b"0"
        return original_replace(self, graph, ori_node)

    StridedSlice.replace = replace


def install_interpolate_compatibility() -> None:
    """Map OpenVINO's ``simple`` nearest mode to ONNX Runtime's ``floor`` mode."""
    from openvino2onnx.domain.intel.openvino.passes.op.interpolate import Interpolate

    original_replace = Interpolate.replace

    def replace(self, graph, ori_node):
        for attribute in ori_node.attribute:
            if attribute.name == "nearest_mode" and attribute.s == b"simple":
                attribute.s = b"floor"
        return original_replace(self, graph, ori_node)

    Interpolate.replace = replace


def install_trivial_operator_compatibility() -> None:
    """Preserve semantics for IR operators handled by the package's trivial pass."""
    from onnx.helper import make_node
    from openvino2onnx.domain.intel.openvino.passes.op.trivial import Trivial

    original_replace = Trivial.replace

    def replace(self, graph, ori_node):
        if ori_node.op_type == "Einsum":
            equation = self.get_attribute(ori_node, "equation")
            return make_node(
                "Einsum",
                inputs=ori_node.input,
                outputs=ori_node.output,
                name=ori_node.name,
                equation=equation,
            )
        if ori_node.op_type == "ConvertLike":
            return make_node(
                "CastLike",
                inputs=ori_node.input,
                outputs=ori_node.output,
                name=ori_node.name,
            )
        return original_replace(self, graph, ori_node)

    Trivial.replace = replace


if __name__ == "__main__":
    install_onnx_mapping_shim()
    install_fake_quantize_compatibility()
    install_topk_compatibility()
    install_strided_slice_compatibility()
    install_interpolate_compatibility()
    install_trivial_operator_compatibility()
    runpy.run_module("openvino2onnx.__main__", run_name="__main__")
