"""
ICE RIOT -- arena PA announcer: macOS `say` -> afconvert (48 kHz) -> numpy PA chain.

Voice choice (Nov 2026, this machine): every installed English voice was rendered with the same
test phrase and compared on pitch range, bandwidth and formants (no listening on speakers):
  * Siri neural voices ("Voice 6" en-US-G, "Voice 2"/Simone) are female-register (~230-310 Hz) and
    ignore pitch control (AVSpeechUtterance.pitchMultiplier and SSML prosody).
  * Aman (Premium, en-IN, neural) is clean but flat (~6 semitone range) and accented en-IN.
  * Daniel (en-GB) is the most expressive male voice installed (~15 semitone pitch range, full
    bandwidth, 125 Hz median), so it is the PA voice. Short calls are slowed down so they land with
    weight; the PA chain below adds the arena character.
Override with ICE_RIOT_VO_VOICE=<say voice name> (must be installed).
"""

import os
import subprocess

import numpy as np

from .dsp import (SR, N, read_wav, peak, trim_lead, trim_tail, normalize, iir, biquad, saturate, compressor,
                  limiter, pad_to, add_reverb, ir_cached, fade, loudness_lufs, dbamp)

VO_VOICE = os.environ.get("ICE_RIOT_VO_VOICE", "Daniel")


def vo_rate(text):
    words = len(text.replace("!", " ").replace(",", " ").split())
    return 172 if words <= 2 else (188 if words <= 4 else 200)


VO_LINES = [
    ("VO_Welcome", "Welcome to Ice Riot!"),
    ("VO_Title", "Ice Riot!"),
    ("VO_Team_NAR", "Northport Narwhals!"),
    ("VO_Team_INF", "Brimstone Inferno!"),
    ("VO_Team_YET", "Glacier Bay Yetis!"),
    ("VO_Team_HAM", "Steel Valley Hammers!"),
    ("VO_Team_BRW", "Bayou Brawlers!"),
    ("VO_Team_VIP", "Neon Coast Vipers!"),
    ("VO_Team_GRZ", "Timber Ridge Grizzlies!"),
    ("VO_Team_COM", "Rocket City Comets!"),
    ("VO_Goal_01", "He shoots, he scores!"),
    ("VO_Goal_02", "Goal!"),
    ("VO_Goal_03", "Lights the lamp!"),
    ("VO_Goal_04", "Top shelf, where mama hides the cookies!"),
    ("VO_Goal_05", "Bar down!"),
    ("VO_Goal_06", "Five hole!"),
    ("VO_Goal_07", "Picks the corner!"),
    ("VO_Goal_08", "What a snipe!"),
    ("VO_Goal_09", "Ripples the twine!"),
    ("VO_Goal_10", "Goal! | Goal! | GOAL!"),
    ("VO_PowerGoal_01", "The net is on fire!"),
    ("VO_PowerGoal_02", "Scorched!"),
    ("VO_PowerGoal_03", "Burned him!"),
    ("VO_Save_01", "What a save!"),
    ("VO_Save_02", "Stoned him!"),
    ("VO_Save_03", "Robbed!"),
    ("VO_Save_04", "Big glove save!"),
    ("VO_Save_05", "Kick save, and a beauty!"),
    ("VO_Save_06", "Denied!"),
    ("VO_PowerSave", "Brick wall!"),
    ("VO_Post_01", "Off the post!"),
    ("VO_Post_02", "Ding! Iron!"),
    ("VO_Hit_01", "Big hit!"),
    ("VO_Hit_02", "Crushed him!"),
    ("VO_Hit_03", "Into the boards!"),
    ("VO_Hit_04", "Ooh, he felt that one!"),
    ("VO_Hit_05", "Lights out!"),
    ("VO_PowerHit_01", "Somebody call an ambulance!"),
    ("VO_PowerHit_02", "He's gonna feel that tomorrow!"),
    ("VO_Fight_01", "The gloves are off!"),
    ("VO_Fight_02", "They're dropping the gloves!"),
    ("VO_Fight_03", "Fight! | Fight! | Fight!"),
    ("VO_FightWin", "And he wins the fight!"),
    ("VO_HatTrick", "Hat trick!"),
    ("VO_Blazing", "He's blazing!"),
    ("VO_OneTimer", "One timer!"),
    ("VO_Slapshot", "Slapshot!"),
    ("VO_Breakaway", "Breakaway!"),
    ("VO_Rebound", "Rebound!"),
    ("VO_Steal_01", "Stolen!"),
    ("VO_Steal_02", "Picks his pocket!"),
    ("VO_Deke", "Deke!"),
    ("VO_Faceoff", "Here's the drop!"),
    ("VO_Period1", "First period!"),
    ("VO_Period2", "Second period!"),
    ("VO_Period3", "Third period!"),
    ("VO_Overtime", "Overtime! Sudden death!"),
    ("VO_EndPeriod", "That's the end of the period!"),
    ("VO_FinalBuzzer", "That's the game!"),
    ("VO_Wins", "wins it!"),
    ("VO_TwoMinutes", "Two minutes left!"),
    ("VO_LastMinute", "Last minute of play!"),
    ("VO_Comeback", "They're coming back!"),
    ("VO_Shutout", "A shutout!"),
    ("VO_Icing", "Icing."),
    ("VO_Offsides", "Offside."),
    ("VO_Penalty", "Penalty!"),
    ("VO_PowerPlay", "Power play!"),
]


