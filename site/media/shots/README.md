# Game screenshots

Drop real in-game captures here. The gallery on the home page loads these exact filenames and
falls back to the Blender renders in `media/renders/` (labelled "Blender render") for any file
that is missing.

| File | What to capture |
|---|---|
| `shot_title.jpg` | Title screen with the logo (attract mode running behind it) |
| `shot_faceoff.jpg` | Opening face-off at center ice, broadcast camera |
| `shot_powershot.jpg` | A flaming power shot in flight (fire streak visible) |
| `shot_goal.jpg` | Goal: net on fire / goal light / celebration |
| `shot_fight.jpg` | A fight with both health bars on screen |
| `shot_replay.jpg` | Instant replay from a cinematic angle |
| `shot_teamselect.jpg` | Team select screen with the crests |
| `shot_join.jpg` | Join screen with several controllers picking sides |

Guidelines: 16:9, 1600×900 (or 1920×1080), JPEG quality ~82, ideally under 300 KB each
(`sips -Z 1600 -s format jpeg -s formatOptions 82 in.png --out shot_x.jpg`).
The first one (`shot_title.jpg`) is shown largest.

Optional: `../trailer.mp4` (H.264, 1080p, ideally under 40 MB). The trailer section on the
home page stays hidden until that file exists.
