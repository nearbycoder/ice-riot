# ICE RIOT — Audio Notes

Everything in this file is produced by `Tools/gen_audio.py` (contract: `Docs/AUDIO_SPEC.md`). All sounds,
music and organ riffs are original procedural synthesis (numpy); announcer lines are macOS `say` + an arena-PA chain.

## Regenerate + import

```sh
# 1. generate all 173 WAVs (~40 s on 16 cores), verify them, write manifest + preview PNGs
/Applications/Blender.app/Contents/Resources/5.3/python/bin/python3.13 Tools/gen_audio.py
#    options: --only Shot_,VO_Goal   --category Music   --no-vo   --check   --no-previews   --jobs N
# 2. import into Unreal headless (needs the editor module built: Tools/build.sh)
Tools/import_audio.sh            # or: Tools/import_audio.sh --gen   (generate + import)
```

* Output: `Art/Export/Audio/<Category>/<Name>.wav` (48 kHz, 16-bit PCM, gitignored) + `Art/Export/Audio/manifest.json`
  (per-file duration, channels, loop, peak, LUFS, Unreal path, sound class, BPM/bars, VO text).
* Verification previews: `Art/Export/Audio/_Previews/` (waveform + log spectrogram per asset, music overview with
  bar lines, loop-seam close-ups). The generator fails (exit 1) on clipping, peaks above −0.5 dBFS, loop seam
  discontinuities, leading silence on SFX/UI, or a channel/duration mismatch.
* Import: `Tools/ue_import_audio.py` (pythonscript commandlet), report `Saved/ue_import_audio_report.txt`,
  log `Saved/ue_import_audio.log`. Re-running is idempotent (re-imports in place, keeps the class/mix assets).
* Deterministic: fixed seeds; only the announcer depends on the installed `say` voice.
* Code: `Tools/audio/dsp.py` (DSP core, BS.1770 loudness), `sfx.py` (SFX + UI), `crowd.py` (crowd + stadium organ),
  `music.py` (tracker, instruments, 5 compositions), `vo.py` (announcer), `preview.py` (analysis + PNGs).

## Unreal assets

* SoundWaves: `/Game/IceRiot/Audio/<Category>/<Name>` (Category = `Sfx`, `Crowd`, `Music`, `UI`, `Announcer`).
* Sound classes `/Game/IceRiot/Audio/Classes/`: `SC_Master` → children `SC_Music`, `SC_SFX`, `SC_Crowd`,
  `SC_Announcer`, `SC_UI` (parent links verified). Mapping: Sfx→`SC_SFX`, Crowd (incl. organ)→`SC_Crowd`,
  Music→`SC_Music`, UI→`SC_UI`, Announcer→`SC_Announcer`.
* Sound mixes `/Game/IceRiot/Audio/Classes/`:
  * `SM_Default` — adjusters for every class at 1.0 (`SC_Master` applies to children). Use as the base mix /
    for options volume sliders (`SetSoundMixClassOverride`).
  * `SM_AnnouncerDuck` — Music ×0.55, Crowd ×0.6, SFX ×0.85, fade in 0.08 s / out 0.45 s. Registered as a
    **passive modifier on `SC_Announcer`**, so it engages automatically whenever an announcer line is audible.
* Loops (`bLooping` = true, virtualization *Play When Silent*): `Shot_Charge`, `Fire_Loop`, `Crowd_Ambience`,
  `Crowd_Excited`, `Music_Title`, `Music_Menu`, `Music_Intermission`, `Music_Overtime`. Every loop is
  sample-exact (all events, echoes and reverb tails wrap around the loop point); loop the whole file.

## Conventions for gameplay code

* One-shots start at sample 0 (no leading silence): trigger at the impact. Shots/punches carry a ≤0.16 s
  wind-up swish before the hit.
* Levels: SFX / UI / crowd one-shots / organ peak −1 dBFS; `Shot_Charge`, `Fire_Loop` peak −3 dBFS;
  `Crowd_Ambience` −23 LUFS, `Crowd_Excited` −20 LUFS (crossfade them; equal-gain crossfade raises energy ~3 LU);
  music −14 LUFS integrated (victory sting −13), ceiling −1 dBFS; announcer −14 LUFS, ceiling −1 dBFS.
