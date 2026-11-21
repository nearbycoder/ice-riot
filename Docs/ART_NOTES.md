# ICE RIOT — Art Notes (what exists, where, and what the C++ needs to know)

Status: **pass 2 complete and imported** (all spec assets exist in Unreal, all 12 master materials compile —
see `VERIFY MASTER` lines in the import report). Asset paths, names, slots, bones and parameter names below are
stable.

## Rebuild / import

```
Tools/build_art.sh [all|branding|rink|arena|props|chars|anims]   # Blender 5.3 headless -> Art/Export (~6 min all)
Tools/import_assets.sh                                           # UnrealEditor-Cmd + Tools/ue_import.py
IR_STEPS=anims Tools/import_assets.sh                            # subset: textures,materials,static,skeletal,anims,map,verify
IR_REBUILD_MASTERS=ALL Tools/import_assets.sh                    # rebuild master material graphs too
```
Report: `Saved/ue_import_report.txt` (every asset, bounds, slots, bone list + bone axes). Full log: `Saved/ue_import.log`.
Generators live in `Blender/` (`gen_branding.py`, `gen_rink.py`, `gen_arena.py`, `gen_props.py`, `gen_character.py`,
`gen_anims.py` + `anim_clips.py`/`anim_core.py`). `.blend` files are saved to `Art/Blend/`; previews to `Art/Previews/`.
The importer never deletes anything outside its own assets; `/Game/IceRiot/FX`, `/Game/IceRiot/UI`, `/Game/IceRiot/Audio`
and an existing `/Game/Maps/Arena` are left untouched.

## Axes (important)

* Blender (x, y, z) m → Unreal (100x, **−100y**, 100z) cm.
* The spec's "main camera on the Blender −Y side" is the **Unreal +Y side** of the rink, looking toward −Y.
  Screen-right = Unreal +X. Far boards / benches / penalty boxes / team banners are on **Unreal −Y**.
* **Characters face Unreal +Y** in the reference pose and in every animation → give the SkeletalMeshComponent a
  relative yaw of **−90°** so the mesh faces the actor's +X. Animations are in place, `root` stays at the origin.
* Static mesh pivots = Blender world origin (center ice, ice top z = 0) unless noted.

## Static meshes — `/Game/IceRiot/Meshes/`

| Asset | Tris | Notes |
|---|---|---|
| `SM_Ice` | 0.7k | rounded slab, top at z = 0, `MI_Ice` (UV 0..1 over x∈[−2300,2300], y∈[−1050,1050] cm) |
| `SM_Boards` | 11.6k | boards, yellow kick plate, navy rail, 46 sponsor panels (`MI_BoardAds`), dark outer face |
| `SM_Glass` | 1.1k | panes to z = 245 cm + stanchions; near side (Unreal +Y half) uses the extra-clear `MI_GlassNear` |
| `SM_Net` | 1.6k | **+X end net**: mouth on the goal line x = +1950 facing −X; `MI_GoalPost`, `MI_Netting` (masked), `MI_NetSkirt`. For the −X end spawn it with **yaw 180°** (or scale X −1) at the origin |
| `SM_GoalLight` | 0.6k | red dome on top of the glass behind the **+X** net (x ≈ 2306, z ≈ 245..280 cm); same mirroring as the net. `MI_GoalLight` scalar `On` (0/1) |
| `SM_Puck` | 0.8k | r 3.8 cm, h 2.54 cm, centered on its pivot; box collision |
| `SM_Arena` | 145k | bowl (17 lower rows, suites + LED ribbon, 13-row upper deck), aisles/stairs, open vomitory trenches (both ends + two near-side corners, lit exit signs), benches + penalty boxes + timekeeper (Unreal −Y side), roof girders, light truss with lamp fixtures, 8 team banners (Unreal −Y side, z ≈ 27..33 m) |
| `SM_Crowd` | 430k | ~8.2k fans, `MI_Crowd` (see crowd shader) |
| `SM_Jumbotron` | 0.3k | center-hung, main box bottom at z = 1600 cm; 4 main screens, each face UV 0..1 (`MI_JumboScreen`), bezels, LED ribbon ring, corner light strips; plus a small 4-sided underbelly screen ring (z ≈ 1440..1590 cm, same material, UV v cropped to 0.2..0.8 of the frame) |
| `SM_Helmet`, `SM_Glove`, `SM_Stick` | 1.2k / 0.6k / 0.6k | loose props, pivot at their own center, simple collision; same slots as on the character |
| `SM_Hat1`, `SM_Hat2`, `SM_Hat3` | ~0.9k | ball cap / beanie / brimmed hat, pivot at hat center, box collision |
| `SM_Ambulance` | 6.9k | cartoony van with "MEDIC" decals (no cross / star of life), siren bar; wheels on z = 0, **front = +X**, length ≈ 4.6 m |
| `SM_Resurfacer` | 7.8k | original ice-resurfacing machine, ICE RIOT livery, front = +X |
| `SM_TitleLogo` | 34k | extruded ICE RIOT logo, centered; letters face **Unreal +Y** (toward the default camera side), read along +X, ~4.2 m wide |

