#!/usr/bin/env python3
from __future__ import annotations

import argparse #lee los parámetros que le pasas por consola
import csv
import re
import sys
import time
from pathlib import Path #gestiona carpetas y archivos
from typing import List, Optional, Set, Tuple
from urllib.parse import urljoin #convierte enlaces relativos en absolutos

from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

BASE_URL = "https://www.poderjudicial.es/search/indexAN.jsp"


def slugify(text: str, max_len: int = 120) -> str:
    #Transforma un título de sentencia en un nombre de archivo válido.
    #Entrada: STS, a 25 de marzo de 2026 - ROJ: STS 1369/2026
    #Salida: STS_a_25_de_marzo_de_2026_-_ROJ_STS_1369_2026
    text = re.sub(r"[^\w\s.-]", "_", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"_+", "_", text)
    return text[:max_len].strip("._") or "documento"


def safe_sleep(seconds: float) -> None:
    #Para meter pausas entre pasos
    #la web cargue,
    #Selenium no vaya demasiado rápido,
    #y el servidor no reciba acciones demasiado agresivas.
    time.sleep(max(seconds, 0.0))

#abrir Chrome preparado para descargar
def build_driver(headless: bool, download_dir: Path) -> webdriver.Chrome:
    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    #Configura tamaño de la venana, idioma
    options.add_argument("--window-size=1440,1600")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=es-ES")
    prefs = {
        "download.default_directory": str(download_dir.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
    }
    options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver

#Espera a que la página cargue
#Sin esto, el script intentaría hacer clic o leer enlaces demasiado pronto.
def wait_ready(driver: webdriver.Chrome, timeout: int = 25) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            if driver.execute_script("return document.readyState") == "complete":
                return
        except Exception:
            pass
        safe_sleep(0.3)
    raise RuntimeError("La página no terminó de cargar a tiempo.")

#cerrar avisos o capas molestas
def close_overlays(driver: webdriver.Chrome) -> None:
    xpaths = [
        "//button[contains(., 'Aceptar')]",
        "//button[contains(., 'ACEPTAR')]",
        "//a[contains(., 'Aceptar')]",
        "//button[contains(., 'Entendido')]",
        "//button[contains(., 'Cerrar')]",
        "//span[contains(., 'Cerrar')]",
    ]
    for xp in xpaths:
        for e in driver.find_elements(By.XPATH, xp):
            try:
                if e.is_displayed():
                    e.click()
                    safe_sleep(0.5)
            except Exception:
                pass


def page_text(driver: webdriver.Chrome) -> str:
    try:
        return (driver.find_element(By.TAG_NAME, "body").text or "").strip()
    except Exception:
        return ""

#detectar si la búsqueda ha fallado
def detect_search_error(driver: webdriver.Chrome) -> Optional[str]:
    txt = page_text(driver).lower()
    if "no se ha podido atender su petición" in txt:
        return "La web indica que no se ha enviado ningún criterio de búsqueda válido."
    if "no ha introducido ninguno de los campos requeridos" in txt:
        return "La web indica que el formulario llegó vacío."
    return None

#localizar el campo correcto de búsqueda
def find_main_search_input(driver: webdriver.Chrome):
    selectors = [
        "#frmBusquedajurisprudencia_TEXT", #es el campo correcto de “Búsqueda por texto libre”.
        "input[name='TEXT']",
        "input[placeholder*='texto libre']",
    ]
    for sel in selectors:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        for el in elems:
            try:
                if el.is_displayed():
                    return el
            except Exception:
                pass
    return None

#escribir el texto de búsqueda. Mete el texto que pasas por consola.
def fill_query(driver: webdriver.Chrome, query: str) -> None:
    inp = find_main_search_input(driver)
    if inp is None:
        raise RuntimeError("No encontré el campo principal de búsqueda.")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
    safe_sleep(0.5)
    driver.execute_script("arguments[0].focus();", inp)
    driver.execute_script("arguments[0].value = '';", inp)
    driver.execute_script("arguments[0].value = arguments[1];", inp, query)
    driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", inp)
    driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", inp)
    value = driver.execute_script("return arguments[0].value;", inp)
    if value.strip() != query.strip():
        raise RuntimeError(f"No pude escribir el texto de búsqueda. Valor actual: {value!r}")

#lanza la búsqueda, Busca el botón “Buscar” y lo pulsa.
def submit_search(driver: webdriver.Chrome) -> None:
    xpaths = [
        "//input[@type='button' and contains(@value, 'Buscar')]",
        "//input[@type='submit' and contains(@value, 'Buscar')]",
        "//button[contains(normalize-space(.), 'Buscar')]",
        "//a[contains(normalize-space(.), 'Buscar')]",
        "//span[contains(normalize-space(.), 'Buscar')]",
    ]
    for xp in xpaths:
        elems = driver.find_elements(By.XPATH, xp)
        for e in elems:
            try:
                if e.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", e)
                    safe_sleep(0.3)
                    driver.execute_script("arguments[0].click();", e)
                    return
            except Exception:
                pass

    inp = find_main_search_input(driver)
    if inp is None:
        raise RuntimeError("No pude localizar el campo de búsqueda para lanzar Enter.")
    inp.send_keys(Keys.ENTER)

#esperar respuesta del buscador. Tras pulsar “Buscar”, el script espera a que ocurra algo:
#aparezcan resultados - aparezca un documento - o aparezca un mensaje de error
def wait_for_search_response(driver: webdriver.Chrome, timeout: int = 25) -> None:
    end = time.time() + timeout
    while time.time() < end:
        txt = page_text(driver).lower()
        if "resultados" in txt or "documento" in txt or "/opendocument/" in driver.current_url.lower():
            return
        err = detect_search_error(driver)
        if err:
            raise RuntimeError(err)
        safe_sleep(0.5)

#Esta función intenta decidir si la página actual es realmente una página de resultados.
def on_results_page(driver: webdriver.Chrome) -> bool:
    txt = page_text(driver).lower()
    if detect_search_error(driver):
        return False
    # Buscamos señales más concretas de resultados reales.
    if "/search/an?" in driver.current_url.lower():
        return True
    if "resultados" in txt and "roj:" in txt:
        return True
    if "/opendocument/" in driver.current_url.lower():
        return True
    return False

#filtrar solo sentencias reales
def is_valid_result_link(href: str, text: str) -> bool:
    href_low = (href or "").lower()
    text_clean = (text or "").strip()
    text_low = text_clean.lower()

    if not href_low or href_low.startswith("javascript:") or href_low.endswith("#"):
        return False

    # Solo queremos documentos judiciales concretos, no enlaces temáticos/laterales.
    if "/search/an/opendocument/" not in href_low:
        return False

    # Exigir además un título mínimamente judicial.
    good_prefixes = ("sts", "stsj", "sap", "san", "sjm", "sjs", "ats", "aat")
    good_markers = ("roj:", "ecli:", "sentencia", "auto")
    return (
        bool(text_clean)
        and (text_low.startswith(good_prefixes) or any(m in text_low for m in good_markers))
    )


def extract_result_links(driver: webdriver.Chrome) -> List[Tuple[str, str]]:
    if not on_results_page(driver):
        raise RuntimeError("No estoy en una página válida de resultados.")
    links = driver.find_elements(By.TAG_NAME, "a")
    out: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for a in links:
        try:
            href = a.get_attribute("href") or ""
            text = (a.text or "").strip()
        except Exception:
            continue
        href = urljoin(driver.current_url, href)
        if not is_valid_result_link(href, text):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append((text, href))
    return out

#pasar a la página siguiente
def click_next_page(driver: webdriver.Chrome) -> bool:
    if not on_results_page(driver):
        return False
    xpaths = [
        "//a[contains(., 'Siguiente')]",
        "//a[contains(., '>>')]",
        "//button[contains(., 'Siguiente')]",
        "//input[contains(@value, 'Siguiente')]",
    ]
    old = driver.current_url
    for xp in xpaths:
        for e in driver.find_elements(By.XPATH, xp):
            try:
                if e.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", e)
                    safe_sleep(0.3)
                    driver.execute_script("arguments[0].click();", e)
                    safe_sleep(1.5)
                    wait_ready(driver, 20)
                    return driver.current_url != old or on_results_page(driver)
            except Exception:
                pass
    return False

#encontrar el PDF dentro de una sentencia
def get_pdf_link_from_document_page(driver: webdriver.Chrome) -> Optional[str]:
    # Primero, cualquier enlace directo a PDF.
    for a in driver.find_elements(By.TAG_NAME, "a"):
        try:
            href = a.get_attribute("href") or ""
            if ".pdf" in href.lower():
                return urljoin(driver.current_url, href)
        except Exception:
            continue

    # Luego el típico texto "puede descargar la resolución aquí".
    xpaths = [
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'descargar')]",
        "//a[contains(., 'aquí')]",
    ]
    for xp in xpaths:
        for a in driver.find_elements(By.XPATH, xp):
            try:
                href = a.get_attribute("href") or ""
                if href:
                    return urljoin(driver.current_url, href)
            except Exception:
                continue
    return None