* Mono (spatialize): all SFX and VO except stereo `Goal_Horn`, `Period_Buzzer`, `Ambulance_Siren` (pans L→R —
  play 2D to match the ambulance gag crossing the top of the screen), `Hat_Rain`, `UI_Start`, `UI_Impact`.
  Crowd, organ and music are stereo (play 2D).
* `Shot_Charge` is a Shepard–Risset glissando: it sounds like it rises forever, so it can loop for any hold time.
  Raise its pitch multiplier with charge for extra urgency if wanted.
* `VO_Wins` ("wins it!") is meant to follow a `VO_Team_<Id>` line (team lines are just the team name).

## Announcer voice

Every installed English voice was rendered with the same test phrase and compared by pitch range, bandwidth
and formants (no speaker playback):

| Voice | Result |
|---|---|
| Siri neural "Voice 6" (en-US) / "Voice 2" Simone (premium) | natural but female register (~230–310 Hz), ignore pitch control (rate/pitch multiplier, SSML) |
| Aman (Premium, en-IN) | clean neural voice, but flat delivery (~6 semitone range) |
| **Daniel (en-GB)** | **chosen**: most expressive male voice installed (~15 semitone range, full bandwidth) |
| Reed, Rocko, Eddy, Fred, Ralph, Albert, Junior, Grandpa, Samantha, Flo, Sandy, Shelley | flatter or narrower-band |

Short calls are spoken slower (172 wpm for 1–2 words, 188 for 3–4, 200 otherwise). `VO_Goal_10` and
`VO_Fight_03` are rendered as three escalating calls (each part higher, the last one slower). PA chain: 4th-order
110 Hz HPF → low shelf/mud cut/presence/air EQ → parallel saturation → 4.5:1 compression → limiter → PA
slap-backs at 75/165/290 ms → 1.5 s arena tail → −14 LUFS. Override the voice with
`ICE_RIOT_VO_VOICE=<name>` (e.g. install a Premium/Enhanced male voice in System Settings → Accessibility →
Spoken Content, then regenerate with `--category Announcer`).

## Music

| Track | Tempo / key | Length | Form |
|---|---|---|---|
| `Music_Title` | 144 BPM, E minor | 36 bars = 60.0 s loop | intro riff (4) → verse riff + synth hook (8) → chorus C–D–Em–Em–C–D–B–B (8) → half-time arp breakdown (4) → guitar solo over the riff (8) → turnaround + snare build into the loop (4) |
| `Music_Menu` | 128 BPM, A dorian, swung 16ths | 24 bars = 45.0 s loop | Am7–D9 funk vamp (slap-style synth bass, wah chops, e-piano, brass stabs) → Fmaj7–G–Em7–Am7… lead hook → vamp with lead + bell double |
| `Music_Intermission` | 96 BPM, D minor | 18 bars = 45.0 s loop | big-beat breakbeat, acid-ish bass, stadium-organ comping and organ melody, distorted guitar stabs in the B section |
| `Music_Overtime` | 144 BPM, C minor | 12 bars = 20.0 s loop | timpani + palm-muted chugs + string ostinato, Ab–Bb lift, Cm–Db–Cm–G7 build with snare roll back to the top |
| `Music_Victory` | 140 BPM, E major | 8.0 s sting | fanfare over E–A–B–E power chords + brass, drum roll, final crash and ring-out |

Instruments are synthesized: Karplus–Strong guitars (double-tracked, amp + cab), KS picked bass, PolyBLEP
leads with glide/vibrato, distorted "guitar lead", supersaw pads, synth brass, FM e-piano, drawbar organ with
rotary swirl, and a synthesized rock kit.

## Asset list

### Sfx (`/Game/IceRiot/Audio/Sfx/`, SC_SFX)

