# Unreal editor script (run headless via Tools/import_fx.sh): builds the game's own runtime assets that are not
# Blender art: FX materials (/Game/IceRiot/FX), HUD fonts (/Game/IceRiot/UI) and the empty arena map if missing.
# print() is invisible in the commandlet, so everything goes to Saved/ue_fx_report.txt.
import os
import unreal

PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
REPORT = os.path.join(PROJECT, "Saved", "ue_fx_report.txt")
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
_rep = open(REPORT, "w")


def log(*a):
    _rep.write(" ".join(str(x) for x in a) + "\n")
    _rep.flush()


AT = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary
P = unreal.MaterialProperty
D_FX = "/Game/IceRiot/FX"
D_UI = "/Game/IceRiot/UI"


def X(mat, cls, x, y, **props):
    e = MEL.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def new_material(name):
    path = "%s/%s" % (D_FX, name)
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    return AT.create_asset(name, D_FX, unreal.Material, unreal.MaterialFactoryNew())


def custom(mat, code, inputs, x, y, out_type=unreal.CustomMaterialOutputType.CMOT_FLOAT4):
    c = X(mat, unreal.MaterialExpressionCustom, x, y)
    c.set_editor_property("code", code)
    c.set_editor_property("output_type", out_type)
    ins = []
    for n, _ in inputs:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        ins.append(ci)
    c.set_editor_property("inputs", ins)
    for i, (n, (expr, outname)) in enumerate(inputs):
        MEL.connect_material_expressions(expr, outname, c, n)
    return c


def mask(mat, src, x, y, r=True, g=False, b=False, a=False):
    m = X(mat, unreal.MaterialExpressionComponentMask, x, y, r=r, g=g, b=b, a=a)
    MEL.connect_material_expressions(src, "", m, "")
    return m


def finish(mat):
    MEL.layout_material_expressions(mat)
    MEL.recompile_material(mat)
    EAL.save_loaded_asset(mat)
    log("MATERIAL", mat.get_name())


def setup(mat, blend, two_sided=True, ism=True):
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("blend_mode", blend)
    mat.set_editor_property("two_sided", two_sided)
    if ism:
        mat.set_editor_property("used_with_instanced_static_meshes", True)


def custom_data(mat):
    cds = [X(mat, unreal.MaterialExpressionPerInstanceCustomData, -1200, 200 + i * 110, data_index=i) for i in range(4)]
    return cds


# --------------------------------------------------------------------------------------------- particles

def build_additive():
    m = new_material("M_FX_Additive")
    setup(m, unreal.BlendMode.BLEND_ADDITIVE)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    cd = custom_data(m)
    code = ("float2 d = UV - 0.5; float r = saturate(length(d) * 2.0);"
            "float core = pow(saturate(1.0 - r), 2.2) + 0.6 * pow(saturate(1.0 - r), 8.0);"
            "return float4(float3(R, G, B) * core * A * 3.0, 1);")
    c = custom(m, code, [("UV", (tc, "")), ("R", (cd[0], "")), ("G", (cd[1], "")), ("B", (cd[2], "")), ("A", (cd[3], ""))], -800, 200)
    MEL.connect_material_property(mask(m, c, -500, 200, True, True, True), "", P.MP_EMISSIVE_COLOR)
    finish(m)


