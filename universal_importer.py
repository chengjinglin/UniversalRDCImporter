import sys, os, json, pickle, subprocess
import numpy as np
import bpy

from .profiling import Timer, profiling_counters
from .preferences import getPreferences
from .utils import getBinaryDir, makeTmpDir

UNIVERSAL_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "universal_rd.py")


class UniversalImportError(Exception):
    pass


def numpyLoad(file):
    (dim,) = np.fromfile(file, dtype=np.int32, count=1)
    shape = np.fromfile(file, dtype=np.int32, count=dim)
    dt = np.dtype(file.read(2).decode("ascii"))
    return np.fromfile(file, dtype=dt).reshape(shape)


def universalCaptureToFiles(context, filepath, prefix, max_blocks):
    pref = getPreferences(context)
    if bpy.app.version < (2, 91, 0):
        blender_dir = os.path.dirname(sys.executable)
        blender_version = "{0}.{1}".format(*bpy.app.version)
        python_home = os.path.join(blender_dir, blender_version, "python")
        python = os.path.join(python_home, "bin", "python.exe" if sys.platform == "win32" else "python3.7m")
    else:
        python = sys.executable
        python_home = os.path.dirname(os.path.dirname(sys.executable))

    os.environ["PYTHONHOME"] = python_home
    os.environ["PYTHONPATH"] = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] += os.pathsep + os.path.abspath(getBinaryDir())
    os.environ["PYTHONIOENCODING"] = "utf-8"

    if pref.debug_info:
        print("[RDC] 子进程: {} {}".format(python, UNIVERSAL_SCRIPT_PATH))

    try:
        out = subprocess.check_output(
            [python, UNIVERSAL_SCRIPT_PATH, filepath, prefix, str(max_blocks)],
            stderr=subprocess.STDOUT, text=True, timeout=600)
        if pref.debug_info:
            print(out)
    except subprocess.TimeoutExpired:
        raise UniversalImportError("超时（>10分钟），请减少最大绘制调用数")
    except subprocess.CalledProcessError as err:
        if pref.debug_info:
            print(err.output)
        if err.returncode == 20:
            raise UniversalImportError("未找到 RenderDoc Python 模块，请确认已安装 RenderDoc")
        elif err.returncode == 21:
            raise UniversalImportError("RenderDoc 模块加载失败（版本不匹配？）")
        else:
            raise UniversalImportError("提取失败 (代码 {})".format(err.returncode))
    except FileNotFoundError:
        raise UniversalImportError("找不到 Python: {}".format(python))