| Asset | Dur (s) | Ch | Loop | Peak dBFS | LUFS | Notes |
|---|---:|---:|:---:|---:|---:|---|
| Skate_Stride_01 | 0.34 | 1 |  | -1.0 | -16.1 | Crisp ice carve, one skating stride |
| Skate_Stride_02 | 0.38 | 1 |  | -1.0 | -14.8 | Crisp ice carve, one skating stride |
| Skate_Stride_03 | 0.31 | 1 |  | -1.0 | -15.4 | Crisp ice carve, one skating stride |
| Skate_Stride_04 | 0.41 | 1 |  | -1.0 | -16.6 | Crisp ice carve, one skating stride |
| Skate_Stride_05 | 0.36 | 1 |  | -1.0 | -17.0 | Crisp ice carve, one skating stride |
| Skate_Stride_06 | 0.33 | 1 |  | -1.0 | -15.8 | Crisp ice carve, one skating stride |
| Skate_Stop_01 | 0.97 | 1 |  | -1.0 | -14.8 | Hockey stop: blade spray / scrape |
| Skate_Stop_02 | 1.07 | 1 |  | -1.0 | -12.6 | Hockey stop: blade spray / scrape |
| Skate_Stop_03 | 0.90 | 1 |  | -1.0 | -12.5 | Hockey stop: blade spray / scrape |
| Skate_Turbo | 1.10 | 1 |  | -1.0 | -16.8 | Turbo burst: hard strides + rising whoosh + power hum |
| Stick_Handle_01 | 0.32 | 1 |  | -1.0 | -24.8 | Light puck taps on the blade |
| Stick_Handle_02 | 0.32 | 1 |  | -1.0 | -24.5 | Light puck taps on the blade |
| Stick_Handle_03 | 0.32 | 1 |  | -1.0 | -21.5 | Light puck taps on the blade |
| Stick_Handle_04 | 0.32 | 1 |  | -1.0 | -22.1 | Light puck taps on the blade |
| Shot_Wrist_01 | 0.75 | 1 |  | -1.0 | -17.0 | Snappy wrist shot |
| Shot_Wrist_02 | 0.75 | 1 |  | -1.0 | -17.1 | Snappy wrist shot |
| Shot_Wrist_03 | 0.75 | 1 |  | -1.0 | -18.9 | Snappy wrist shot |
| Shot_Slap_01 | 1.60 | 1 |  | -1.0 | -15.8 | Huge slap shot crack (stick on ice + puck) |
| Shot_Slap_02 | 1.60 | 1 |  | -1.0 | -14.1 | Huge slap shot crack (stick on ice + puck) |
| Shot_Slap_03 | 1.60 | 1 |  | -1.0 | -13.6 | Huge slap shot crack (stick on ice + puck) |
| Shot_Power | 2.60 | 1 |  | -1.0 | -12.5 | Arcade power shot: massive slap + fiery whoosh + sub boom |
| Shot_Charge | 2.00 | 1 | yes | -3.0 | -11.9 | Rising charge-up tone (Shepard glissando), seamless loop |
| Pass_01 | 0.55 | 1 |  | -1.0 | -19.2 | Sharp sweep pass |
| Pass_02 | 0.55 | 1 |  | -1.0 | -21.5 | Sharp sweep pass |
| Pass_03 | 0.55 | 1 |  | -1.0 | -21.7 | Sharp sweep pass |
| Puck_Post_01 | 2.20 | 1 |  | -1.0 | -12.5 | Metallic PING off the goal post |
| Puck_Post_02 | 2.20 | 1 |  | -1.0 | -12.5 | Metallic PING off the goal post |
| Puck_Crossbar | 2.20 | 1 |  | -1.0 | -14.0 | Higher metallic ring off the crossbar |
| Puck_Boards_01 | 0.80 | 1 |  | -1.0 | -19.1 | Hollow thud off the dasher boards |
| Puck_Boards_02 | 0.80 | 1 |  | -1.0 | -18.9 | Hollow thud off the dasher boards |
| Puck_Boards_03 | 0.80 | 1 |  | -1.0 | -18.0 | Hollow thud off the dasher boards |
| Puck_Boards_04 | 0.80 | 1 |  | -1.0 | -20.1 | Hollow thud off the dasher boards |
| Puck_Glass_01 | 1.01 | 1 |  | -1.0 | -21.1 | Puck thunk off the glass (+ panel rattle) |
| Puck_Glass_02 | 1.04 | 1 |  | -1.0 | -24.5 | Puck thunk off the glass (+ panel rattle) |
| Puck_Ice_01 | 0.55 | 1 |  | -1.0 | -18.4 | Puck landing flat on the ice |
| Puck_Ice_02 | 0.55 | 1 |  | -1.0 | -19.2 | Puck landing flat on the ice |
| Puck_Ice_03 | 0.55 | 1 |  | -1.0 | -19.2 | Puck landing flat on the ice |
| Net_Ripple | 0.89 | 1 |  | -1.0 | -19.2 | Puck hitting the back of the net mesh |
| Check_01 | 0.77 | 1 |  | -1.0 | -18.9 | Body check thud (pads) |
| Check_02 | 0.80 | 1 |  | -1.0 | -17.8 | Body check thud (pads) |
| Check_03 | 0.80 | 1 |  | -1.0 | -18.0 | Body check thud (pads) |
| Check_04 | 0.80 | 1 |  | -1.0 | -16.9 | Body check thud (pads) |
| Check_Power | 2.60 | 1 |  | -1.0 | -17.7 | Enormous power-check crunch + boards + glass rattle |
| Boards_Slam_01 | 1.90 | 1 |  | -1.0 | -19.2 | Player slammed into the boards, glass shakes |
| Boards_Slam_02 | 1.90 | 1 |  | -1.0 | -18.8 | Player slammed into the boards, glass shakes |
| Fall_Ice_01 | 1.40 | 1 |  | -1.0 | -18.2 | Body hitting the ice + slide |
| Fall_Ice_02 | 1.60 | 1 |  | -1.0 | -17.8 | Body hitting the ice + slide |
| Fall_Ice_03 | 1.20 | 1 |  | -1.0 | -17.8 | Body hitting the ice + slide |
| Stick_Clack_01 | 0.50 | 1 |  | -1.0 | -21.0 | Sticks clashing (pokes, hooks) |
| Stick_Clack_02 | 0.50 | 1 |  | -1.0 | -16.4 | Sticks clashing (pokes, hooks) |
| Stick_Clack_03 | 0.50 | 1 |  | -1.0 | -12.3 | Sticks clashing (pokes, hooks) |
| Save_Pad_01 | 0.60 | 1 |  | -1.0 | -20.5 | Puck off the goalie leg pad |
| Save_Pad_02 | 0.60 | 1 |  | -1.0 | -20.6 | Puck off the goalie leg pad |
| Save_Pad_03 | 0.60 | 1 |  | -1.0 | -19.5 | Puck off the goalie leg pad |
| Save_Glove | 0.60 | 1 |  | -1.0 | -19.3 | Glove snag: leather pop |
| Save_Blocker | 0.70 | 1 |  | -1.0 | -18.5 | Blocker deflection |
| Save_Power | 2.59 | 1 |  | -1.0 | -18.6 | 'Brick wall' power save: stone thud + magic shimmer |
| Whistle_Short | 0.90 | 1 |  | -1.0 | -9.5 | Referee whistle, short blast |
| Whistle_Long | 1.80 | 1 |  | -1.0 | -7.8 | Referee whistle, tweet + long blast |
| Goal_Horn | 5.00 | 2 |  | -1.0 | -9.2 | Deep arena goal horn (~4 s, stereo) |
| Period_Buzzer | 3.10 | 2 |  | -1.0 | -8.5 | End-of-period buzzer (stereo) |
| Faceoff_Drop | 0.60 | 1 |  | -1.0 | -23.6 | Puck slapped onto the ice at the face-off |
| Fight_Jab_01 | 0.45 | 1 |  | -1.0 | -16.2 | Fight: quick jab |
| Fight_Jab_02 | 0.45 | 1 |  | -1.0 | -13.7 | Fight: quick jab |
| Fight_Jab_03 | 0.45 | 1 |  | -1.0 | -15.5 | Fight: quick jab |
| Fight_Punch_01 | 0.65 | 1 |  | -1.0 | -16.5 | Fight: hard punch |
| Fight_Punch_02 | 0.65 | 1 |  | -1.0 | -14.9 | Fight: hard punch |
| Fight_Punch_03 | 0.65 | 1 |  | -1.0 | -14.3 | Fight: hard punch |
| Fight_Uppercut | 1.30 | 1 |  | -1.0 | -13.9 | Fight: big uppercut |
| Fight_Block | 0.45 | 1 |  | -1.0 | -18.0 | Fight: forearm block |
| Fight_Grab | 0.75 | 1 |  | -1.0 | -16.9 | Fight: jersey tug |
| Gloves_Drop | 1.48 | 1 |  | -1.0 | -16.4 | Gloves and stick hitting the ice |
| Ambulance_Siren | 3.24 | 2 |  | -1.0 | -14.3 | Comedic siren racing past L->R with doppler (~3.3 s, stereo) |
| Flame_Burst | 2.20 | 1 |  | -1.0 | -13.2 | Net bursts into flame |
| Fire_Loop | 6.00 | 1 | yes | -3.0 | -18.3 | Crackling fire, seamless 6 s loop |
| Hat_Rain | 4.56 | 2 |  | -1.0 | -12.8 | Hats raining onto the ice (stereo) |
| Glass_Rattle | 1.60 | 1 |  | -1.0 | -20.0 | Rink glass rattling in its frame |

