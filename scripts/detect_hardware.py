#!/usr/bin/env python3
"""
TBC-AI — Fase 1: Detector de hardware
Detecta las características del equipo y recomienda el modelo de Ollama óptimo.
No requiere dependencias externas (solo librería estándar de Python).
"""

import platform
import subprocess
import shutil
import sys
import os


def get_ram_gb():
    try:
        system = platform.system()
        if system == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode().strip()
            return round(int(out) / (1024 ** 3), 1)
        elif system == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        kb = int(line.split()[1])
                        return round(kb / (1024 ** 2), 1)
        elif system == "Windows":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return round(stat.ullTotalPhys / (1024 ** 3), 1)
    except Exception as e:
        return f"No detectado ({e})"
    return "No detectado"


def get_gpu_info():
    system = platform.system()
    info = []
    try:
        if system == "Darwin":
            out = subprocess.check_output(["system_profiler", "SPDisplaysDataType"]).decode()
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("Chipset Model") or "Metal" in line:
                    info.append(line)
        elif system == "Linux":
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]
                ).decode().strip()
                if out:
                    info.append(f"NVIDIA: {out}")
            except (subprocess.CalledProcessError, FileNotFoundError):
                try:
                    out = subprocess.check_output(["lspci"]).decode()
                    for line in out.splitlines():
                        if "VGA" in line or "3D" in line:
                            info.append(line.strip())
                except Exception:
                    pass
        elif system == "Windows":
            out = subprocess.check_output(
                ["wmic", "path", "win32_VideoController", "get", "name"]
            ).decode()
            for line in out.splitlines():
                line = line.strip()
                if line and line != "Name":
                    info.append(line)
    except Exception as e:
        info.append(f"No detectado ({e})")
    return info if info else ["No detectado"]


def get_disk_free_gb():
    _, _, free = shutil.disk_usage(os.path.expanduser("~"))
    return round(free / (1024 ** 3), 1)


def get_version(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        return out.splitlines()[0]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "No instalado"


def is_apple_silicon():
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def recommend_model(ram_gb):
    """Recomendación conservadora: reserva 4-6 GB para SO y resto de la app."""
    if isinstance(ram_gb, str):
        return "No se puede recomendar: RAM no detectada."
    if ram_gb >= 32:
        return ("Qwen2.5:14b o Llama3.1:8b (calidad alta). "
                "Con GPU dedicada >=12GB VRAM, también viable Qwen2.5:32b cuantizado.")
    elif ram_gb >= 16:
        return "Llama3.1:8b o Qwen2.5:7b (equilibrio calidad/velocidad, recomendado por defecto)."
    elif ram_gb >= 8:
        return "Phi3.5:mini o Qwen2.5:3b (RAM limitada, priorizar velocidad sobre calidad)."
    else:
        return "RAM insuficiente (<8GB) para un LLM local con calidad aceptable."


def main():
    print("=" * 60)
    print("TBC-AI — Detector de hardware (Fase 1)")
    print("=" * 60)

    system = platform.system()
    machine = platform.machine()
    processor = platform.processor() or machine
    ram_gb = get_ram_gb()
    gpu_info = get_gpu_info()
    disk_free = get_disk_free_gb()
    python_version = sys.version.split()[0]
    git_version = get_version(["git", "--version"])
    ollama_version = get_version(["ollama", "--version"])
    apple_silicon = is_apple_silicon()

    print(f"\nSistema operativo    : {system} {platform.release()}")
    print(f"Arquitectura         : {machine}")
    print(f"Procesador           : {processor}")
    print(f"Apple Silicon        : {'Sí' if apple_silicon else 'No'}")
    print(f"RAM total            : {ram_gb} GB")
    print(f"GPU detectada        : {', '.join(gpu_info)}")
    print(f"Almacenamiento libre : {disk_free} GB")
    print(f"Python               : {python_version}")
    print(f"Git                  : {git_version}")
    print(f"Ollama               : {ollama_version}")

    print("\n" + "-" * 60)
    print("RECOMENDACIÓN DE MODELO")
    print("-" * 60)
    print(recommend_model(ram_gb))

    if isinstance(disk_free, float) and disk_free < 20:
        print("\nAVISO: menos de 20 GB libres. Modelo + índice vectorial "
              "pueden ocupar entre 5 y 15 GB según el modelo elegido.")

    if ollama_version == "No instalado":
        print("\nAVISO: Ollama no está instalado. Necesario antes de la Fase 2.")
        print("  macOS/Linux: curl -fsSL https://ollama.com/install.sh | sh")
        print("  Windows: descargar instalador desde https://ollama.com/download")

    if git_version == "No instalado":
        print("\nAVISO: Git no está instalado, necesario para versionar el proyecto.")

    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hardware_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Sistema operativo: {system} {platform.release()}\n")
        f.write(f"Arquitectura: {machine}\n")
        f.write(f"Procesador: {processor}\n")
        f.write(f"Apple Silicon: {apple_silicon}\n")
        f.write(f"RAM total (GB): {ram_gb}\n")
        f.write(f"GPU: {', '.join(gpu_info)}\n")
        f.write(f"Disco libre (GB): {disk_free}\n")
        f.write(f"Python: {python_version}\n")
        f.write(f"Git: {git_version}\n")
        f.write(f"Ollama: {ollama_version}\n")
        f.write(f"Recomendación: {recommend_model(ram_gb)}\n")

    print(f"\nInforme guardado en: {report_path}")


if __name__ == "__main__":
    main()
