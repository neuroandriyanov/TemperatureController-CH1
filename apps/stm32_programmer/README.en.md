# Bench · STM32 programming

[Русский](README.md) | **English**

Launch from the root: `python run.py programmer`. The application targets STM32F030C8 with 64 KB Flash through the built-in UART ROM bootloader. It uses a custom Python client for AN3155; ST FlashLoader installation is neither required nor included.

It opens BIN and Intel HEX, displays addresses and contents, and checks vectors and memory ranges. Select the port manually. By default it offers the current build output, `firmware/build/controller.bin`, if present. If it has not been built yet, open it after building or select your own compatible image.

Operations: device identification, backup read, erase, write with verification, comparison against a file, full “erase → write → verify” cycle, application start. A backup is saved before erase/full cycle. An incorrect chip ID blocks erasing. Results and backup go to `captures`; if backup saving fails, erasing does not proceed. Cancellation occurs between packets and does not guarantee intact firmware after an interrupted write.

The CLI uses the same checks:

```text
python app.py --ports
python app.py --operation probe --port PORT
python app.py --operation flash --port PORT --firmware ../../firmware/build/controller.bin
```

Replace `PORT` with your bootloader UART port. Commands without a port fail; there are no preset COM numbers. BOOT0/RESET are switched on the board. Complete procedure: [QUICKSTART](../../docs/QUICKSTART.en.md).

For CLI examples from this directory, use `python ../../env.py` instead of `python` to run in the environment installed by the common setup.py.
