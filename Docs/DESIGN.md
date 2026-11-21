# ICE RIOT — Game Design

ICE RIOT is an original, over-the-top arcade hockey game in the spirit of the mid-90s 3D arcade hockey
cabinets and their Nintendo 64 ports (fast 3-on-3, turbo, flaming power shots, bone-rattling power checks,
fights). All teams, players, logos, arenas, music and announcer lines are original. No real league, team,
player or existing game is referenced anywhere in the game, art or audio.

## Research notes (how the inspiration actually played)

From the N64 instruction manual (Midway, 1996) and contemporary reviews:

- **Arcade mode**: 3 skaters + goalie per side, smaller "arcade" rink, *no rules, no penalties*.
  Simulation mode adds 3/4/5-man teams, offsides, icing and minor penalties.
- Period length 1:30 / 2:00 / 2:30 / 3:00 in Arcade mode, 3 periods, sudden-death overtime.
- **Offense**: Shoot (tap = wrist shot, hold + release = slap shot), Pass (directional), Turbo,
  **One-timer** (Shoot + Pass: shoot the moment the pass arrives), **Power shot** (Shoot + Turbo: the net
  catches fire / the goalie is knocked into the net). Pressing Pass while a CPU teammate has the puck
  calls for it; Shoot tells him to shoot.
- **Defense**: Check, Steal (poke), Hook, Trip, Dive, Switch player, Turbo. A **power check** sends a player
  flying (an ambulance crossed the top of the screen).
- **Goalies** are CPU controlled; "power saves" turn the goalie into a brick wall for a moment.
- **Turbo** shown in the colored ring under each human's feet (white = available) and recharges on its own.
- Player ID rings: one color per human, CPU teammates get a neutral ring.
- **Fighting**: every skater has an *anger meter* that rises when he gets hit; when it boils over the
  play stops, the two drop the gloves (jab, hard punch, grab, uppercut). The loser is replaced.
- Face-offs: the ref drops the puck, press a direction + button at the drop to win it.
- 7 camera angles, instant replay, practice modes (offense, shooting), season/playoff modes,
  5 difficulty levels, secret super teams and big-head codes.
- Critics: four-player multiplayer was the selling point; single-player AI was weak, the
  commentary repetitive. **We fix both**: smarter, difficulty-scaled AI and a big pool of announcer lines.

## Core rules (ICE RIOT)

- Default **3-on-3 + CPU goalies**, team size option 3 / 4 (4v4 is used automatically for 7–8 humans).
- 3 periods, length 1:30 / 2:00 / 2:30 / 3:00 (default 2:00), sudden-death overtime.
- **Arcade rules** (default): no offsides, no icing, no penalties. **Pro rules**: icing + offsides
  (face-off in the offending zone) and hooking/tripping penalties (penalty box, power play).
- Puck out of play (over the glass) → face-off at the nearest dot. Goalie freeze > 2 s → face-off.
- Up to **8 local players**: 2 on the keyboard + up to 8 gamepads (any mix up to 8).

## Controls

| Action | Gamepad | Keyboard P1 | Keyboard P2 |
|---|---|---|---|
| Skate | Left stick / D-pad | W A S D | Arrow keys |
| Shoot (tap wrist, hold slap) / Check on D | A / Cross | J or Space | Numpad 1 / , |
| Pass / Steal (poke) on D | X / Square | K | Numpad 2 / . |
| Turbo | RT / R1 (also LT) | L or Left Shift | Numpad 3 / / or Right Shift |
| Switch player (D) / Deke spin (O) | B / Circle | I | Numpad 4 / ; |
| Hook (D) / Drop pass (O) | Y / Triangle | U | Numpad 5 / ' |
| Pause | Start | Esc / P | |

Combos: **Shoot + Turbo** = power shot (needs ½ turbo); **Shoot + Pass** = one-timer pass/shot;
**Turbo + Check** = power check; **Turbo + Steal** = dive/poke lunge; **Hook + Turbo** = trip.
In a fight: Shoot = hard punch, Pass = jab, Hook = grab, Turbo + Shoot = uppercut, Switch = block.

## Signature arcade systems

- **Turbo**: +45 % top speed, sharper turns, harder checks. Drains while held, recharges after 0.6 s.
- **Power shot**: flaming puck with a streak; on a goal the net bursts into flames, the goalie can be
  knocked back into the net. Costs 50 % turbo.
- **Power check**: victim is launched (ragdoll-ish arc), can fly into/over the boards, stick and
  helmet pop off; an ambulance gag crosses the top of the screen. Big screen shake + glass rattle.
- **Anger meter** → **fights** (toggle): health bars, four attacks, block; the loser is knocked out
  and sits for the rest of the play (replaced by a fresh skater) and the winner's team gets a full turbo
  refill + *RAGE* (power shots free for 15 s).
- **Hat trick**: a player's third goal makes hats rain onto the ice; he goes **BLAZING** (fire trail,
  better shots) until the opponents score twice.
- **Goalie power save**: a goalie that's been peppered glows and stones the next shot.
- **Goal celebration**: horn, goal light, camera on the scorer, then an instant replay of the goal from a
  cinematic angle (skippable).
- **Comeback catch-up** (difficulty-scaled, can be disabled).
- Cheats on the title/option screens (big heads, tiny players, super teams, fight frenzy).

## Modes

- **Exhibition**: 1–8 humans, any teams, any side.
- **Tournament**: arcade ladder — beat every team (loss = replay the same team).
- **Practice**: Shooting (you vs goalie), Free Skate.
- **Attract mode**: CPU vs CPU behind the title screen.

## Cameras (cycle in-game with the Camera key / Back button)

Broadcast (side, default), High Broadcast, Overhead, End-Zone Chase, Close Action, Blimp.
