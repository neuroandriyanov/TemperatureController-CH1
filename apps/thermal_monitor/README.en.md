# Bench · video and thermal imaging

[Русский](README.md) | **English**

Launch: `python run.py thermal` from the root. Two independent DirectShow sources: a color camera/HDMI capture card and UTi260B. The application targets Windows; dependencies are in `requirements.txt`.

Color video has adjustable glare reduction and sharpening. These settings do not create radiometric data. The thermal image rotates by 0/90/180/270°. Alignment opens a translucent layer: four corners change perspective and the center handle controls rotation; the result is saved locally. Realign after changing the mounting.

The crosshair shows an approximate temperature derived from the UTi260B palette and recognized scale. A saved point is projected onto the color image. The save button creates a color frame with markers, a thermogram and JSON under `output/bench_monitor`. Original on-screen readings differ from estimates at arbitrary points.

## Automation control

Startup creates a local API on 127.0.0.1, using a free port from 18765…18774 and a random token. `control.py` reads `.runtime/api.json` automatically; do not publish that file. Examples from the application directory:

```text
python control.py state
python control.py devices
python control.py temperature 0.45 0.58
python control.py mark 0.45 0.58 --name A
python control.py save
python control.py frame thermal thermal.png --raw
```

Complete interface: [API.en.txt](API.en.txt). Choose devices/modes from the actual returned list. Settings saved on another PC are not supplied.

## Measurement boundaries

This decodes video output; it is not a radiometric SDK. The `≈` sign is mandatory: accuracy depends on the palette, scale, emissivity, reflections, screen and geometry. An unknown palette, unreadable OSD or menu means temperature is unavailable. The menu heuristic sometimes triggers falsely on dark regions of an ordinary scene; these gaps were retained in the experiment, with selected frames analyzed separately. A full correction needs test frames of real menus and ordinary scenes; this publication does not claim that correction is complete.

A capture card may continue returning “NOT SUPPORT” frames after an external camera overheats: receiving a frame does not establish that the optics work. Snapshots are visually reviewed before publication. To analyze material, use the [method](../../measurements/README.en.md).

For CLI examples from this directory, use `python ../../env.py` instead of `python` to run in the environment installed by the common setup.py.
