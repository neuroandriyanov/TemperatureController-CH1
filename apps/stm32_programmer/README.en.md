[Русский](README.md) | **English**

# Bench · STM32 programming

Start from the project root: `python run.py programmer`. The application targets STM32F030C8 with 64 KB Flash through the standard UART ROM bootloader. It uses an original Python AN3155 client; ST FlashLoader is neither required nor included.

It opens BIN and Intel HEX, displays addresses and contents, and checks vectors and memory ranges. Select the port manually. The current `firmware/build/controller.bin` output is proposed by default if present. If it has not been built yet, open it after building or select your own compatible image.

Operations: device identification, backup read, erase, write with verification, comparison with a file, a full “erase → write → verify” cycle and application startup. A backup is saved before erase/full-cycle operations. An incorrect chip ID blocks erase. Results and backups are in `captures`; if backup saving fails, erase does not continue. Cancellation occurs between packets and does not guarantee intact firmware after an interrupted write.

CLI uses the same checks:

```text
python app.py --ports
python app.py --operation probe --port PORT
python app.py --operation flash --port PORT --firmware ../../firmware/build/controller.bin
```

Replace `PORT` with your programming UART port. Commands without a port fail; there are no preset COM numbers. BOOT0/RESET are switched on the board. Full procedure: [QUICKSTART](../../docs/QUICKSTART.en.md).

For CLI examples from this directory, use `python ../../env.py` instead of `python` to run in the environment installed by the common setup.py.
