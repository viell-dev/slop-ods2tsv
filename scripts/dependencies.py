"""Inspect release imports and run with development runtime directories absent from PATH."""
import argparse
import os
from pathlib import Path
import re
import subprocess

from validation import require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    if os.name == "nt":
        vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
        root = Path(subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-requires",
                    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True).strip())
        candidates = list(root.glob("VC/Tools/MSVC/*/bin/Hostx64/x64/dumpbin.exe"))
        require(candidates, "dumpbin is required for Windows release inspection")
        output = subprocess.check_output([str(sorted(candidates)[-1]), "/dependents", str(binary)], text=True)
        imports = {name.lower() for name in re.findall(r'(?im)^\s*([a-z0-9_.-]+\.dll)\s*$', output)}
        require(imports, "no import table found")
        os_dlls = {"advapi32.dll", "bcrypt.dll", "bcryptprimitives.dll", "crypt32.dll", "dbghelp.dll", "iphlpapi.dll", "kernel32.dll",
                   "kernelbase.dll", "ntdll.dll", "ole32.dll", "psapi.dll", "secur32.dll", "shell32.dll",
                   "user32.dll", "userenv.dll", "version.dll", "ws2_32.dll"}
        unexpected = {name for name in imports if name not in os_dlls and not name.startswith(("api-ms-win-core-", "ext-ms-win-"))}
        require(not unexpected, f"Unreviewed runtime dependencies: {sorted(unexpected)}")
        env = os.environ.copy()
        env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        for name in ("PYTHONHOME", "PYTHONPATH", "RUSTUP_HOME", "CARGO_HOME", "DOTNET_ROOT"):
            env.pop(name, None)
        subprocess.run([str(binary), "--version"], env=env, check=True)
        print("Verified OS-only Windows imports:", ", ".join(sorted(imports)))
    else:
        output = subprocess.check_output(["readelf", "-l", str(binary)], text=True)
        require("INTERP" not in output, "Linux binary has a dynamic ELF interpreter")
        dynamic = subprocess.check_output(["readelf", "-d", str(binary)], text=True)
        require("NEEDED" not in dynamic, "Linux binary has shared-library requirements")
        print("Verified Linux executable has no ELF interpreter or shared-library requirements.")


if __name__ == "__main__":
    main()