### Crowd (`/Game/IceRiot/Audio/Crowd/`, SC_Crowd)

| Asset | Dur (s) | Ch | Loop | Peak dBFS | LUFS | Notes |
|---|---:|---:|:---:|---:|---:|---|
| Crowd_Ambience | 30.00 | 2 | yes | -8.2 | -23.0 | Indoor arena murmur, seamless 30 s loop |
| Crowd_Excited | 30.00 | 2 | yes | -7.3 | -20.0 | Energetic crowd, seamless 30 s loop (crossfade with ambience) |
| Crowd_Cheer_Big | 5.92 | 2 |  | -1.0 | -12.6 | Goal eruption (6 s) |
| Crowd_Cheer_Small | 2.43 | 2 |  | -1.0 | -11.7 | Small cheer (2.5 s) |
| Crowd_Ooh | 1.93 | 2 |  | -1.0 | -13.0 | Near-miss 'ooh' |
| Crowd_Aah | 2.14 | 2 |  | -1.0 | -12.8 | Disappointed 'aww' |
| Crowd_Boo | 2.95 | 2 |  | -1.0 | -11.4 | Boo (3 s) |
| Crowd_Chant | 8.75 | 2 |  | -1.0 | -18.8 | Stomp-stomp-clap x3 with 'hey!' answers and a wordless chant |
| Organ_Charge | 6.62 | 2 |  | -1.0 | -11.5 | Stadium organ rising 'charge'-style build (original) |
| Organ_Riff_01 | 5.47 | 2 |  | -1.0 | -13.0 | Short arena-organ stinger (original) |
| Organ_Riff_02 | 4.99 | 2 |  | -1.0 | -13.5 | Short arena-organ stinger (original) |
| Organ_Riff_03 | 5.39 | 2 |  | -1.0 | -13.3 | Short arena-organ stinger (original) |
| Organ_Riff_04 | 4.90 | 2 |  | -1.0 | -13.1 | Short arena-organ stinger (original) |
| Organ_Clap | 13.81 | 2 |  | -1.0 | -14.2 | Organ call + crowd clap answers |