#esperar a que el PDF termine de bajar
def wait_for_download(pdf_dir: Path, before_names: Set[str], timeout: int = 60) -> Optional[Path]:
    end = time.time() + timeout
    while time.time() < end:
        current_names = {p.name for p in pdf_dir.iterdir() if p.is_file()}
        new_names = current_names - before_names
        partials = [p for p in pdf_dir.iterdir() if p.suffix.lower() in (".crdownload", ".part")]
        if new_names and not partials:
            candidates = [pdf_dir / name for name in new_names]
            return max(candidates, key=lambda p: p.stat().st_mtime)
        safe_sleep(1.0)
    return None


def write_csv(rows: List[Tuple[str, str]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["titulo", "url"])
        w.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--output", default="cendoj_output")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--max-docs", type=int, default=20)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--pause", type=float, default=2.0)
    args = parser.parse_args()

    output_dir = Path(args.output)
    pdf_dir = output_dir / "pdfs"
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    driver = None
    all_links: List[Tuple[str, str]] = []
    seen_urls: Set[str] = set()

    try:
        driver = build_driver(args.headless, pdf_dir)
        driver.get(BASE_URL)
        wait_ready(driver)
        safe_sleep(1.5)
        close_overlays(driver)

        fill_query(driver, args.query)
        submit_search(driver)
        wait_ready(driver)
        safe_sleep(2.0)
        wait_for_search_response(driver)

        err = detect_search_error(driver)
        if err:
            raise RuntimeError(err)

        if not on_results_page(driver):
            raise RuntimeError("No he llegado a una página clara de resultados.")

        for page_num in range(1, args.max_pages + 1):
            page_links = extract_result_links(driver)
            fresh = 0
            for title, url in page_links:
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_links.append((title, url))
                    fresh += 1
            print(f"[INFO] Página {page_num}: detectados {len(page_links)} enlaces válidos, nuevos {fresh}")
            safe_sleep(args.pause)

            if page_num < args.max_pages and click_next_page(driver):
                safe_sleep(2.0)
            else:
                break

        if not all_links:
            raise RuntimeError("No he detectado enlaces de resultados válidos.")

        csv_path = output_dir / "enlaces_detectados.csv"
        write_csv(all_links, csv_path)
        print(f"[OK] CSV guardado en: {csv_path}")

        downloaded = 0
        for idx, (title, url) in enumerate(all_links[: args.max_docs], start=1):
            print(f"[INFO] ({idx}/{min(len(all_links), args.max_docs)}) Revisando: {title}")
            try:
                before_names = {p.name for p in pdf_dir.iterdir() if p.is_file()}
                driver.get(url)
                wait_ready(driver)
                safe_sleep(args.pause)

                pdf_url = get_pdf_link_from_document_page(driver)
                if not pdf_url:
                    print("  - No detecté enlace PDF en esta página.")
                    continue

                driver.get(pdf_url)
                wait_ready(driver)
                safe_sleep(1.0)

                new_file = wait_for_download(pdf_dir, before_names, timeout=60)
                if new_file:
                    target = pdf_dir / f"{idx:04d}_{slugify(title)}{new_file.suffix.lower() or '.pdf'}"
                    if new_file != target:
                        try:
                            new_file.rename(target)
                            new_file = target
                        except Exception:
                            pass
                    print(f"  - Descargado: {new_file.name}")
                    downloaded += 1
                else:
                    print("  - No pude confirmar la descarga.")

                safe_sleep(args.pause)

            except Exception as e:
                print(f"  - Error en documento: {e}")

        print(f"[RESUMEN] enlaces={len(all_links)} | descargados={downloaded} | carpeta={pdf_dir.resolve()}")
        return 0

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
