# ICE RIOT — Art Asset Contract

Every 3D asset and texture is generated procedurally by Python scripts in `Blender/` (Blender 5.3, headless),
exported to `Art/Export/`, then imported into Unreal 5.9 by `Tools/ue_import.py` into `/Game/IceRiot/...`.
The C++ game loads assets **by these exact paths and names**, so names below are a contract.

All branding is ORIGINAL: no real league/team/player/brand/game names or logos (no NHL, no "Zamboni" — say
"ice resurfacer"). The art target is a polished, chunky, stylized late-90s-arcade-meets-modern look:
bold saturated team colors, glossy ice, readable silhouettes from a high side camera, big bright arena.
The game also ships to the **web (WebGPU mobile renderer tier)**, so keep it lean: skater ≤ 15k tris,
goalie ≤ 18k, whole arena + crowd ≤ 600k tris, textures ≤ 2048² except the ice (4096×2048).

## Tools and conventions

* Blender: `/opt/homebrew/bin/blender -b --factory-startup --python-exit-code 1 -P Blender/<script>.py`.
  Blender 5.3 uses layered Actions only (`action.fcurves` does not exist; use the slot/channelbag API), Eevee id
  `BLENDER_EEVEE`. Numpy is available inside Blender's Python.
* Blender meters, Z up. Unreal centimeters, Z up. FBX maps Blender `(x, y, z)` m → Unreal `(100x, -100y, 100z)` cm.
* **Static meshes**: FBX in meters, `FBX_SCALE_NONE`; Unreal bakes object transforms, so the **static mesh pivot is
  the Blender WORLD ORIGIN**.
* **Skeletal meshes / animations**: build in meters, scale objects ×100 and apply, scene unit scale 0.01,
  `FBX_SCALE_ALL`; no import scale in Unreal (bones end up scale 1, in cm).
* Characters face **Blender −Y** in their rest pose and in every animation. Animations are **in place** (no root
  motion; the `root` bone stays at the origin, yaw 0). 30 fps.
* Camera convention: the main game camera sits on the Blender **−Y** side of the rink, elevated, looking toward +Y.
  Screen-right = Blender +X. Text/logos on the far boards, jumbotron faces, banners and the ice must read correctly
  from that view (ice logos read from −Y).
* Reference implementation of this whole pipeline (different sport, same engine/tools):
  `/Users/nearby/.t3/projects/basketballjam/Blender/*.py` and `/Users/nearby/.t3/projects/basketballjam/Tools/ue_import.py`.
  Reuse techniques freely, never its branding.

## Rink (Blender meters, center ice at origin, ice surface z = 0)

| Item | Value |
|---|---|
| Ice / boards inner face | x ∈ [−23, 23], y ∈ [−10.5, 10.5], corner radius 6.5 |
| Boards | 1.07 high, 0.15 thick, white with a 0.22 m yellow kick plate at the bottom, rounded top rail; ad panels on the board faces (fictional sponsors) |
| Glass | on top of the boards up to z = 2.45 (thin panes with visible stanchions every ~2.2 m). The near (−Y) side glass must be very transparent |
| Center red line | x = 0, 0.30 wide (with the center logo on top) |
| Blue lines | x = ±6.0, 0.30 wide |
| Goal lines | x = ±19.5, 0.05 wide red, spanning to the boards |
| Center circle | r 4.0 blue (0.05 line), center dot r 0.15 blue |
| End-zone face-off circles | centers (±14.5, ±5.5), r 4.0 red, hash marks, dot r 0.30 red |
| Neutral-zone dots | (±4.5, ±5.5), r 0.30 red |
| Goal crease | semicircle r 1.8 centered at (±19.5, 0), light-blue fill, red outline, opening toward center ice |
| Net mouth | centered on the goal line: y ∈ [−0.915, 0.915], height 1.22, red posts/crossbar r 0.03, depth 1.0 (back toward the end boards), white mesh netting |
| Puck | r 0.038, thickness 0.0254, centered at origin |
| Benches | two player benches behind the **far (+Y)** boards, penalty box(es) also on the far side |

