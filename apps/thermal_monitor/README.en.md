[Русский](README.md) | **English**

# Bench · video and thermal monitoring

Start with `python run.py thermal` from the project root. Two independent DirectShow sources: a color camera/HDMI capture card and UTi260B. The program targets Windows; dependencies are listed in `requirements.txt`.

Color video has adjustable glare reduction and sharpening. These settings do not create radiometric data. The thermal image can rotate by 0/90/180/270°. Alignment opens a transparent layer: four corners control perspective, and the center handle controls rotation; the result is saved locally. Realign after changing the mounting.

A crosshair shows approximate temperature from the UTi260B palette and recognized scale. A saved marker is projected onto the color image. The save button creates a color frame with markers, a thermogram and JSON in `output/bench_monitor`. Original on-screen readings differ from an estimate at an arbitrary point.

## Automation control

Startup creates a local API on 127.0.0.1, using an available port in 18765…18774 and a random token. `control.py` reads `.runtime/api.json` itself; do not publish that file. Examples from the application directory:

```text
python control.py state
python control.py devices
python control.py temperature 0.45 0.58
python control.py mark 0.45 0.58 --name A
python control.py save
python control.py frame thermal thermal.png --raw
```

Full interface: [API.en.txt](API.en.txt). Select devices and modes from the actual discovered list. Settings from somebody else's PC are not supplied.

## Measurement limitations

This decodes a video output; it is not a radiometric SDK. The `≈` sign is essential: accuracy depends on palette, scale, emissivity, reflections, display and geometry. An unknown palette, unreadable OSD or menu makes temperature unavailable. The menu heuristic sometimes triggers incorrectly on dark areas of an ordinary scene; such gaps were preserved in the experiment, and selected frames were analyzed separately. A complete fix requires test frames of real menus and ordinary scenes; this publication does not claim that fix is complete.

A capture card may keep delivering “NOT SUPPORT” frames after an external camera overheats: receiving a frame does not establish that the optical camera is working. Images are visually checked before publication. For analysis, use the [methodology](../../measurements/README.en.md).

For CLI examples from this directory, use `python ../../env.py` instead of `python` to run in the environment installed by the common setup.py.
