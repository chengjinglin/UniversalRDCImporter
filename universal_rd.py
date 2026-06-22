import sys, json, pickle, traceback
import numpy as np

try:
    import renderdoc as rd
except ModuleNotFoundError:
    print("Error: Cannot find the RenderDoc Module.")
    sys.exit(20)
except ImportError as err:
    print("Error: Failed to load the RenderDoc Module: {}".format(err))
    sys.exit(21)

from meshdata import makeMeshData
from profiling import Timer, profiling_counters
from rdutils import CaptureWrapper

_, CAPTURE_FILE, FILEPREFIX, MAX_BLOCKS_STR = sys.argv[:4]
MAX_BLOCKS = int(MAX_BLOCKS_STR)
MIN_INDICES = 30


def numpySave(array, file):
    np.array([array.ndim], dtype=np.int32).tofile(file)
    np.array(array.shape, dtype=np.int32).tofile(file)
    dt = array.dtype.descr[0][1][1:3].encode("ascii")
    file.write(dt)
    array.tofile(file)


def getAttributeCategory(name, attr_format, attr_index, all_attrs):
    name_lower = name.lower() if name else ""
    comp_count = attr_format.compCount
    is_float = attr_format.compType == rd.CompType.Float

    if any(kw in name_lower for kw in ["pos", "vert", "vertex", "vtx"]):
        return "position", 100
    if any(kw in name_lower for kw in ["norm", "nrm"]):
        return "normal", 100
    if any(kw in name_lower for kw in ["uv", "tex", "texcoord", "tc"]):
        return "uv", 100
    if any(kw in name_lower for kw in ["color", "col", "diffuse", "rgba", "rgb"]):
        return "color", 100
    if any(kw in name_lower for kw in ["tangent", "tan", "binorm", "bitan", "blend", "bone", "weight"]):
        return "extra", 100
    if is_float and comp_count == 3 and attr_index == 0:
        return "position", 60
    if is_float and comp_count == 3:
        return "position", 50
    if is_float and comp_count == 2:
        return "uv", 70
    if is_float and comp_count == 4:
        return "color", 40
    return "unknown", 0