## Skeleton `SK_Skater_Skeleton` (shared by skater, goalie, referee)

Required bone names (exact): `root` (at floor), `pelvis`, `spine_01`, `spine_02`, `spine_03`, `neck`, `head`,
`clavicle_l`, `upperarm_l`, `lowerarm_l`, `hand_l`, `clavicle_r`, `upperarm_r`, `lowerarm_r`, `hand_r`,
`thigh_l`, `calf_l`, `foot_l`, `toe_l`, `thigh_r`, `calf_r`, `foot_r`, `toe_r`, `stick` (child of `hand_r`, runs along
the shaft), `stick_blade` (child of `stick`, **located at the blade's puck contact point** on the ice, its +X pointing
along the blade toward the toe). More bones (fingers, twist) are optional.
The C++ attaches the puck to `stick_blade`, scales `head` for big-head mode, and hides the stick by scaling `stick`.
Skater height ≈ 1.95 m on skates; chunky arcade proportions (broad shoulder pads, slightly oversized helmet/gloves).

## Characters

| Asset | Notes |
|---|---|
| `SK_Skater` | helmet with visor, jersey (team colors, stripes, shoulder yoke), number on back + both sleeves, pants/breezers, shin socks with stripes, gloves, skates, stick. Face visible under the helmet |
| `SK_Goalie` | same skeleton: big leg pads, blocker (right hand), catching glove (left), chest protector under jersey, painted mask, goalie stick |
| Referee | **no separate mesh**: the game uses `SK_Skater` with `MI_RefJersey` on the jersey slots and the stick hidden |

**Material slots (exact names; the game overrides colors at runtime via MIDs):**
`MI_TeamPrimary`, `MI_TeamSecondary`, `MI_TeamTrim`, `MI_Helmet`, `MI_Visor`, `MI_Skin`, `MI_Face`, `MI_Gloves`,
`MI_Pants`, `MI_SkateBoot`, `MI_SkateBlade`, `MI_StickShaft`, `MI_StickTape`, `MI_Number`, plus goalie-only
`MI_GoaliePads`, `MI_GoalieMask`. Each skater/goalie MUST use these slot names (unused ones may be absent).

## Animations (`A_<Name>`, all on `SK_Skater_Skeleton`, 30 fps, in place)

Times in seconds. "evt" = gameplay event time the C++ relies on — make the motion hit it.

