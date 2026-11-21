"""ICE RIOT - Unreal import pipeline.

Imports everything the Blender generators wrote to Art/Export into /Game/IceRiot, builds the master
materials (M_IR_*) + material instances (MI_*) from Art/Export/Materials/*.json, imports the shared
skeleton (SK_Skater_Skeleton), skeletal meshes, animations, static meshes and textures, and creates the
empty /Game/Maps/Arena map.

Run headless (see Tools/import_assets.sh):
  UnrealEditor-Cmd IceRiot.uproject -run=pythonscript -script=Tools/ue_import.py -unattended -nosplash \
      -AllowCommandletRendering
Steps (env IR_STEPS, comma list): textures,materials,static,skeletal,anims,map,verify
IR_REBUILD_MASTERS=ALL (or names) deletes + rebuilds the master material graphs.
print() is invisible in the commandlet: everything goes to Saved/ue_import_report.txt.
"""

import glob
import json
import os
import traceback

import unreal

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
ART = os.path.join(PROJECT, "Art", "Export")
REPORT = os.path.join(PROJECT, "Saved", "ue_import_report.txt")
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
_rep = open(REPORT, "w")


def log(*a):
    _rep.write(" ".join(str(x) for x in a) + "\n")
    _rep.flush()


unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
AT = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary

BASE = "/Game/IceRiot"
D_MESH = BASE + "/Meshes"
D_ANIM = BASE + "/Anims"
D_MAT = BASE + "/Materials"
D_TEX = BASE + "/Textures"
SKELETON = D_MESH + "/SK_Skater_Skeleton"

STEPS = [s.strip() for s in os.environ.get("IR_STEPS", "textures,materials,static,skeletal,anims,map,verify").split(",")
         if s.strip()]
REBUILD = set(x.strip() for x in os.environ.get("IR_REBUILD_MASTERS", "").split(",") if x.strip())
COUNTS = {}


def bump(k):
    COUNTS[k] = COUNTS.get(k, 0) + 1


def asset_path(folder, name):
    return "%s/%s.%s" % (folder, name, name)


def load(folder, name):
    p = asset_path(folder, name)
    return unreal.load_asset(p) if EAL.does_asset_exist(p) else None


def import_file(filename, dest, options=None, name=None):
    t = unreal.AssetImportTask()
    t.filename = filename
    t.destination_path = dest
    t.automated = True
    t.save = True
    t.replace_existing = True
    if name:
        t.destination_name = name
    if options is not None:
        t.options = options
    AT.import_asset_tasks([t])
    paths = list(t.imported_object_paths)
    if not paths:
        log("IMPORT FAILED", filename)
        bump("failed")
    return paths


# ---------------------------------------------------------------------------
# Textures
# ---------------------------------------------------------------------------
LINEAR_TEX = ("T_Digits",)          # data textures: masks in channels


def import_textures():
    for f in sorted(glob.glob(os.path.join(ART, "Textures", "*.png"))):
        name = os.path.splitext(os.path.basename(f))[0]
        import_file(f, D_TEX, name=name)
        tex = load(D_TEX, name)
        if not tex:
            continue
        if name in LINEAR_TEX:
            tex.set_editor_property("srgb", False)
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP)
        if name.startswith(("T_Logo", "T_LogoIceRiot")):
            tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_UI)
        EAL.save_loaded_asset(tex)
        bump("textures")
        log("TEX", name, tex.blueprint_get_size_x(), tex.blueprint_get_size_y())


# ---------------------------------------------------------------------------
# Master materials
# ---------------------------------------------------------------------------
MASTER_BUILDERS = []
P = unreal.MaterialProperty


def master(key, name):
    def deco(fn):
        MASTER_BUILDERS.append((key, name, fn))
        return fn
    return deco


def X(mat, cls, x, y, **props):
    e = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def vparam(mat, name, default, x, y, group="Params"):
    return X(mat, unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name,
             default_value=unreal.LinearColor(*default), group=group)


def sparam(mat, name, default, x, y, group="Params"):
    return X(mat, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=default,
             group=group)


def tparam(mat, name, tex, x, y, uvs=None, linear=False):
    e = X(mat, unreal.MaterialExpressionTextureSampleParameter2D, x, y, parameter_name=name, texture=tex)
    if linear:
        e.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    if uvs is not None:
        MEL.connect_material_expressions(uvs, "", e, "UVs")
    return e