def loadManifest(prefix):
    path = "{}manifest.json".format(prefix)
    if not os.path.isfile(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def loadUniversalData(prefix, drawcall_id):
    data = {"indices": None, "positions": None, "normals": None, "uvs": None, "colors": None,
            "constants": None, "textures": []}

    for key, fname in [
        ("indices", "{}{:05d}-indices.bin"),
        ("positions", "{}{:05d}-positions.bin"),
        ("normals", "{}{:05d}-normals.bin"),
        ("uvs", "{}{:05d}-uv.bin"),
        ("colors", "{}{:05d}-colors.bin"),
    ]:
        path = fname.format(prefix, drawcall_id)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                data[key] = numpyLoad(f)

    con_path = "{}{:05d}-constants.bin".format(prefix, drawcall_id)
    if os.path.isfile(con_path):
        with open(con_path, "rb") as f:
            data["constants"] = pickle.load(f)

    tex_list = []
    tex_idx = 0
    while True:
        tex_path = "{}{:05d}-texture_{}.png".format(prefix, drawcall_id, tex_idx)
        if os.path.isfile(tex_path):
            try:
                tex_list.append(bpy.data.images.load(tex_path))
            except Exception:
                pass
            tex_idx += 1
        else:
            break
    tex_list.sort(key=lambda img: img.size[0] * img.size[1] if img and img.size[0] > 0 else 0, reverse=True)
    data["textures"] = tex_list
    return data


def addMesh(context, name, verts, tris, uvs=None, normals=None, colors=None):
    mesh = bpy.data.meshes.new(name)

    if verts.ndim == 1:
        verts = verts.reshape(-1, 3)
    if verts.shape[1] < 3:
        pad = np.zeros((verts.shape[0], 3 - verts.shape[1]), dtype=verts.dtype)
        verts = np.hstack([verts[:, :verts.shape[1]], pad])
    else:
        verts = verts[:, :3]

    mesh.from_pydata(verts.tolist(), [], tris)

    if uvs is not None and len(uvs) > 0:
        if uvs.ndim == 1:
            uvs = uvs.reshape(-1, 2)
        uv_list = uvs[:, :2].tolist()
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for loop in mesh.loops:
            vi = loop.vertex_index
            if vi < len(uv_list):
                uv_layer.data[loop.index].uv = tuple(uv_list[vi])

# 

    if normals is not None and len(normals) > 0 and len(normals) == len(verts):
        if normals.ndim == 1:
            normals = normals.reshape(-1, 3)
# 
        try:
            mesh.normals_split_custom_set_from_vertices(normals[:, :3].tolist())
        except Exception:
            pass

    obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(obj)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return obj


def addUniversalMaterial(name, obj, images):
    if not images:
        return None
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    obj.data.materials.append(mat)

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    principled = None
    for node in nodes:
        if node.type == "BSDF_PRINCIPLED":
            principled = node
            break
    if principled is None:
        principled = nodes.new(type="ShaderNodeBsdfPrincipled")
        principled.location = (0, 0)
        for node in nodes:
            if node.type == "OUTPUT_MATERIAL":
                links.new(principled.outputs[0], node.inputs[0])
                break

    principled.inputs["Roughness"].default_value = 1.0

    img = images[0]
    if img is not None:
        tex = nodes.new(type="ShaderNodeTexImage")
        tex.image = img
        links.new(tex.outputs[0], principled.inputs[0])

    return mat


def cleanupTempFiles(rdc_dir):
    import shutil
    cleaned = 0
    try:
        for item in os.listdir(rdc_dir):
            item_path = os.path.join(rdc_dir, item)
            if os.path.isdir(item_path) and os.path.isfile(os.path.join(item_path, "manifest.json")):
                shutil.rmtree(item_path, ignore_errors=True)
                cleaned += 1
    except Exception:
        pass
    return cleaned


def universalFilesToBlender(context, prefix, max_blocks=-1):
    manifest = loadManifest(prefix)
    log_dir = os.path.dirname(prefix)
    wm = context.window_manager

    if manifest is None:
        raise UniversalImportError("提取未生成清单\n目录: {}".format(log_dir))

    drawcalls = manifest.get("drawcalls", [])
    print("[RDC] 找到 {} 个可用绘制调用".format(len(drawcalls)))

    if not drawcalls:
        raise UniversalImportError(
            "未找到 3D 几何体 ({} 个事件)\n目录: {}".format(
                manifest.get("total_drawcalls", "?"), log_dir))

    if max_blocks <= 0:
        max_blocks = len(drawcalls)

    imported = 0
    total = min(max_blocks, len(drawcalls))
    wm.progress_begin(0, total)

    for i, dc in enumerate(drawcalls):
        if imported >= max_blocks:
            break
        wm.progress_update(i)
        dc_id = dc["id"]

        if not os.path.isfile("{}{:05d}-indices.bin".format(prefix, dc_id)):
            continue

        try:
            data = loadUniversalData(prefix, dc_id)
        except Exception:
            continue

        if data["indices"] is None or data["positions"] is None or len(data["positions"]) == 0:
            continue

        indices = data["indices"]
        topology = dc.get("topology", "TRIANGLES")
        n = len(indices)

        if topology == "TRIANGLE_STRIP":
            tris = [
                [int(indices[i + j]) for j in ([0, 1, 2] if i % 2 == 0 else [0, 2, 1])]
                for i in range(n - 2)
            ]
            tris = [t for t in tris if t[0] != t[1] and t[1] != t[2] and t[0] != t[2]]
        else:
            tris = [[int(indices[3 * i + j]) for j in range(3)] for i in range(n // 3)]

        if not tris:
            continue

        dc_name = dc.get("name", "Mesh_{:05d}".format(dc_id))
        safe_name = dc_name.replace("(", "_").replace(")", "").replace(" ", "_")

        obj = addMesh(context, safe_name, data["positions"], tris,
                      data["uvs"], data["normals"], data["colors"])

        images = data.get("textures", [])
        if images:
            addUniversalMaterial(safe_name + "_材质", obj, images)

        imported += 1

    wm.progress_end()
    print("[RDC] 成功导入 {} 个网格".format(imported))

    if imported == 0:
        raise UniversalImportError(
            "清单有 {} 个条目但均无法导入\n目录: {}".format(len(drawcalls), log_dir))

    return imported


def importUniversalCapture(context, filepath, max_blocks=-1):
    pref = getPreferences(context)
    prefix = makeTmpDir(pref, filepath)
    universalCaptureToFiles(context, filepath, prefix, max_blocks)
    return universalFilesToBlender(context, prefix, max_blocks)


