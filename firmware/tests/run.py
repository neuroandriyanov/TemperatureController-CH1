"""Compile and run pure C tests with GCC/Clang or installed MSVC Build Tools."""
from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/tests"
OUT.mkdir(parents=True, exist_ok=True)
sources = [str(p) for p in sorted((ROOT / "app").glob("*.c"))] + [str(ROOT / "tests/test_core.c")]
cc = os.environ.get("CC") or shutil.which("gcc") or shutil.which("clang")
if cc:
    executable = OUT / ("test_core.exe" if os.name == "nt" else "test_core")
    flags = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-g", "-O1"]
    if os.environ.get("SANITIZE") == "1":
        flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    subprocess.run([cc, *flags, "-I" + str(ROOT / "app"), *sources, "-lm", "-o", str(executable)], check=True, cwd=OUT)
else:
    program_files = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    candidates = sorted((program_files / "Microsoft Visual Studio").glob("*/BuildTools/VC/Auxiliary/Build/vcvars64.bat"))
    if not candidates:
        raise SystemExit("Install GCC, Clang, or Visual Studio C++ Build Tools")
    env = os.environ.copy()
    env["PATH"] = os.path.join(env.get("SystemRoot", "C:/Windows"), "System32")
    text = subprocess.check_output('cmd.exe /d /s /c ""' + str(candidates[-1]) + '" >nul && set"', env=env, text=True)
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    executable = OUT / "test_core.exe"
    compiler = shutil.which("cl.exe", path=env.get("Path", env.get("PATH")))
    subprocess.run([compiler, "/nologo", "/std:c11", "/W4", "/WX", "/D_CRT_SECURE_NO_WARNINGS",
                    "/I" + str(ROOT / "app"), *sources, "/Fe:" + str(executable)], env=env, cwd=OUT, check=True)
subprocess.run([str(executable)], check=True, cwd=OUT)