def link(a, ao, b, bi):
    MEL.connect_material_expressions(a, ao, b, bi)


def op(mat, cls, a, b, x, y, ao="", bo=""):
    e = X(mat, cls, x, y)
    link(a, ao, e, "A")
    link(b, bo, e, "B")
    return e


def mul(mat, a, b, x, y, ao="", bo=""):
    return op(mat, unreal.MaterialExpressionMultiply, a, b, x, y, ao, bo)


def add(mat, a, b, x, y, ao="", bo=""):
    return op(mat, unreal.MaterialExpressionAdd, a, b, x, y, ao, bo)


def lerp(mat, a, b, alpha, x, y, ao="", bo="", co=""):
    e = X(mat, unreal.MaterialExpressionLinearInterpolate, x, y)
    link(a, ao, e, "A")
    link(b, bo, e, "B")
    link(alpha, co, e, "Alpha")
    return e


def const(mat, v, x, y):
    return X(mat, unreal.MaterialExpressionConstant, x, y, r=v)


def out(e, prop, o=""):
    MEL.connect_material_property(e, o, prop)


def white_tex():
    return unreal.load_asset("/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture")


def tex_or_white(name):
    return load(D_TEX, name) or white_tex()


def usage(m, skel=True):
    for prop in ("used_with_skeletal_mesh", "used_with_instanced_static_meshes", "used_with_morph_targets"):
        try:
            if prop == "used_with_skeletal_mesh" and not skel:
                continue
            m.set_editor_property(prop, True)
        except Exception:
            pass


def uv_tiled(m, x, y):
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, x - 400, y)
    til = vparam(m, "Tiling", (1, 1, 0, 0), x - 400, y + 120)
    msk = X(m, unreal.MaterialExpressionComponentMask, x - 200, y + 120, r=True, g=True, b=False, a=False)
    link(til, "", msk, "")
    return mul(m, tc, msk, x, y)


@master("opaque", "M_IR_Opaque")
def _m_opaque(m):
    usage(m)
    tex = tparam(m, "BaseTexture", white_tex(), -600, 0, uv_tiled(m, -800, 0))
    col = vparam(m, "BaseColor", (1, 1, 1, 1), -600, 300)
    out(mul(m, tex, col, -300, 0, "RGB", ""), P.MP_BASE_COLOR)
    out(sparam(m, "Roughness", 0.5, -300, 200), P.MP_ROUGHNESS)
    out(sparam(m, "Metallic", 0.0, -300, 300), P.MP_METALLIC)
    out(sparam(m, "Specular", 0.5, -300, 400), P.MP_SPECULAR)
    ec = vparam(m, "EmissiveColor", (0, 0, 0, 1), -600, 500)
    es = sparam(m, "EmissiveStrength", 0.0, -600, 650)
    out(mul(m, ec, es, -300, 550), P.MP_EMISSIVE_COLOR)


@master("masked", "M_IR_Masked")
def _m_masked(m):
    usage(m)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property("two_sided", True)
    tex = tparam(m, "BaseTexture", white_tex(), -700, 0, uv_tiled(m, -900, 0))
    col = vparam(m, "BaseColor", (1, 1, 1, 1), -700, 300)
    out(mul(m, tex, col, -300, 0, "RGB", ""), P.MP_BASE_COLOR)
    out(tex, P.MP_OPACITY_MASK, "A")
    out(sparam(m, "Roughness", 0.6, -300, 200), P.MP_ROUGHNESS)


@master("vertexcolor", "M_IR_VertexColor")
def _m_vertexcolor(m):
    usage(m)
    vc = X(m, unreal.MaterialExpressionVertexColor, -700, 0)
    col = vparam(m, "BaseColor", (1, 1, 1, 1), -700, 200)
    out(mul(m, vc, col, -300, 0), P.MP_BASE_COLOR)
    out(sparam(m, "Roughness", 0.7, -300, 200), P.MP_ROUGHNESS)
    out(sparam(m, "Metallic", 0.0, -300, 300), P.MP_METALLIC)