| Name | Len | Loop | Notes |
|---|---|---|---|
| A_Idle | 2.0 | ✓ | ready stance, knees bent, stick blade on the ice in front-right |
| A_Skate | 0.80 | ✓ | full stride cycle at ~7 m/s, stick on ice, arms swing naturally |
| A_SkateTurbo | 0.60 | ✓ | deep, aggressive sprint strides, lean forward |
| A_Glide | 1.2 | ✓ | coasting, both skates on ice, stick on ice |
| A_SkateBack | 1.0 | ✓ | backward C-cuts (defensive skating) |
| A_Carry | 0.80 | ✓ | skating while stickhandling: blade sweeps left-right in front of the body (blade stays on the ice) |
| A_Stop | 0.45 | | hockey stop, body turns 90°, skates scrape |
| A_ShotWrist | 0.55 | | evt release 0.22 |
| A_SlapWindup | 0.40 | | ends at full backswing (held by the game while charging) |
| A_SlapRelease | 0.50 | | starts from the windup pose; evt impact 0.10 |
| A_OneTimer | 0.55 | | fast slap from a short windup; evt impact 0.18 |
| A_Pass | 0.45 | | sweep pass; evt release 0.16 |
| A_Check | 0.55 | | shoulder check lunge; evt contact 0.18 |
| A_PowerCheck | 0.70 | | huge launching hit; evt contact 0.22 |
| A_PokeCheck | 0.45 | | stick jab forward along the ice; evt 0.15 |
| A_Hook | 0.60 | | stick hooks out to the side/front; evt 0.20 |
| A_Dive | 1.2 | | belly slide forward, ends lying prone |
| A_HitFall | 1.1 | | knocked off feet backward, lands on the ice (ends lying) |
| A_Flip | 1.2 | | power-check victim: tumbling cartwheel in the air, ends lying (the game moves the actor along an arc) |
| A_GetUp | 0.9 | | from lying to ready stance |
| A_Celebrate1 | 2.4 | | big fist pump, stick raised |
| A_Celebrate2 | 2.4 | | knee slide with bow-and-arrow / stick-guitar style flair (original) |
| A_Celebrate3 | 2.4 | | jump into the glass, arms raised |
| A_Dejected | 2.0 | ✓ | head down, slow glide |
| A_FaceoffReady | 1.0 | ✓ | deep crouch, stick on ice |
| A_FaceoffWin | 0.40 | | quick sweep backward; evt 0.10 |
| A_FightIdle | 1.0 | ✓ | gloves off, fists up, bouncing (stick hidden by game) |
| A_FightJab | 0.35 | | evt hit 0.12 |
| A_FightPunch | 0.55 | | evt hit 0.25 |
| A_FightUppercut | 0.70 | | evt hit 0.32 |
| A_FightGrab | 0.60 | | grabs jersey; evt 0.25 |
| A_FightBlock | 0.50 | | arms up guard |
| A_FightHit | 0.45 | | head snaps back |
| A_FightKO | 1.6 | | wobble and collapse, ends lying |
| A_GoalieReady | 2.0 | ✓ | goalie crouch, stick on ice, glove open |
| A_GoalieShuffleL / A_GoalieShuffleR | 0.6 | ✓ | lateral shuffle (character's own left / right) |
| A_GoalieButterfly | 0.6 | | drop to butterfly, held at end |
| A_GoalieGloveHigh | 0.5 | | glove-side high save |
| A_GoalieBlockerHigh | 0.5 | | blocker-side high save |
| A_GoaliePadL / A_GoaliePadR | 0.5 | | pad kick save low left/right |
| A_GoalieDiveL / A_GoalieDiveR | 0.9 | | full stretch dive, ends on the ice |
| A_GoaliePoke | 0.5 | | poke check; evt 0.18 |
| A_GoalieCover | 0.6 | | smothers the puck, held at end |
| A_RefDrop | 1.0 | | referee bends and drops the puck; evt drop 0.55 |
| A_RefSignal | 1.5 | | arm points at the net (goal signal) |

## Props and environment (static meshes)

| Asset | Notes |
|---|---|
| `SM_Puck` | black vulcanized rubber, subtle knurled edge, logo on top |
| `SM_Net` | the **+X** end net: mouth on the goal line x = +19.5 facing −X (toward center). Separate material for netting (`MI_Netting`, masked/translucent) and posts (`MI_GoalPost`). Pivot = world origin (so the C++ places it with an identity transform; it mirrors it for the −X end) |
| `SM_NetBurning` optional | — (fire is done with game VFX) |
| `SM_Ice` | the ice slab with markings, pivot origin. Material `MI_Ice` (texture `T_IceMarkings`, 4096×2048 covering x ∈ [−23,23], y ∈ [−10.5,10.5]) |
| `SM_Boards` | boards + kick plate + rail + board ads (`MI_BoardAds`, texture `T_BoardAds`) |
| `SM_Glass` | glass panes `MI_Glass` + stanchions; near side included |
| `SM_Arena` | bowl, stairs, upper deck, suite level, rafters, scoreboard truss, benches, penalty boxes, tunnels, banners |
| `SM_Crowd` | thousands of stylized fans (low poly) using `MI_Crowd` (crowd shader: vertex color, per-fan bob phase in UV0.x and amplitude in UV0.y; the C++ drives a `Excitement` scalar 0..1) |
| `SM_Jumbotron` | center-hung 4-sided video cube above center ice, bottom ~16 m; screens use `MI_JumboScreen` whose texture param `Screen` the game feeds with a render target (each face UV 0..1) |
| `SM_GoalLight` | red goal light dome behind each net; game toggles its emissive via `MI_GoalLight` scalar `On` |
| `SM_Helmet`, `SM_Glove`, `SM_Stick` | loose props (helmet/stick fly off on power checks; gloves dropped in fights) |
| `SM_Hat` | a few hat styles in one mesh or `SM_Hat1..3` (hat-trick hats raining on the ice) |
| `SM_Ambulance` | cartoony original ambulance (flat-ish side profile, red cross-free: use a star-of-life-free generic "MEDIC" decal), drives across the top of the screen as a gag |
| `SM_Resurfacer` | optional: an original ice-resurfacing machine for the intermission/title scene |
| `SM_TitleLogo` | 3D extruded ICE RIOT logo for the title screen |

## Team branding (8 original teams)

| Id | Team | Primary | Secondary | Trim |
|---|---|---|---|---|
| NAR | Northport Narwhals | teal | navy | white |
| INF | Brimstone Inferno | crimson | orange | black |
| YET | Glacier Bay Yetis | ice blue | white | silver |
| HAM | Steel Valley Hammers | black | gold | white |
| BRW | Bayou Brawlers | swamp green | gold | black |
| VIP | Neon Coast Vipers | magenta | electric purple | white |
| GRZ | Timber Ridge Grizzlies | brown | orange | cream |
| COM | Rocket City Comets | royal blue | red | white |

Textures: `T_Logo_<Id>` (1024² RGBA, bold flat vector-style crest), `T_LogoIceRiot` (game logo, RGBA),
`T_BoardAds` (fictional, funny sponsors), banners `T_Banner_<Id>`. Write the exact team colors (linear RGB) to
`Art/Export/teams.json` (the C++ copies them). The ice markings texture has the ICE RIOT logo at center ice.

## Material contract

Same as the reference pipeline: material slot names ARE the Unreal material-instance names, unique project-wide.
Every generator writes `Art/Export/Materials/<generator>.json` mapping `MI_*` → parameters. Shaders:
`opaque`, `vertexcolor`, `glass`, `emissive` (with `pan_u`/`pan_v`), `masked`, `crowd`, plus:

* `team` — BaseColor = vector param `Color` × optional texture (white default); `roughness`, `metallic`. Used by every
  team-colored slot; the game sets `Color` per player.
* `skin` — BaseColor = lerp(vector param `SkinColor`, texture.rgb, texture.a) (for `MI_Face`; eyes/brows painted in the
  texture alpha) .
* `number` — jersey number: two digits from a digit atlas `T_Digits` (10 bold block digits in a row, white fill with a
  dark outline in a second channel). Scalar params `Tens` (−1 = single digit) and `Ones`, vector params `Color`
  (fill) and `OutlineColor`. Number mesh quads UV 0..1 span the full two-digit area; masked where no digit.
* `ice` — glossy ice: markings texture, very low roughness (0.05–0.12) with subtle scratch variation, slight
  subsurface-ish blue tint; optional scalar `Wear` 0..1 (the game raises it each period).
* `screen` — unlit emissive with texture param `Screen` (render target), scalar `Brightness`.

## Outputs and import

* `Art/Export/Meshes/*.fbx`, `Art/Export/Anims/A_*.fbx`, `Art/Export/Textures/T_*.png`, `Art/Export/Materials/*.json`,
  `Art/Export/teams.json`. Keep every `.blend` in `Art/Blend/` (the web build may re-export from them).
* `Tools/build_art.sh` regenerates everything; `Tools/import_assets.sh` runs `Tools/ue_import.py` headless.
* Unreal paths: `/Game/IceRiot/Meshes/` (SK_, SM_), `/Game/IceRiot/Anims/` (A_), `/Game/IceRiot/Materials/` (masters
  `M_*` and `MI_*`), `/Game/IceRiot/Textures/` (T_). Skeleton: `/Game/IceRiot/Meshes/SK_Skater_Skeleton`.
* The import also creates an empty map `/Game/Maps/Arena` (the C++ spawns everything into it at runtime).