class UniversalCaptureScraper:
    def __init__(self, controller):
        self.controller = controller

    def consolidateEvents(self, rootList, accumulator=None):
        if accumulator is None:
            accumulator = []
        for root in rootList:
            name = root.GetName(self.controller.GetStructuredFile())
            setattr(root, "name", name.split("::", 1)[-1])
            accumulator.append(root)
            self.consolidateEvents(root.children, accumulator)
        return accumulator

    def getShaderConstants(self, draw, state=None):
        controller = self.controller
        if state is None:
            controller.SetFrameEvent(draw.eventId, True)
            state = controller.GetPipelineState()
        shader = state.GetShader(rd.ShaderStage.Vertex)
        ep = state.GetShaderEntryPoint(rd.ShaderStage.Vertex)
        ref = state.GetShaderReflection(rd.ShaderStage.Vertex)
        constants = {}
        for cbn, cb in enumerate(ref.constantBlocks):
            block = {}
            cbuff = state.GetConstantBuffer(rd.ShaderStage.Vertex, cbn, 0)
            try:
                variables = controller.GetCBufferVariableContents(
                    state.GetGraphicsPipelineObject(), shader, rd.ShaderStage.Vertex, ep,
                    cb.bindPoint, cbuff.resourceId, 0, 0)
            except Exception:
                continue
            for var in variables:
                if var.members:
                    vals = []
                    if var.rows == 1:
                        for m in var.members:
                            vals.append(m.value.f32v[0])
                    else:
                        for m in var.members:
                            vals.append([m.value.f32v[c] for c in range(min(4, var.columns))])
                    block[var.name] = vals
                else:
                    if var.rows == 1:
                        block[var.name] = [var.value.f32v[c] for c in range(min(4, var.columns))]
                    else:
                        block[var.name] = [[var.value.f32v[r * 4 + c] for c in range(min(4, var.columns))] for r in range(var.rows)]
            constants[cb.name if cb.name else "$Globals"] = block
        return constants

    def extractAllTextures(self, drawcall_id, state):
        texture_files = []
        for stage in [rd.ShaderStage.Fragment, rd.ShaderStage.Vertex]:
            try:
                bindpoints = state.GetBindpointMapping(stage)
                if not bindpoints.samplers:
                    continue
                resources = state.GetReadOnlyResources(stage)
                for sampler_bind in bindpoints.samplers:
                    try:
                        rid = resources[sampler_bind.bind].resources[0].resourceId
                    except (IndexError, AttributeError):
                        continue
                    texsave = rd.TextureSave()
                    texsave.resourceId = rid
                    texsave.mip = 0
                    texsave.slice.sliceIndex = 0
                    texsave.alpha = rd.AlphaMapping.Preserve
                    texsave.destType = rd.FileType.PNG
                    fname = "{}{:05d}-texture_{}.png".format(FILEPREFIX, drawcall_id, len(texture_files))
                    self.controller.SaveTexture(texsave, fname)
                    texture_files.append(fname)
            except Exception:
                continue
        return texture_files

    def run(self):
        controller = self.controller
        drawcalls = self.consolidateEvents(controller.GetRootActions())

        total_calls = len(drawcalls)
        max_dc = total_calls if MAX_BLOCKS <= 0 else min(MAX_BLOCKS, total_calls)
        print("Total events: {}, extracting up to {}".format(total_calls, max_dc))

        manifest = {"capture_type": "Universal", "total_drawcalls": total_calls, "drawcalls": []}
        output_idx = 0

        for draw_idx in range(total_calls):
            if output_idx >= max_dc:
                break

            draw = drawcalls[draw_idx]
            timer = Timer()

            try:
                controller.SetFrameEvent(draw.eventId, True)
                state = controller.GetPipelineState()
            except Exception:
                continue

            attrs = state.GetVertexInputs()
            if len(attrs) == 0:
                continue

            ib = state.GetIBuffer()
            vbs = state.GetVBuffers()

            attr_info = []
            for i, attr in enumerate(attrs):
                cat, conf = getAttributeCategory(attr.name, attr.format, i, attrs)
                attr_info.append({"index": i, "name": attr.name, "category": cat, "confidence": conf,
                                  "compCount": attr.format.compCount, "compType": str(attr.format.compType)})

            def best_attr(category):
                candidates = [(a["confidence"], a["index"]) for a in attr_info if a["category"] == category]
                if not candidates:
                    return -1
                candidates.sort(reverse=True)
                return candidates[0][1]

            pos_idx = best_attr("position")
            normal_idx = best_attr("normal")
            uv_idx = best_attr("uv")
            color_idx = best_attr("color")

            if pos_idx < 0:
                for ai, a in enumerate(attrs):
                    if a.format.compCount >= 3 and a.format.compType == rd.CompType.Float:
                        pos_idx = ai
                        break
                if pos_idx < 0:
                    continue

            if uv_idx == pos_idx:
                alt_uv = -1
                for a in attr_info:
                    if a["index"] != pos_idx and a["category"] == "uv" and a["confidence"] >= 50:
                        alt_uv = a["index"]
                        break
                uv_idx = alt_uv if alt_uv >= 0 else -1

            try:
                meshes = [makeMeshData(attrs[i], ib, vbs, draw) for i in range(len(attrs))]

                m_pos = meshes[pos_idx]
                indices = m_pos.fetchIndices(controller)
                if len(indices) < MIN_INDICES:
                    continue
                with open("{}{:05d}-indices.bin".format(FILEPREFIX, output_idx), "wb") as f:
                    numpySave(indices, f)

                positions = m_pos.fetchData(controller)
                with open("{}{:05d}-positions.bin".format(FILEPREFIX, output_idx), "wb") as f:
                    numpySave(positions, f)

                has_normals = False
                if normal_idx >= 0 and normal_idx != pos_idx:
                    try:
                        normals = meshes[normal_idx].fetchData(controller)
                        with open("{}{:05d}-normals.bin".format(FILEPREFIX, output_idx), "wb") as f:
                            numpySave(normals, f)
                        has_normals = True
                    except Exception:
                        pass

                has_uvs = False
                if uv_idx >= 0 and uv_idx not in (pos_idx, normal_idx):
                    try:
                        uvs = meshes[uv_idx].fetchData(controller)
                        with open("{}{:05d}-uv.bin".format(FILEPREFIX, output_idx), "wb") as f:
                            numpySave(uvs, f)
                        has_uvs = True
                    except Exception:
                        pass

                has_colors = False
                if color_idx >= 0 and color_idx not in (pos_idx, normal_idx, uv_idx):
                    try:
                        colors = meshes[color_idx].fetchData(controller)
                        with open("{}{:05d}-colors.bin".format(FILEPREFIX, output_idx), "wb") as f:
                            numpySave(colors, f)
                        has_colors = True
                    except Exception:
                        pass

            except Exception as err:
                print("  [{}/{}] {}: error ({})".format(draw_idx, total_calls, draw.name, err))
                continue

            try:
                constants = self.getShaderConstants(draw, state=state)
            except Exception:
                constants = {}

            topology = "TRIANGLE_STRIP" if state.GetPrimitiveTopology() == rd.Topology.TriangleStrip else "TRIANGLES"
            constants["DrawCall"] = {"topology": topology, "type": "Universal"}
            with open("{}{:05d}-constants.bin".format(FILEPREFIX, output_idx), "wb") as f:
                pickle.dump(constants, f)

            texture_files = self.extractAllTextures(output_idx, state)
            profiling_counters["processDrawEvent"].add_sample(timer)

            manifest["drawcalls"].append({
                "id": output_idx, "original_id": draw_idx, "name": draw.name,
                "eventId": draw.eventId, "topology": topology,
                "has_positions": True, "has_normals": has_normals,
                "has_uvs": has_uvs, "has_colors": has_colors,
                "num_indices": int(len(indices)), "num_textures": len(texture_files),
                "attributes": attr_info,
            })
            output_idx += 1

        manifest_path = "{}manifest.json".format(FILEPREFIX)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print("Done: {} drawcalls extracted from {} total".format(output_idx, total_calls))


def main(controller):
    UniversalCaptureScraper(controller).run()


if __name__ == "__main__":
    if "pyrenderdoc" in globals():
        pyrenderdoc.Replay().BlockInvoke(main)
    else:
        print("Loading capture: {}".format(CAPTURE_FILE))
        with CaptureWrapper(CAPTURE_FILE) as controller:
            main(controller)
