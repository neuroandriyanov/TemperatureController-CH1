"""Build firmware with Arm GNU Toolchain; Python 3.9+, no Python dependencies."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build"

def toolchain():
    suffix = ".exe" if os.name == "nt" else ""
    configured = os.environ.get("ARM_GCC_DIR")
    if configured:
        return Path(configured) / ("arm-none-eabi-gcc" + suffix)
    found = shutil.which("arm-none-eabi-gcc")
    if found:
        return Path(found)
    if os.name == "nt":
        found = sorted(Path("C:/ST").glob("STM32CubeIDE_*/STM32CubeIDE/plugins/*gnu-tools*/tools/bin/arm-none-eabi-gcc.exe"))
        if found:
            return found[-1]
    raise SystemExit("Install Arm GNU Toolchain or set ARM_GCC_DIR to its bin directory")

def main():
    gcc = toolchain()
    OUT.mkdir(exist_ok=True)
    sources = sorted((ROOT / "app").glob("*.c")) + sorted((ROOT / "Core/Src").glob("*.c"))
    sources += sorted((ROOT / "Drivers/STM32F0xx_HAL_Driver/Src").glob("*.c"))
    sources += sorted((ROOT / "Core/Startup").glob("*.s"))
    common = ["-mcpu=cortex-m0", "-mthumb", "-mfloat-abi=soft", "--specs=nano.specs"]
    includes = ["app", "Core/Inc", "Drivers/STM32F0xx_HAL_Driver/Inc", "Drivers/STM32F0xx_HAL_Driver/Inc/Legacy",
                "Drivers/CMSIS/Include", "Drivers/CMSIS/Device/ST/STM32F0xx/Include"]

    def compile_one(src):
        obj = OUT / (src.stem + ".o")
        flags = ["-x", "assembler-with-cpp"] if src.suffix == ".s" else [
            "-std=c11", "-Os", "-ffunction-sections", "-fdata-sections", "-fstack-usage",
            "-Wall", "-Wextra", "-DUSE_HAL_DRIVER", "-DSTM32F030x8",
            *["-I" + p for p in includes]]
        if src.suffix == ".c" and "Drivers" not in src.relative_to(ROOT).parts:
            flags += ["-Werror"]
        result = subprocess.run([str(gcc), *common, *flags, "-c", str(src.relative_to(ROOT)), "-o", str(obj.relative_to(ROOT))],
                                cwd=ROOT, capture_output=True, text=True)
        return obj, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(compile_one, sources))
    log = "".join(r.stdout + r.stderr for _, r in results)
    if any(r.returncode for _, r in results):
        (OUT / "build.log").write_text(log, encoding="utf-8")
        raise SystemExit(log)
    result = subprocess.run([str(gcc), *common, "--specs=nosys.specs", "-TSTM32F030C8TX_FLASH.ld",
        "-Wl,--gc-sections", "-Wl,--fatal-warnings", "-Wl,-Map=build/controller.map", "-o", "build/controller.elf",
        *[str(p.relative_to(ROOT)) for p, _ in results], "-Wl,--start-group", "-lc", "-lm", "-Wl,--end-group"],
        cwd=ROOT, capture_output=True, text=True)
    log += result.stdout + result.stderr
    (OUT / "build.log").write_text(log, encoding="utf-8")
    if result.returncode:
        raise SystemExit(log)
    suffix = gcc.suffix
    for fmt, ext in [("binary", "bin"), ("ihex", "hex")]:
        subprocess.run([str(gcc.with_name("arm-none-eabi-objcopy" + suffix)), "-O", fmt,
                        "build/controller.elf", "build/controller." + ext], cwd=ROOT, check=True)
    size = subprocess.check_output([str(gcc.with_name("arm-none-eabi-size" + suffix)), "build/controller.elf"], cwd=ROOT, text=True)
    print(log + size)
    image = (OUT / "controller.bin").read_bytes()
    if not 8 <= len(image) <= 65536:
        raise SystemExit("Invalid flash image length")
    sp, reset = (int.from_bytes(image[i:i+4], "little") for i in (0,4))
    if sp != 0x20002000 or not 0x08000000 <= (reset & ~1) < 0x08010000 or not reset & 1:
        raise SystemExit("Invalid initial stack or reset vector")
    version = subprocess.check_output([str(gcc), "--version"], text=True).splitlines()[0]
    manifest = {"version": "2.5.0", "protocol": "2.4", "mcu": "STM32F030C8T6", "address": "0x08000000",
                "compiler": version, "size": size.splitlines()[-1], "hardware_tested": False,
                "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob("controller.*") if p.suffix in (".bin", ".hex", ".elf")}}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Build complete; device was not programmed.")

if __name__ == "__main__":
    main()