@master("glass", "M_IR_Glass")
def _m_glass(m):
    usage(m)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", True)
    try:
        m.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
    except Exception as ex:
        log("glass lighting mode", ex)
    out(vparam(m, "BaseColor", (0.85, 0.93, 1.0, 1), -500, 0), P.MP_BASE_COLOR)
    fr = X(m, unreal.MaterialExpressionFresnel, -700, 200, exponent=4.0, base_reflect_fraction=0.0)
    opv = sparam(m, "Opacity", 0.2, -700, 350)
    out(add(m, opv, mul(m, fr, const(m, 0.35, -700, 450), -500, 250), -300, 250), P.MP_OPACITY)
    out(sparam(m, "Roughness", 0.05, -500, 450), P.MP_ROUGHNESS)
    out(const(m, 1.0, -500, 550), P.MP_SPECULAR)


@master("emissive", "M_IR_Emissive")
def _m_emissive(m):
    usage(m)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    tm = X(m, unreal.MaterialExpressionTime, -1300, 150)
    pu = sparam(m, "PanU", 0.0, -1300, 250)
    pv = sparam(m, "PanV", 0.0, -1300, 350)
    ap = X(m, unreal.MaterialExpressionAppendVector, -1100, 300)
    link(pu, "", ap, "A")
    link(pv, "", ap, "B")
    uv = add(m, uv_tiled(m, -1100, 0), mul(m, tm, ap, -950, 200), -800, 50)
    tex = tparam(m, "BaseTexture", white_tex(), -600, 0, uv)
    col = vparam(m, "BaseColor", (1, 1, 1, 1), -600, 300)
    st = sparam(m, "EmissiveStrength", 1.0, -600, 450)
    out(mul(m, mul(m, tex, col, -350, 0, "RGB", ""), st, -150, 100), P.MP_EMISSIVE_COLOR)


@master("screen", "M_IR_Screen")
def _m_screen(m):
    usage(m, skel=False)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -900, 0)
    tex = tparam(m, "Screen", tex_or_white("T_JumboDefault"), -600, 0, tc)
    br = sparam(m, "Brightness", 1.5, -600, 300)
    out(mul(m, tex, br, -300, 0, "RGB", ""), P.MP_EMISSIVE_COLOR)


@master("goallight", "M_IR_GoalLight")
def _m_goallight(m):
    usage(m, skel=False)
    col = vparam(m, "Color", (1.0, 0.05, 0.02, 1), -700, 0)
    out(col, P.MP_BASE_COLOR)
    out(sparam(m, "Roughness", 0.2, -300, 150), P.MP_ROUGHNESS)
    on = sparam(m, "On", 0.0, -900, 300)
    st = sparam(m, "EmissiveStrength", 60.0, -900, 400)
    idle = sparam(m, "IdleGlow", 0.15, -900, 500)
    k = add(m, mul(m, on, st, -700, 350), idle, -500, 400)
    out(mul(m, col, k, -300, 300), P.MP_EMISSIVE_COLOR)


def rim_and_flash(m, x, y):
    fr = X(m, unreal.MaterialExpressionFresnel, x, y, exponent=3.0, base_reflect_fraction=0.0)
    rc = vparam(m, "RimColor", (1.0, 0.45, 0.08, 1), x, y + 150)
    rs = sparam(m, "RimStrength", 0.0, x, y + 300)
    fc = vparam(m, "FlashColor", (1, 1, 1, 1), x, y + 450)
    fs = sparam(m, "FlashStrength", 0.0, x, y + 600)
    rim = mul(m, mul(m, fr, rc, x + 250, y + 50), rs, x + 450, y + 100)
    flash = mul(m, fc, fs, x + 250, y + 500)
    return add(m, rim, flash, x + 650, y + 250)


@master("team", "M_IR_Team")
def _m_team(m):
    usage(m)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1100, 0)
    tex = tparam(m, "Texture", white_tex(), -900, 0, tc)
    col = vparam(m, "Color", (0.8, 0.8, 0.8, 1), -900, 300)
    out(mul(m, tex, col, -500, 0, "RGB", ""), P.MP_BASE_COLOR)
    out(sparam(m, "Roughness", 0.6, -500, 200), P.MP_ROUGHNESS)
    out(sparam(m, "Metallic", 0.0, -500, 300), P.MP_METALLIC)
    out(rim_and_flash(m, -1300, 500), P.MP_EMISSIVE_COLOR)