### Music (`/Game/IceRiot/Audio/Music/`, SC_Music)

| Asset | Dur (s) | Ch | Loop | Peak dBFS | LUFS | Notes |
|---|---:|---:|:---:|---:|---:|---|
| Music_Title | 60.00 | 2 | yes | -1.3 | -14.0 | Title: 144 BPM driving E-minor rock riff + synth lead, 36 bars, seamless loop |
| Music_Menu | 45.00 | 2 | yes | -1.3 | -14.0 | Menus: 128 BPM A-dorian funk-rock groove, 24 bars, seamless loop |
| Music_Intermission | 45.00 | 2 | yes | -1.3 | -14.0 | Intermission: 96 BPM D-minor big-beat + stadium organ, 18 bars, seamless loop |
| Music_Victory | 8.00 | 2 |  | -1.3 | -13.0 | Victory sting: E-major fanfare, 8 s |
| Music_Overtime | 20.00 | 2 | yes | -1.3 | -14.0 | Overtime: 144 BPM C-minor tense loop, 12 bars (20 s) |

### UI (`/Game/IceRiot/Audio/UI/`, SC_UI)

| Asset | Dur (s) | Ch | Loop | Peak dBFS | LUFS | Notes |
|---|---:|---:|:---:|---:|---:|---|
| UI_Move | 0.09 | 1 |  | -1.0 | -20.1 | Menu cursor move |
| UI_Select | 0.40 | 1 |  | -1.0 | -13.4 | Menu select / confirm |
| UI_Back | 0.19 | 1 |  | -1.0 | -17.0 | Menu back / cancel |
| UI_Start | 2.18 | 2 |  | -1.0 | -9.4 | Big press-start hit (stereo) |
| UI_Join | 0.66 | 1 |  | -1.0 | -15.8 | Player joined |
| UI_Error | 0.29 | 1 |  | -1.0 | -12.1 | Error / not allowed |
| UI_Tick | 0.12 | 1 |  | -1.0 | -21.7 | Countdown tick |
| UI_Whoosh | 0.54 | 1 |  | -1.0 | -13.4 | Banner swipe whoosh |
| UI_Impact | 2.40 | 2 |  | -1.0 | -14.4 | Logo slam (stereo) |