def build_translucent():
    m = new_material("M_FX_Translucent")
    setup(m, unreal.BlendMode.BLEND_TRANSLUCENT)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    cd = custom_data(m)
    code = ("float2 d = UV - 0.5; float r = saturate(length(d) * 2.0);"
            "float n = 0.75 + 0.25 * sin(UV.x * 23.0 + UV.y * 17.0);"
            "float a = pow(saturate(1.0 - r), 1.6) * n * A;"
            "return float4(float3(R, G, B) * 1.6, a);")
    c = custom(m, code, [("UV", (tc, "")), ("R", (cd[0], "")), ("G", (cd[1], "")), ("B", (cd[2], "")), ("A", (cd[3], ""))], -800, 200)
    MEL.connect_material_property(mask(m, c, -500, 150, True, True, True), "", P.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(mask(m, c, -500, 300, False, False, False, True), "", P.MP_OPACITY)
    finish(m)


def build_opaque():
    m = new_material("M_FX_Opaque")
    m.set_editor_property("used_with_instanced_static_meshes", True)
    cd = custom_data(m)
    a = X(m, unreal.MaterialExpressionAppendVector, -900, 200)
    MEL.connect_material_expressions(cd[0], "", a, "A")
    MEL.connect_material_expressions(cd[1], "", a, "B")
    b = X(m, unreal.MaterialExpressionAppendVector, -700, 250)
    MEL.connect_material_expressions(a, "", b, "A")
    MEL.connect_material_expressions(cd[2], "", b, "B")
    MEL.connect_material_property(b, "", P.MP_BASE_COLOR)
    finish(m)


# --------------------------------------------------------------------------------------------- player ring / shadow / glow

def build_ring():
    m = new_material("M_FX_Ring")
    setup(m, unreal.BlendMode.BLEND_TRANSLUCENT, ism=False)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1200, 0)
    col = X(m, unreal.MaterialExpressionVectorParameter, -1200, 150, parameter_name="Color", default_value=unreal.LinearColor(0.1, 0.5, 1, 1))
    alpha = X(m, unreal.MaterialExpressionScalarParameter, -1200, 300, parameter_name="Alpha", default_value=1.0)
    turbo = X(m, unreal.MaterialExpressionScalarParameter, -1200, 400, parameter_name="Turbo", default_value=1.0)
    pulse = X(m, unreal.MaterialExpressionScalarParameter, -1200, 500, parameter_name="Pulse", default_value=0.0)
    time = X(m, unreal.MaterialExpressionTime, -1200, 600)
    code = (
        "float2 d = UV - 0.5; float r = length(d) * 2.0;"
        "float aa = 0.02;"
        "float ring = smoothstep(0.66 - aa, 0.66, r) * (1.0 - smoothstep(0.80, 0.80 + aa, r));"
        # turbo arc: outer band, clockwise from the top, fills with the meter
        "float ang = frac(atan2(d.x, -d.y) / 6.2831853 + 1.0);"
        "float band = smoothstep(0.84 - aa, 0.84, r) * (1.0 - smoothstep(0.97, 0.97 + aa, r));"
        "float lit = step(ang, Turbo);"
        "float glow = (1.0 - smoothstep(0.0, 0.66, r)) * 0.10;"
        "float p = 1.0 + Pulse * 0.6 * sin(Time * 9.0);"
        "float3 c = Col.rgb * (ring * 2.2 * p + glow) + band * lit * lerp(Col.rgb, float3(1,1,1), 0.55) * 2.0 + band * (1.0 - lit) * 0.06;"
        "float a = saturate(ring * 0.95 + band * (lit * 0.9 + 0.22) + glow * 1.5) * Alpha;"
        "return float4(c, a);")
    c = custom(m, code, [("UV", (tc, "")), ("Col", (col, "")), ("Alpha", (alpha, "")), ("Turbo", (turbo, "")), ("Pulse", (pulse, "")), ("Time", (time, ""))], -700, 200)
    MEL.connect_material_property(mask(m, c, -400, 150, True, True, True), "", P.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(mask(m, c, -400, 300, False, False, False, True), "", P.MP_OPACITY)
    finish(m)


def build_shadow():
    m = new_material("M_FX_Shadow")
    setup(m, unreal.BlendMode.BLEND_TRANSLUCENT, ism=False)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1000, 0)
    code = "float r = saturate(length(UV - 0.5) * 2.0); return pow(1.0 - r, 2.0) * 0.42;"
    c = custom(m, code, [("UV", (tc, ""))], -700, 100, unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    blk = X(m, unreal.MaterialExpressionConstant3Vector, -700, -100, constant=unreal.LinearColor(0, 0, 0, 1))
    MEL.connect_material_property(blk, "", P.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(c, "", P.MP_OPACITY)
    finish(m)


def build_glow():
    m = new_material("M_FX_Glow")
    setup(m, unreal.BlendMode.BLEND_ADDITIVE, ism=False)
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1000, 0)
    col = X(m, unreal.MaterialExpressionVectorParameter, -1000, 150, parameter_name="Color", default_value=unreal.LinearColor(0.4, 0.8, 1, 1))
    alpha = X(m, unreal.MaterialExpressionScalarParameter, -1000, 300, parameter_name="Alpha", default_value=0.8)
    code = "float r = saturate(length(UV - 0.5) * 2.0); return Col.rgb * pow(1.0 - r, 2.5) * Alpha * 1.5;"
    c = custom(m, code, [("UV", (tc, "")), ("Col", (col, "")), ("Alpha", (alpha, ""))], -700, 100, unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    MEL.connect_material_property(c, "", P.MP_EMISSIVE_COLOR)
    finish(m)


# --------------------------------------------------------------------------------------------- fonts

def import_font(ttf, face_name, font_name):
    face_path = "%s/%s" % (D_UI, face_name)
    if not EAL.does_asset_exist(face_path):
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", ttf)
        t.set_editor_property("destination_path", D_UI)
        t.set_editor_property("destination_name", face_name)
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("save", True)
        AT.import_asset_tasks([t])
    face = unreal.load_asset(face_path)
    if not isinstance(face, unreal.FontFace):
        log("FONT FACE import produced", type(face).__name__ if face else None, "for", ttf)
        # the importer may create a UFont directly; find the face it made
        return None
    face.set_editor_property("loading_policy", unreal.FontLoadingPolicy.INLINE)
    EAL.save_loaded_asset(face)
    font_path = "%s/%s" % (D_UI, font_name)
    if EAL.does_asset_exist(font_path):
        EAL.delete_asset(font_path)
    font = AT.create_asset(font_name, D_UI, unreal.Font, unreal.FontFactory())
    font.set_editor_property("font_cache_type", unreal.FontCacheType.RUNTIME)
    comp = font.get_editor_property("composite_font")
    comp.import_text('(DefaultTypeface=(Fonts=((Name="Default",Font=(FontFaceAsset="%s.%s")))))' % (face_path, face_name))
    font.set_editor_property("composite_font", comp)
    font.set_editor_property("legacy_font_size", 32)
    log("FONT composite", comp.export_text()[:300])
    EAL.save_loaded_asset(font)
    log("FONT", font_name, "<-", os.path.basename(ttf))
    return font


# --------------------------------------------------------------------------------------------- map

def ensure_map():
    path = "/Game/Maps/Arena"
    if EAL.does_asset_exist(path):
        log("MAP exists", path)
        return
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    les.new_level(path)
    les.save_current_level()
    log("MAP created", path)


STEPS = [s for s in os.environ.get("IR_FX_STEPS", "materials,fonts,map").split(",") if s]
try:
    if "materials" in STEPS:
        for fn in (build_additive, build_translucent, build_opaque, build_ring, build_shadow, build_glow):
            try:
                fn()
            except Exception as e:  # keep going, report
                log("ERROR", fn.__name__, e)
    if "fonts" in STEPS:
        fonts = os.path.join(PROJECT, "Art", "Fonts")
        import_font(os.path.join(fonts, "Anton-Regular.ttf"), "FF_Anton", "F_Display")
        import_font(os.path.join(fonts, "BarlowSemiCondensed-SemiBold.ttf"), "FF_Barlow", "F_Body")
    if "map" in STEPS:
        ensure_map()
except Exception as e:
    log("FATAL", e)
log("DONE")
_rep.close()