@master("skin", "M_IR_Skin")
def _m_skin(m):
    usage(m)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1100, 0)
    tex = tparam(m, "Texture", tex_or_white("T_Face"), -900, 0, tc)
    sk = vparam(m, "SkinColor", (0.69, 0.40, 0.26, 1), -900, 300)
    amt = sparam(m, "FaceAmount", 1.0, -900, 450)
    alpha = mul(m, tex, amt, -650, 200, "A", "")
    out(lerp(m, sk, tex, alpha, -400, 0, "", "RGB", ""), P.MP_BASE_COLOR)
    out(sparam(m, "Roughness", 0.55, -400, 250), P.MP_ROUGHNESS)
    out(sparam(m, "Specular", 0.4, -400, 350), P.MP_SPECULAR)
    out(rim_and_flash(m, -1300, 600), P.MP_EMISSIVE_COLOR)


NUMBER_HLSL = """
float d = Ones;
float lu = (UV.x - 0.25) * 2.0;
if (Tens >= 0.0) {
    if (UV.x < 0.5) { d = Tens; lu = UV.x * 2.0; }
    else { lu = (UV.x - 0.5) * 2.0; }
}
float valid = (lu >= 0.0 && lu <= 1.0) ? 1.0 : 0.0;
return float3((floor(d + 0.5) + saturate(lu)) / 10.0, UV.y, valid);
"""


@master("number", "M_IR_Number")
def _m_number(m):
    usage(m)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1500, 0)
    tens = sparam(m, "Tens", 1.0, -1500, 150)
    ones = sparam(m, "Ones", 7.0, -1500, 250)
    cu = X(m, unreal.MaterialExpressionCustom, -1200, 100)
    cu.set_editor_property("code", NUMBER_HLSL)
    cu.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    cu.set_editor_property("description", "JerseyDigits")
    ins = []
    for nm in ("UV", "Tens", "Ones"):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", nm)
        ins.append(ci)
    cu.set_editor_property("inputs", ins)
    link(tc, "", cu, "UV")
    link(tens, "", cu, "Tens")
    link(ones, "", cu, "Ones")
    uvm = X(m, unreal.MaterialExpressionComponentMask, -950, 50, r=True, g=True, b=False, a=False)
    link(cu, "", uvm, "")
    vm = X(m, unreal.MaterialExpressionComponentMask, -950, 250, r=False, g=False, b=True, a=False)
    link(cu, "", vm, "")
    tex = tparam(m, "Digits", tex_or_white("T_Digits"), -750, 0, uvm, linear=True)
    col = vparam(m, "Color", (1, 1, 1, 1), -750, 300)
    ocol = vparam(m, "OutlineColor", (0.02, 0.05, 0.12, 1), -750, 450)
    out(lerp(m, ocol, col, tex, -400, 100, "", "", "R"), P.MP_BASE_COLOR)
    out(mul(m, tex, vm, -400, 300, "G", ""), P.MP_OPACITY_MASK)
    out(sparam(m, "Roughness", 0.6, -400, 450), P.MP_ROUGHNESS)


@master("ice", "M_IR_Ice")
def _m_ice(m):
    usage(m, skel=False)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1300, 0)
    mk = tparam(m, "Markings", tex_or_white("T_IceMarkings"), -1000, 0, tc)
    tint = vparam(m, "Tint", (0.93, 0.97, 1.0, 1), -1000, 250)
    wear = sparam(m, "Wear", 0.0, -1300, 600)
    # scratches: tiled detail texture, stronger with Wear
    tcs = X(m, unreal.MaterialExpressionTextureCoordinate, -1300, 400, u_tiling=24.0, v_tiling=11.0)
    sc = tparam(m, "Scratches", tex_or_white("T_IceScratches"), -1000, 400, tcs)
    sv = mul(m, sc, add(m, const(m, 0.35, -900, 700), wear, -750, 650), -650, 450, "R", "")
    snow = vparam(m, "SnowColor", (0.85, 0.88, 0.92, 1), -700, 800)
    base = mul(m, mk, tint, -700, 0, "RGB", "")
    out(lerp(m, base, snow, mul(m, sv, const(m, 0.5, -650, 950), -450, 600), -300, 0), P.MP_BASE_COLOR)
    rmin = sparam(m, "RoughnessMin", 0.06, -700, 1000)
    rmax = sparam(m, "RoughnessMax", 0.30, -700, 1100)
    out(lerp(m, rmin, rmax, sv, -300, 900), P.MP_ROUGHNESS)
    out(sparam(m, "Specular", 0.6, -300, 1100), P.MP_SPECULAR)


