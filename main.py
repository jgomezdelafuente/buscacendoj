#!/usr/bin/env python3
import subprocess
import sys
import argparse


def run_script(command: list[str]) -> int:
    try:
        process = subprocess.Popen(command)
        process.wait()

        if process.returncode != 0:
            print(f"[ERROR] Falló: {' '.join(command)}")
            return process.returncode

        return 0

    except Exception as e:
        print(f"[ERROR] Excepción ejecutando {' '.join(command)}: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline CENDOJ + Clasificador IA")

    parser.add_argument("query", help="Texto de búsqueda (ej: 'falso autonomo glovo')")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--max-docs", type=int, default=5)
    parser.add_argument("--pause", type=float, default=3.0)
    parser.add_argument("--headless", action="store_true")

    args = parser.parse_args()

    print("[INFO] Ejecutando scraper...")

    scraper_cmd = [
        sys.executable,
        "cendoj_scraper.py",
        args.query,
        "--max-pages", str(args.max_pages),
        "--max-docs", str(args.max_docs),
        "--pause", str(args.pause)
    ]

    if args.headless:
        scraper_cmd.append("--headless")

    result = run_script(scraper_cmd)
    if result != 0:
        print("[ERROR] Falló el scraper")
        return result

    print("[INFO] Ejecutando clasificador...")

    classifier_cmd = [
        sys.executable,
        "clasificar_falso_autonomo.py"
    ]

    result = run_script(classifier_cmd)
    if result != 0:
        print("[ERROR] Falló el clasificador")
        return result

    print("[OK] Pipeline completado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())