### Announcer (`/Game/IceRiot/Audio/Announcer/`, SC_Announcer)

| Asset | Dur (s) | Ch | Loop | Peak dBFS | LUFS | Notes |
|---|---:|---:|:---:|---:|---:|---|
| VO_Welcome | 2.06 | 1 |  | -1.7 | -14.0 | "Welcome to Ice Riot!" |
| VO_Title | 1.59 | 1 |  | -1.0 | -14.0 | "Ice Riot!" |
| VO_Team_NAR | 2.12 | 1 |  | -2.5 | -14.0 | "Northport Narwhals!" |
| VO_Team_INF | 2.19 | 1 |  | -3.1 | -14.0 | "Brimstone Inferno!" |
| VO_Team_YET | 2.13 | 1 |  | -2.5 | -14.0 | "Glacier Bay Yetis!" |
| VO_Team_HAM | 2.06 | 1 |  | -2.9 | -14.0 | "Steel Valley Hammers!" |
| VO_Team_BRW | 1.78 | 1 |  | -1.8 | -14.0 | "Bayou Brawlers!" |
| VO_Team_VIP | 2.10 | 1 |  | -2.5 | -14.0 | "Neon Coast Vipers!" |
| VO_Team_GRZ | 2.11 | 1 |  | -1.5 | -14.0 | "Timber Ridge Grizzlies!" |
| VO_Team_COM | 1.98 | 1 |  | -2.7 | -14.0 | "Rocket City Comets!" |
| VO_Goal_01 | 2.40 | 1 |  | -3.4 | -14.0 | "He shoots, he scores!" |
| VO_Goal_02 | 1.37 | 1 |  | -1.0 | -15.1 | "Goal!" |
| VO_Goal_03 | 1.75 | 1 |  | -1.5 | -14.0 | "Lights the lamp!" |
| VO_Goal_04 | 3.23 | 1 |  | -1.5 | -14.0 | "Top shelf, where mama hides the cookies!" |
| VO_Goal_05 | 1.68 | 1 |  | -1.0 | -14.2 | "Bar down!" |
| VO_Goal_06 | 1.73 | 1 |  | -1.0 | -14.0 | "Five hole!" |
| VO_Goal_07 | 1.70 | 1 |  | -1.9 | -14.0 | "Picks the corner!" |
| VO_Goal_08 | 1.52 | 1 |  | -2.7 | -14.0 | "What a snipe!" |
| VO_Goal_09 | 2.02 | 1 |  | -2.1 | -14.0 | "Ripples the twine!" |
| VO_Goal_10 | 2.26 | 1 |  | -1.4 | -14.0 | "Goal! Goal! GOAL!" |
| VO_PowerGoal_01 | 1.79 | 1 |  | -2.3 | -14.0 | "The net is on fire!" |
| VO_PowerGoal_02 | 1.46 | 1 |  | -3.1 | -14.0 | "Scorched!" |
| VO_PowerGoal_03 | 1.74 | 1 |  | -1.0 | -14.0 | "Burned him!" |
| VO_Save_01 | 1.66 | 1 |  | -2.9 | -14.0 | "What a save!" |
| VO_Save_02 | 1.83 | 1 |  | -2.1 | -14.0 | "Stoned him!" |
| VO_Save_03 | 1.41 | 1 |  | -1.0 | -14.5 | "Robbed!" |
| VO_Save_04 | 1.88 | 1 |  | -1.8 | -14.0 | "Big glove save!" |
| VO_Save_05 | 2.36 | 1 |  | -1.0 | -14.0 | "Kick save, and a beauty!" |
| VO_Save_06 | 1.48 | 1 |  | -1.0 | -14.1 | "Denied!" |
| VO_PowerSave | 1.68 | 1 |  | -1.0 | -14.1 | "Brick wall!" |
| VO_Post_01 | 1.57 | 1 |  | -1.6 | -14.0 | "Off the post!" |
| VO_Post_02 | 2.03 | 1 |  | -1.0 | -14.8 | "Ding! Iron!" |
| VO_Hit_01 | 1.49 | 1 |  | -1.0 | -14.0 | "Big hit!" |
| VO_Hit_02 | 1.76 | 1 |  | -1.3 | -14.0 | "Crushed him!" |
| VO_Hit_03 | 1.72 | 1 |  | -1.0 | -14.0 | "Into the boards!" |
| VO_Hit_04 | 2.33 | 1 |  | -1.0 | -14.2 | "Ooh, he felt that one!" |
| VO_Hit_05 | 1.53 | 1 |  | -1.7 | -14.0 | "Lights out!" |
| VO_PowerHit_01 | 2.33 | 1 |  | -1.3 | -14.0 | "Somebody call an ambulance!" |
| VO_PowerHit_02 | 2.35 | 1 |  | -2.2 | -14.0 | "He's gonna feel that tomorrow!" |
| VO_Fight_01 | 1.75 | 1 |  | -3.0 | -14.0 | "The gloves are off!" |
| VO_Fight_02 | 2.00 | 1 |  | -1.0 | -14.0 | "They're dropping the gloves!" |
| VO_Fight_03 | 2.28 | 1 |  | -2.8 | -14.0 | "Fight! Fight! Fight!" |
| VO_FightWin | 1.83 | 1 |  | -2.2 | -14.0 | "And he wins the fight!" |
| VO_HatTrick | 1.50 | 1 |  | -1.0 | -14.5 | "Hat trick!" |
| VO_Blazing | 1.75 | 1 |  | -1.0 | -14.1 | "He's blazing!" |
| VO_OneTimer | 1.61 | 1 |  | -1.0 | -14.0 | "One timer!" |
| VO_Slapshot | 1.57 | 1 |  | -2.9 | -14.0 | "Slapshot!" |
| VO_Breakaway | 1.70 | 1 |  | -1.5 | -14.0 | "Breakaway!" |
| VO_Rebound | 1.66 | 1 |  | -1.0 | -14.5 | "Rebound!" |
| VO_Steal_01 | 1.52 | 1 |  | -1.0 | -14.0 | "Stolen!" |
| VO_Steal_02 | 1.81 | 1 |  | -2.3 | -14.0 | "Picks his pocket!" |
| VO_Deke | 1.25 | 1 |  | -1.8 | -14.0 | "Deke!" |
| VO_Faceoff | 1.66 | 1 |  | -1.0 | -14.0 | "Here's the drop!" |
| VO_Period1 | 1.87 | 1 |  | -3.3 | -14.0 | "First period!" |
| VO_Period2 | 1.89 | 1 |  | -1.0 | -14.0 | "Second period!" |
| VO_Period3 | 1.79 | 1 |  | -2.2 | -14.0 | "Third period!" |
| VO_Overtime | 2.55 | 1 |  | -1.1 | -14.0 | "Overtime! Sudden death!" |
| VO_EndPeriod | 2.15 | 1 |  | -1.9 | -14.0 | "That's the end of the period!" |
| VO_FinalBuzzer | 1.85 | 1 |  | -1.7 | -14.0 | "That's the game!" |
| VO_Wins | 1.38 | 1 |  | -1.8 | -14.0 | "wins it!" |
| VO_TwoMinutes | 1.79 | 1 |  | -2.4 | -14.0 | "Two minutes left!" |
| VO_LastMinute | 2.11 | 1 |  | -1.0 | -14.0 | "Last minute of play!" |
| VO_Comeback | 1.79 | 1 |  | -1.0 | -14.1 | "They're coming back!" |
| VO_Shutout | 1.53 | 1 |  | -1.0 | -14.2 | "A shutout!" |
| VO_Icing | 1.50 | 1 |  | -1.0 | -14.0 | "Icing." |
| VO_Offsides | 1.61 | 1 |  | -1.6 | -14.0 | "Offside." |
| VO_Penalty | 1.57 | 1 |  | -1.0 | -14.0 | "Penalty!" |
| VO_PowerPlay | 1.69 | 1 |  | -1.0 | -14.0 | "Power play!" |

Plus `/Game/IceRiot/Audio/Classes/`: `SC_Master`, `SC_Music`, `SC_SFX`, `SC_Crowd`, `SC_Announcer`, `SC_UI`,
`SM_Default`, `SM_AnnouncerDuck` (181 `.uasset` files in `Content/IceRiot/Audio/` in total).