@master("crowd", "M_IR_Crowd")
def _m_crowd(m):
    usage(m, skel=False)
    vc = X(m, unreal.MaterialExpressionVertexColor, -600, -200)
    out(vc, P.MP_BASE_COLOR)
    out(const(m, 0.85, -300, -50), P.MP_ROUGHNESS)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1600, 200)
    ph = X(m, unreal.MaterialExpressionComponentMask, -1400, 150, r=True, g=False, b=False, a=False)
    link(tc, "", ph, "")
    amv = X(m, unreal.MaterialExpressionComponentMask, -1500, 300, r=False, g=True, b=False, a=False)
    link(tc, "", amv, "")
    am = X(m, unreal.MaterialExpressionOneMinus, -1400, 300)   # FBX import flips V
    link(amv, "", am, "")
    ex = sparam(m, "Excitement", 0.0, -1600, 450)
    tm = X(m, unreal.MaterialExpressionTime, -1600, 50)
    freq = add(m, mul(m, ex, const(m, 1.6, -1500, 600), -1350, 500), const(m, 0.9, -1350, 650), -1200, 550)
    arg = add(m, mul(m, tm, freq, -1100, 100), ph, -950, 150)
    sn = X(m, unreal.MaterialExpressionSine, -800, 150, period=1.0)
    link(arg, "", sn, "")
    ab = X(m, unreal.MaterialExpressionAbs, -650, 150)
    link(sn, "", ab, "")
    height = mul(m, mul(m, ab, am, -500, 200),
                 add(m, const(m, 2.5, -650, 400), mul(m, ex, const(m, 22.0, -800, 500), -650, 500), -500, 400),
                 -350, 250)
    up = X(m, unreal.MaterialExpressionConstant3Vector, -350, 450, constant=unreal.LinearColor(0, 0, 1, 1))
    out(mul(m, up, height, -150, 300), P.MP_WORLD_POSITION_OFFSET)


def build_masters():
    masters = {}
    for key, name, fn in MASTER_BUILDERS:
        existing = load(D_MAT, name)
        if existing is not None and name not in REBUILD and "ALL" not in REBUILD:
            masters[key] = existing
            continue
        if existing is not None:
            EAL.delete_asset(asset_path(D_MAT, name))
        m = AT.create_asset(name, D_MAT, unreal.Material, unreal.MaterialFactoryNew())
        try:
            fn(m)
        except Exception:
            log("MASTER BUILD ERROR", name, traceback.format_exc())
        MEL.layout_material_expressions(m)
        MEL.recompile_material(m)
        EAL.save_loaded_asset(m)
        log("MASTER", name)
        bump("masters")
        masters[key] = m
    return masters


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------
def lc(c, a=1.0):
    c = list(c) + [a] * (4 - len(c))
    return unreal.LinearColor(c[0], c[1], c[2], c[3])


def setv(mi, n, v):
    MEL.set_material_instance_vector_parameter_value(mi, n, v)


def sets(mi, n, v):
    MEL.set_material_instance_scalar_parameter_value(mi, n, float(v))


def sett(mi, n, tname):
    tex = load(D_TEX, tname)
    if tex:
        MEL.set_material_instance_texture_parameter_value(mi, n, tex)
    else:
        log("MISSING TEXTURE", tname, "for", mi.get_name())