def say_render(text, rate, tmpdir, tag, voice=None):
    """Render one line with macOS `say`, convert to 48 kHz 16-bit WAV; returns float mono."""
    voice = voice or VO_VOICE
    aiff = os.path.join(tmpdir, tag + ".aiff")
    wav = os.path.join(tmpdir, tag + ".wav")
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", aiff, text], check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@48000", "--src-complexity", "bats", "-r", "127",
                    aiff, wav], check=True)
    x, sr = read_wav(wav)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if sr != SR or x.shape[0] < N(0.15) or peak(x) < 0.01:
        raise RuntimeError("say produced unusable audio for %r (sr=%s, n=%d)" % (text, sr, x.shape[0]))
    return x


def render_line(text, tmpdir, tag):
    """Render a line. Text with '|' is rendered as separate calls that escalate: each part is a
    little higher (tape-style resample) and the last one is slower and bigger."""
    from .dsp import resample
    parts = [p.strip() for p in text.split("|")]
    if len(parts) == 1:
        return say_render(text, vo_rate(text), tmpdir, tag)
    out = np.zeros(0)
    for k, p in enumerate(parts):
        last = k == len(parts) - 1
        x = say_render(p, 150 if last else 185, tmpdir, "%s_%d" % (tag, k))
        x = trim_tail(trim_lead(x, -40.0, preroll=0.005), -45.0)
        x = resample(x, 2.0 ** ((1.5 * k) / 12.0)) * (0.75 + 0.125 * k)
        gap = np.zeros(N(0.09))
        out = np.concatenate([out, gap, x]) if out.size else x
    return out


def vo_process(x):
    """Arena PA chain: trim -> HPF 110 Hz -> mud cut / presence / air EQ -> parallel saturation ->
    compression -> limiting -> two PA slap-backs (near + far stands) -> arena tail -> -1 dBFS."""
    x = trim_tail(trim_lead(x, -40.0, preroll=0.01), -50.0)
    x = normalize(x, -1.0)
    x = iir(x, biquad("hp", 110, 0.5412), biquad("hp", 110, 1.3066))             # 4th-order Butterworth
    x = iir(x, biquad("lowshelf", 180, 0.7, 2.0), biquad("peak", 350, 1.0, -3.0), biquad("peak", 2900, 0.9, 4.5),
            biquad("highshelf", 8500, 0.7, 2.0), biquad("lp", 11000, 0.7))
    x = saturate(normalize(x, -1.0), drive=2.6, mix=0.45)
    x = compressor(x, thresh_db=-24.0, ratio=4.5, attack=0.002, release=0.08, knee_db=6.0)
    x = limiter(normalize(x, 2.0), ceiling_db=-1.0, lookahead=0.002, release=0.05)
    band = iir(x, biquad("hp", 350, 0.7), biquad("lp", 3200, 0.7))
    y = pad_to(x, x.shape[0] + N(0.4))
    for d, g in ((0.075, 0.20), (0.165, 0.11), (0.29, 0.05)):
        k = N(d)
        y[k:k + band.shape[0]] += g * band
    ir = ir_cached("vo_arena", rt60=1.5, length=1.1, predelay=0.025, stereo=False)
    y = add_reverb(y, ir, wet=0.2)
    y = fade(trim_tail(y, -58.0), 0.002, 0.12)
    # consistent loudness across lines: -14 LUFS, -1 dBFS ceiling
    y = y * float(dbamp(-14.0 - loudness_lufs(y)))
    y = limiter(y, -1.0, 0.002, 0.05)
    return y