Triangle budget: arena + crowd + rink ≈ 590k (≤ 600k). Skater 14.9k (≤ 15k), goalie 17.3k (≤ 18k).

Arena layout (meters, offset measured outward from the boards' inner face): concourse to 3.2, lower bowl rows
from z 1.35 rising 0.40/row to offset 17.8 / z 8.15, suite wall + ribbon board to z 12.4, upper deck to offset
31.3 / z 20.6, roof at z 36. A broadcast camera at Unreal (0, +2200..+2600, 1100..1400) looks over the near seats.

## Skeletal meshes

* `/Game/IceRiot/Meshes/SK_Skater`, `/Game/IceRiot/Meshes/SK_Goalie`, both on
  **`/Game/IceRiot/Meshes/SK_Skater_Skeleton`** (25 bones, names exact):
  `root pelvis spine_01 spine_02 spine_03 neck head clavicle_l upperarm_l lowerarm_l hand_l clavicle_r upperarm_r
  lowerarm_r hand_r stick stick_blade thigh_l calf_l foot_l toe_l thigh_r calf_r foot_r toe_r`.
* Height ≈ 1.95 m on skates (blade bottom at z = 0). Right-handed shooter: blade on the character's right.
* **`stick`**: child of `hand_r`, head at the bottom-hand grip, runs down the shaft. Scale it to 0 to hide the
  stick (it collapses into the glove). The stick bone carries keyed rotation (and tiny translation) in clips.
* **`stick_blade`**: child of `stick`; its location is **where the puck CENTER sits when cradled on the forehand**
  (in front of the blade face, 1.27 cm above the blade bottom) — attach the puck with zero offset.
  Local axes in Unreal: **+X along the blade toward the toe**, +Z = blade up, −Y = forehand face normal (puck side).
  In the bind pose the stick is held steeper than in play, so the toe is tipped up 20° and the bone sits at
  z ≈ 6 cm; in every on-ice clip the blade lies flat and the bone is at z ≈ 1.27 cm.
* **Big-head mode**: scale `head` — head, face, helmet, visor, chin strap, goalie mask + cage are 100 % `head`.
* No physics asset is generated (the falls/flip are authored animations).

### Material slots (slot name = material instance in `/Game/IceRiot/Materials/`)
SK_Skater: `MI_TeamPrimary MI_TeamSecondary MI_TeamTrim MI_Pants MI_Skin MI_SkateBoot MI_Face MI_Helmet MI_Visor
MI_Gloves MI_StickTape MI_SkateBlade MI_StickShaft MI_Number MI_JerseyCrest`
SK_Goalie: same minus helmet/visor, plus `MI_GoalieMask MI_GoaliePads` (`MI_Face` is present but hidden under the mask).

* Jersey: body `MI_TeamPrimary`; shoulder yoke, hem band, sleeve band, sock band = `MI_TeamSecondary`;
  thin pinstripes, collar, hem edge, glove cuff roll = `MI_TeamTrim`. Socks use Primary/Secondary/Trim too.
  Neck guard + skate boots + chin strap = `MI_SkateBoot` (black).
* **Extra slot `MI_JerseyCrest`** (not in the spec): chest crest decal, masked material, texture param
  **`BaseTexture`** → set it to `T_Logo_<Id>` per team (defaults to `T_Logo_NAR`).
* `MI_Helmet`, `MI_Gloves`, `MI_Pants`, `MI_StickShaft`, `MI_GoaliePads`, `MI_GoalieMask` are **team-shader**
  instances too (vector `Color`) so the game can tint them (suggest: helmet/gloves/pants = secondary,
  goalie mask = primary; `MI_GoalieMask` has a painted grey-scale design texture `T_GoalieMask` multiplied by `Color`).
* Referee: put **`MI_RefJersey`** on `MI_TeamPrimary`, `MI_TeamSecondary` and `MI_TeamTrim` (black/white vertical
  stripes from `T_RefStripes` via cylindrical jersey UVs); suggest black `Color` on helmet/pants/gloves MIDs and
  hide the stick (scale `stick` to 0). `A_RefDrop` / `A_RefSignal` are authored for the ref.
* Numbers: `MI_Number` quads on the back and both sleeves (two-digit area, UV 0..1).

## Master materials (`/Game/IceRiot/Materials/M_IR_*`) and parameters

| Shader | Master | Parameters |
|---|---|---|
| team | `M_IR_Team` | vector `Color`, texture `Texture` (white default), `Roughness`, `Metallic`, plus emissive extras `RimColor`/`RimStrength` (fresnel rim, e.g. BLAZING / RAGE) and `FlashColor`/`FlashStrength` (hit flash) |
| skin | `M_IR_Skin` | vector `SkinColor`, texture `Texture` (T_Face, features in alpha), `FaceAmount` (0 on MI_Skin), `Roughness`, `Specular`, same Rim/Flash extras |
| number | `M_IR_Number` | scalars `Tens` (−1 = single digit, centered) and `Ones`, vectors `Color` (fill) and `OutlineColor`, texture `Digits` (T_Digits: R = fill, G = fill+outline); masked |
| ice | `M_IR_Ice` | texture `Markings` (T_IceMarkings), vector `Tint`, scalar **`Wear`** 0..1 (scratches + snow dulling), texture `Scratches`, vector `SnowColor`, `RoughnessMin` (0.07), `RoughnessMax`, `Specular` |
| screen | `M_IR_Screen` | texture **`Screen`** (default T_JumboDefault — feed your render target), scalar `Brightness` (unlit) |
| goallight | `M_IR_GoalLight` | scalar **`On`** 0..1, `EmissiveStrength` (60), `IdleGlow`, vector `Color` |
| crowd | `M_IR_Crowd` | scalar **`Excitement`** 0..1 (make a MID of `MI_Crowd`); vertex color base, bob via WPO: phase = UV0.x, amplitude = 1−UV0.y (FBX flips V), height 2.5 cm + 22 cm × Excitement, frequency rises with Excitement |
| opaque | `M_IR_Opaque` | `BaseTexture`, `BaseColor`, `Tiling`, `Roughness`, `Metallic`, `Specular`, `EmissiveColor`, `EmissiveStrength` |
| masked | `M_IR_Masked` | `BaseTexture` (alpha = mask), `BaseColor`, `Tiling`, `Roughness`; two-sided |
| glass | `M_IR_Glass` | `BaseColor`, `Opacity`, `Roughness` (translucent, two-sided, fresnel edge) |
| emissive | `M_IR_Emissive` | `BaseTexture`, `BaseColor`, `EmissiveStrength`, `PanU`, `PanV`, `Tiling` (unlit) — ribbon boards, siren lights, arena lamps |
| vertexcolor | `M_IR_VertexColor` | `BaseColor`, `Roughness`, `Metallic` |

All masters are flagged for skeletal + instanced static meshes, no tessellation/fancy features (web-safe);
the number shader uses one small Custom HLSL node.

## Textures — `/Game/IceRiot/Textures/`
`T_Logo_<Id>` (1024² RGBA crests: NAR INF YET HAM BRW VIP GRZ COM), `T_Banner_<Id>` (1024×2048 pennants),
`T_LogoIceRiot` (2048×1024 RGBA), `T_BoardAds` (2048² atlas, 2 × 8 cells of 4:1 ads), `T_Digits` (2048×256, linear),
`T_IceMarkings` (4096×2048), `T_IceScratches`, `T_Netting`, `T_PuckTop`, `T_Face`, `T_GoalieMask`, `T_RefStripes`,
`T_RibbonBoard`, `T_JumboDefault`.
Team colors (linear RGB + sRGB hex, city, name, logo/banner names): **`Art/Export/teams.json`**.

Sponsors (all fictional): Frostbite Cola, Puck Yeah! Energy, Toothless Dental, Penalty Box Pizza, Moosejaw
Insurance, Blue Line Bank, Icy Dogs, Big Lumber, Glove Drop, Slapshot Soda, Goon Squad Security, Maple Crunch,
Slush Bucket, 5-Hole Donuts, ICE RIOT, Snowplow Trucks.

## Animations — `/Game/IceRiot/Anims/` (30 fps, in place, all on SK_Skater_Skeleton)

Clip lengths are whole frames, so spec lengths that fall on half frames are rounded **up** by ≤ 1/60 s
(e.g. 0.55 → 0.567). Event times are exactly as specified (also stored as markers in the .blend and in
`Art/Export/Manifests/anims.json`). Looping clips have identical first/last frames.

| Clip | Length s (frames) | Loop | Event (s) |
|---|---|---|---|
| A_Idle | 2.000 (60) | yes | |
| A_Skate | 0.800 (24) | yes | |
| A_SkateTurbo | 0.600 (18) | yes | (right hand only on the stick, left arm pumps) |
| A_Glide | 1.200 (36) | yes | |
| A_SkateBack | 1.000 (30) | yes | |
| A_Carry | 0.800 (24) | yes | blade sweeps L↔R on the ice |
| A_Stop | 0.467 (14) | | |
| A_ShotWrist | 0.567 (17) | | release 0.22 |
| A_SlapWindup | 0.400 (12) | | ends at full backswing (hold) |
| A_SlapRelease | 0.500 (15) | | impact 0.10 (starts from the windup pose) |
| A_OneTimer | 0.567 (17) | | impact 0.18 |
| A_Pass | 0.467 (14) | | release 0.16 |
| A_Check | 0.567 (17) | | contact 0.18 |
| A_PowerCheck | 0.700 (21) | | contact 0.22 |
| A_PokeCheck | 0.467 (14) | | poke 0.15 |
| A_Hook | 0.600 (18) | | hook 0.20 |
| A_Dive | 1.200 (36) | | ends lying **prone** |
| A_HitFall | 1.100 (33) | | ends lying **supine** |
| A_Flip | 1.200 (36) | | twisting back-flip, ends supine (same pose as HitFall end) |
| A_GetUp | 0.900 (27) | | starts from the supine pose (HitFall/Flip/FightKO end) |
| A_Celebrate1 | 2.400 (72) | | fist pumps, stick raised |
| A_Celebrate2 | 2.400 (72) | | knee slide + stick guitar |
| A_Celebrate3 | 2.400 (72) | | jump into the glass (glass is in front, character −Y in Blender / +Y in UE mesh space) |
| A_Dejected | 2.000 (60) | yes | |
| A_FaceoffReady | 1.000 (30) | yes | |
| A_FaceoffWin | 0.400 (12) | | sweep 0.10 |
| A_FightIdle | 1.000 (30) | yes | |
| A_FightJab | 0.367 (11) | | hit 0.12 |
| A_FightPunch | 0.567 (17) | | hit 0.25 |
| A_FightUppercut | 0.700 (21) | | hit 0.32 |
| A_FightGrab | 0.600 (18) | | grab 0.25 |
| A_FightBlock | 0.500 (15) | | guard held at the end |
| A_FightHit | 0.467 (14) | | |
| A_FightKO | 1.600 (48) | | ends supine |
| A_GoalieReady | 2.000 (60) | yes | |
| A_GoalieShuffleL / R | 0.600 (18) | yes | toward the goalie's own left (+X Blender) / right |
| A_GoalieButterfly | 0.600 (18) | | held at the end |
| A_GoalieGloveHigh / BlockerHigh | 0.500 (15) | | |
| A_GoaliePadL / PadR | 0.500 (15) | | |
| A_GoalieDiveL / DiveR | 0.900 (27) | | ends on the ice |
| A_GoaliePoke | 0.500 (15) | | poke 0.18 |
| A_GoalieCover | 0.600 (18) | | held at the end |
| A_RefDrop | 1.000 (30) | | drop 0.55 (right hand) |
| A_RefSignal | 1.500 (45) | | right arm points forward |

Fight clips keep the stick in the right hand (the game hides it). Root motion is disabled on every sequence.

## Pass 2 changes (summary)
* Animations: deeper arcade lean everywhere (skating ≈ 69° total), hockey stride with outward push on the inside
  edge, stickhandling sweeps, stronger turbo arm pump, butterfly with pads facing the shooter, cleaner fight guard,
  fixed ref puck-drop hand. Clips that mix "both hands on the stick" and free-hand keys are re-solved so hands and
  stick never pop (PowerCheck, Dive, GetUp, Celebrate1-3, GoalieDiveR). Supine pose keeps the stick on the ice.
* Characters: goalie pads with channels, knee rolls, toe bridge and team-colored graphics; helmet crown cleaned.
* Crests: Vipers crest redesigned (spade head, brow plates, fangs + forked tongue); banners regenerated.
* Arena: open vomitory trenches instead of dark boxes; jumbotron bezels, corner light strips, underbelly screens.

## Verification artifacts
* `Art/Previews/` — `branding_crests.png`, `rink_*.png`, `arena_*.png`, `props.png`, `sk_skater_*.png`,
  `sk_goalie_*.png`, and `anim_<Name>.png` frame strips (3/4 view on top, profile below; the black disc is a
  stand-in puck on `stick_blade`). ~70 MB — consider gitignoring `Art/Previews/` if you don't want them committed.
* `Saved/ue_import_report.txt` — every imported asset with bounds and slots, skeleton bone list + axes,
  anim lengths/events, master-material shader statistics.

## Known limitations / ideas
* Clip lengths on half frames are rounded up by ≤ 1/60 s (see table).
* Dive ends prone while GetUp starts supine — blend ~0.2 s (or play HitFall's last pose) when chaining them.
* `SM_TitleLogo` is 34k tris (title screen only).
* No physics asset is generated for the skeletal meshes; falls/flips are authored animations.
* The bind pose holds the stick steeper than in play (blade toe tipped up); irrelevant at runtime.