def build_instances(masters):
    defs = {}
    for f in sorted(glob.glob(os.path.join(ART, "Materials", "*.json"))):
        with open(f) as fp:
            d = json.load(fp)
        for k in d:
            if k in defs:
                log("DUPLICATE MATERIAL NAME", k, "in", os.path.basename(f))
        defs.update(d)
    for name, d in sorted(defs.items()):
        shader = d.get("shader", "opaque")
        parent = masters.get(shader)
        if parent is None:
            log("UNKNOWN SHADER", shader, "for", name)
            parent = masters["opaque"]
        mi = load(D_MAT, name) or AT.create_asset(name, D_MAT, unreal.MaterialInstanceConstant,
                                                    unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, parent)
        col = d.get("color", [1, 1, 1])
        tex = d.get("texture")
        if shader == "glass":
            setv(mi, "BaseColor", lc(col))
            sets(mi, "Opacity", d.get("opacity", 0.2))
            sets(mi, "Roughness", d.get("roughness", 0.05))
        elif shader == "emissive":
            setv(mi, "BaseColor", lc(col))
            sets(mi, "EmissiveStrength", d.get("emissive_strength", 1.0))
            sets(mi, "PanU", d.get("pan_u", 0.0))
            sets(mi, "PanV", d.get("pan_v", 0.0))
            if tex:
                sett(mi, "BaseTexture", tex)
            til = d.get("tiling")
            if til:
                setv(mi, "Tiling", unreal.LinearColor(til[0], til[1], 0, 0))
        elif shader == "team":
            setv(mi, "Color", lc(col))
            sets(mi, "Roughness", d.get("roughness", 0.6))
            sets(mi, "Metallic", d.get("metallic", 0.0))
            if tex:
                sett(mi, "Texture", tex)
        elif shader == "skin":
            setv(mi, "SkinColor", lc(d.get("skin_color", [0.69, 0.4, 0.26])))
            sets(mi, "FaceAmount", d.get("face_amount", 1.0))
            sets(mi, "Roughness", d.get("roughness", 0.55))
            if tex:
                sett(mi, "Texture", tex)
        elif shader == "number":
            setv(mi, "Color", lc(col))
            setv(mi, "OutlineColor", lc(d.get("outline_color", [0.02, 0.05, 0.12])))
            sets(mi, "Tens", d.get("tens", 1))
            sets(mi, "Ones", d.get("ones", 7))
            sett(mi, "Digits", tex or "T_Digits")
        elif shader == "ice":
            if tex:
                sett(mi, "Markings", tex)
            sets(mi, "Wear", d.get("wear", 0.0))
            sets(mi, "RoughnessMin", d.get("roughness", 0.07))
        elif shader == "screen":
            if tex:
                sett(mi, "Screen", tex)
            sets(mi, "Brightness", d.get("brightness", 1.5))
        elif shader == "goallight":
            setv(mi, "Color", lc(col))
            sets(mi, "EmissiveStrength", d.get("emissive_strength", 60.0))
            sets(mi, "On", d.get("on", 0.0))
        elif shader == "crowd":
            sets(mi, "Excitement", d.get("excitement", 0.0))
        else:   # opaque / masked / vertexcolor
            setv(mi, "BaseColor", lc(col))
            sets(mi, "Roughness", d.get("roughness", 0.5))
            if shader in ("opaque", "vertexcolor"):
                sets(mi, "Metallic", d.get("metallic", 0.0))
            if shader == "opaque":
                sets(mi, "Specular", d.get("specular", 0.5))
                if d.get("emissive") is not None:
                    setv(mi, "EmissiveColor", lc(d["emissive"]))
                    sets(mi, "EmissiveStrength", d.get("emissive_strength", 1.0))
            if tex and shader in ("opaque", "masked"):
                sett(mi, "BaseTexture", tex)
            til = d.get("tiling")
            if til and shader in ("opaque", "masked"):
                setv(mi, "Tiling", unreal.LinearColor(til[0], til[1], 0, 0))
        MEL.update_material_instance(mi)
        EAL.save_loaded_asset(mi)
        bump("instances")
    log("INSTANCES", len(defs))


def mat_for_slot(slot_name):
    mi = load(D_MAT, str(slot_name))
    if mi is None:
        log("NO MATERIAL FOR SLOT", slot_name)
        bump("missing_slot_material")
    return mi


# ---------------------------------------------------------------------------
# Meshes
# ---------------------------------------------------------------------------
def static_options():
    o = unreal.FbxImportUI()
    o.import_mesh = True
    o.import_as_skeletal = False
    o.import_materials = False
    o.import_textures = False
    o.import_animations = False
    o.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    d = o.static_mesh_import_data
    d.set_editor_property("combine_meshes", True)
    d.set_editor_property("auto_generate_collision", False)
    d.set_editor_property("generate_lightmap_u_vs", False)
    d.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    d.set_editor_property("remove_degenerates", True)
    d.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
    return o


def import_static():
    for f in sorted(glob.glob(os.path.join(ART, "Meshes", "SM_*.fbx"))):
        name = os.path.splitext(os.path.basename(f))[0]
        import_file(f, D_MESH, static_options(), name=name)
        sm = load(D_MESH, name)
        if not sm:
            continue
        mats = sm.get_editor_property("static_materials")
        for i, sm_mat in enumerate(mats):
            mi = mat_for_slot(sm_mat.get_editor_property("material_slot_name"))
            if mi:
                sm.set_material(i, mi)
        if name in PROP_COLLISION:
            add_collision(sm, PROP_COLLISION[name])
        EAL.save_loaded_asset(sm)
        bump("static")
        b = sm.get_bounds()
        log("STATIC", name, "tris", sm.get_num_triangles(0) if hasattr(sm, "get_num_triangles") else "?",
            "slots", [str(x.get_editor_property("material_slot_name")) for x in mats],
            "origin", fmt(b.origin), "extent", fmt(b.box_extent))


PROP_COLLISION = {"SM_Puck": "box", "SM_Helmet": "sphere", "SM_Glove": "box", "SM_Stick": "box", "SM_Hat1": "box",
                  "SM_Hat2": "box", "SM_Hat3": "box"}


def add_collision(sm, kind):
    shape = {"box": unreal.ScriptCollisionShapeType.BOX, "sphere": unreal.ScriptCollisionShapeType.SPHERE}[kind]
    try:
        sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        sub.remove_collisions(sm)
        sub.add_simple_collisions(sm, shape)
    except Exception as ex:
        try:
            unreal.EditorStaticMeshLibrary.add_simple_collisions(sm, shape)
        except Exception as ex2:
            log("collision failed", sm.get_name(), ex, ex2)


def fmt(v):
    return "(%.1f, %.1f, %.1f)" % (v.x, v.y, v.z)


def skeletal_options(skeleton=None):
    o = unreal.FbxImportUI()
    o.import_mesh = True
    o.import_as_skeletal = True
    o.import_materials = False
    o.import_textures = False
    o.import_animations = False
    o.create_physics_asset = False
    o.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    if skeleton:
        o.skeleton = skeleton
    d = o.skeletal_mesh_import_data
    d.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    d.set_editor_property("import_morph_targets", False)
    d.set_editor_property("update_skeleton_reference_pose", False)
    return o


def assign_skeletal_materials(skm):
    mats = skm.get_editor_property("materials")
    new = []
    for m in mats:
        mi = mat_for_slot(m.get_editor_property("material_slot_name"))
        if mi:
            m.set_editor_property("material_interface", mi)
        new.append(m)
    skm.set_editor_property("materials", new)
    return [str(m.get_editor_property("material_slot_name")) for m in new]


def import_skeletal():
    existing = load(D_MESH, "SK_Skater_Skeleton")
    import_file(os.path.join(ART, "Meshes", "SK_Skater.fbx"), D_MESH, skeletal_options(existing), name="SK_Skater")
    skm = load(D_MESH, "SK_Skater")
    if not skm:
        log("SK_Skater import failed")
        return
    skel = skm.get_editor_property("skeleton")
    slots = assign_skeletal_materials(skm)
    EAL.save_loaded_asset(skm)
    EAL.save_loaded_asset(skel)
    bump("skeletal")
    log("SKELETAL SK_Skater skeleton", skel.get_path_name(), "slots", slots)
    goalie = os.path.join(ART, "Meshes", "SK_Goalie.fbx")
    import_file(goalie, D_MESH, skeletal_options(skel), name="SK_Goalie")
    g = load(D_MESH, "SK_Goalie")
    if g:
        slots = assign_skeletal_materials(g)
        EAL.save_loaded_asset(g)
        bump("skeletal")
        log("SKELETAL SK_Goalie skeleton", g.get_editor_property("skeleton").get_path_name(), "slots", slots)


def import_anims():
    skel = load(D_MESH, "SK_Skater_Skeleton")
    if not skel:
        log("no skeleton for anims")
        return
    manifest = {}
    mp = os.path.join(ART, "Manifests", "anims.json")
    if os.path.exists(mp):
        with open(mp) as fp:
            manifest = json.load(fp)
    for f in sorted(glob.glob(os.path.join(ART, "Anims", "A_*.fbx"))):
        name = os.path.splitext(os.path.basename(f))[0]
        o = unreal.FbxImportUI()
        o.import_mesh = False
        o.import_as_skeletal = True
        o.import_animations = True
        o.import_materials = False
        o.import_textures = False
        o.skeleton = skel
        o.mesh_type_to_import = unreal.FBXImportType.FBXIT_ANIMATION
        ad = o.anim_sequence_import_data
        ad.set_editor_property("animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
        ad.set_editor_property("remove_redundant_keys", False)
        ad.set_editor_property("import_bone_tracks", True)
        import_file(f, D_ANIM, o, name=name)
        a = load(D_ANIM, name)
        if not a:
            continue
        a.set_editor_property("enable_root_motion", False)
        clip = manifest.get(name[2:], {})
        if clip.get("loop"):
            try:
                a.set_editor_property("loop", True)
            except Exception:
                pass
        EAL.save_loaded_asset(a)
        bump("anims")
        log("ANIM", name, "%.3f s" % a.get_play_length(), "loop" if clip.get("loop") else "",
            "events", clip.get("events", {}))


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------
def create_map():
    path = "/Game/Maps/Arena"
    if EAL.does_asset_exist(path + ".Arena"):
        log("MAP exists", path)
        return
    w = AT.create_asset("Arena", "/Game/Maps", unreal.World, unreal.WorldFactory())
    EAL.save_loaded_asset(w)
    log("MAP created", path)


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
REQUIRED_BONES = ["root", "pelvis", "spine_01", "spine_02", "spine_03", "neck", "head", "clavicle_l", "upperarm_l",
                  "lowerarm_l", "hand_l", "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r", "thigh_l", "calf_l",
                  "foot_l", "toe_l", "thigh_r", "calf_r", "foot_r", "toe_r", "stick", "stick_blade"]


def verify():
    skel = load(D_MESH, "SK_Skater_Skeleton")
    if not skel:
        log("VERIFY FAIL no skeleton at", SKELETON)
        return
    pose = unreal.AnimPoseExtensions.get_reference_pose(skel)
    names = [str(n) for n in unreal.AnimPoseExtensions.get_bone_names(pose)]
    missing = [b for b in REQUIRED_BONES if b not in names]
    log("VERIFY bones", len(names), "missing", missing, "all", names)
    for bn in ("root", "pelvis", "head", "hand_r", "stick", "stick_blade", "foot_l"):
        if bn not in names:
            continue
        tw = unreal.AnimPoseExtensions.get_bone_pose(pose, bn, unreal.AnimPoseSpaces.WORLD)
        r = tw.rotation
        log("BONE", bn, "pos", fmt(tw.translation), "X", fmt(r.rotate_vector(unreal.Vector(1, 0, 0))),
            "Y", fmt(r.rotate_vector(unreal.Vector(0, 1, 0))), "Z", fmt(r.rotate_vector(unreal.Vector(0, 0, 1))))
    for n in ("SK_Skater", "SK_Goalie"):
        m = load(D_MESH, n)
        if m:
            s = m.get_editor_property("skeleton")
            b = m.get_bounds()
            log("VERIFY", n, "skeleton", s.get_path_name() if s else None, "bounds origin", fmt(b.origin), "extent",
                fmt(b.box_extent))
    anims = [a for a in EAL.list_assets(D_ANIM, recursive=False, include_folder=False)]
    bad = []
    for p in anims:
        a = unreal.load_asset(p)
        if isinstance(a, unreal.AnimSequence):
            s = a.get_editor_property("skeleton")
            if not s or s.get_path_name() != skel.get_path_name():
                bad.append(p)
    log("VERIFY anims", len(anims), "wrong skeleton", bad)
    for key, name, fn in MASTER_BUILDERS:
        m = load(D_MAT, name)
        if not m:
            log("VERIFY MASTER missing", name)
            continue
        try:
            st = MEL.get_statistics(m)
            vs = st.get_editor_property("num_vertex_shader_instructions")
            ps = st.get_editor_property("num_pixel_shader_instructions")
            log("VERIFY MASTER", name, "vs", vs, "ps", ps, "OK" if ps > 0 else "NOT COMPILED")
        except Exception as ex:
            log("VERIFY MASTER", name, "stats unavailable", ex)
    log("COUNTS", COUNTS)


def main():
    log("STEPS", STEPS)
    masters = None
    for step in STEPS:
        try:
            if step == "textures":
                import_textures()
            elif step == "materials":
                masters = build_masters()
                build_instances(masters)
            elif step == "static":
                import_static()
            elif step == "skeletal":
                import_skeletal()
            elif step == "anims":
                import_anims()
            elif step == "map":
                create_map()
            elif step == "verify":
                verify()
        except Exception:
            log("STEP FAILED", step, traceback.format_exc())
            bump("step_failed")
    EAL.save_directory(BASE, only_if_is_dirty=True, recursive=True)
    log("IMPORT DONE")


main()
