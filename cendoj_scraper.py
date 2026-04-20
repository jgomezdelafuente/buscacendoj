#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from typing import List, Optional, Set, Tuple
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

BASE_URL = "https://www.poderjudicial.es/search/indexAN.jsp"


def slugify(text: str, max_len: int = 120) -> str:
    text = re.sub(r"[^\w\s.-]", "_", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"_+", "_", text)
    return text[:max_len].strip("._") or "documento"


def safe_sleep(seconds: float) -> None:
    time.sleep(max(seconds, 0.0))


def build_driver(headless: bool, download_dir: Path) -> webdriver.Chrome:
    options = ChromeOptions()

    if headless:
        options.add_argument("--headless=new")

    options.page_load_strategy = "eager"
    options.add_argument("--window-size=1440,1600")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=es-ES")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-blink-features=AutomationControlled")

    prefs = {
        "download.default_directory": str(download_dir.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(90)
    driver.set_script_timeout(90)

    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """
            },
        )
    except Exception:
        pass

    return driver


def wait_ready(driver: webdriver.Chrome, timeout: int = 25) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            state = driver.execute_script("return document.readyState")
            if state in ("interactive", "complete"):
                return
        except Exception:
            pass
        safe_sleep(0.3)
    raise RuntimeError("La página no dejó el DOM listo a tiempo.")


def page_text(driver: webdriver.Chrome) -> str:
    try:
        return (driver.find_element(By.TAG_NAME, "body").text or "").strip()
    except Exception:
        return ""


def is_connection_reset_error(exc: Exception) -> bool:
    txt = str(exc).lower()
    return (
        "err_connection_reset" in txt
        or "connection reset" in txt
        or "net::err_connection_reset" in txt
    )


def safe_get(
    driver: webdriver.Chrome,
    url: str,
    ready_timeout: int = 25,
    retries: int = 4,
    retry_sleep: float = 3.0,
) -> None:
    last_error: Optional[Exception] = None

    for attempt in range(1, retries + 1):
        try:
            driver.get(url)
            safe_sleep(1.0)
            wait_ready(driver, timeout=ready_timeout)
            return

        except TimeoutException as e:
            last_error = e
            try:
                if driver.find_elements(By.TAG_NAME, "body"):
                    return
            except Exception:
                pass

        except WebDriverException as e:
            last_error = e
            if is_connection_reset_error(e):
                safe_sleep(retry_sleep * attempt)
                continue

            try:
                if driver.find_elements(By.TAG_NAME, "body"):
                    return
            except Exception:
                pass

            safe_sleep(retry_sleep * attempt)

        except Exception as e:
            last_error = e
            safe_sleep(retry_sleep * attempt)

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"No pude abrir la URL: {url}")


def close_overlays(driver: webdriver.Chrome) -> None:
    xpaths = [
        "//button[contains(., 'Aceptar')]",
        "//button[contains(., 'ACEPTAR')]",
        "//a[contains(., 'Aceptar')]",
        "//button[contains(., 'Entendido')]",
        "//button[contains(., 'Cerrar')]",
        "//span[contains(., 'Cerrar')]",
        "//button[contains(., 'De acuerdo')]",
        "//button[contains(., 'Aceptar y continuar')]",
    ]
    for xp in xpaths:
        for e in driver.find_elements(By.XPATH, xp):
            try:
                if e.is_displayed():
                    driver.execute_script("arguments[0].click();", e)
                    safe_sleep(0.5)
            except Exception:
                pass


def detect_search_error(driver: webdriver.Chrome) -> Optional[str]:
    txt = page_text(driver).lower()
    if "no se ha podido atender su petición" in txt:
        return "La web indica que no se ha enviado ningún criterio de búsqueda válido."
    if "no ha introducido ninguno de los campos requeridos" in txt:
        return "La web indica que el formulario llegó vacío."
    if "se ha producido un error" in txt and "búsqueda" in txt:
        return "La web devolvió un error al procesar la búsqueda."
    return None


def switch_to_default(driver: webdriver.Chrome) -> None:
    try:
        driver.switch_to.default_content()
    except Exception:
        pass


def find_element_in_all_frames(driver: webdriver.Chrome, by: By, value: str):
    switch_to_default(driver)

    try:
        elems = driver.find_elements(by, value)
        for el in elems:
            try:
                if el.is_displayed() and el.is_enabled():
                    return el, "default"
            except Exception:
                pass
    except Exception:
        pass

    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for idx, frame in enumerate(iframes):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            elems = driver.find_elements(by, value)
            for el in elems:
                try:
                    if el.is_displayed() and el.is_enabled():
                        return el, f"iframe[{idx}]"
                except Exception:
                    pass
        except Exception:
            continue

    driver.switch_to.default_content()
    return None, None


def debug_list_inputs(driver: webdriver.Chrome) -> None:
    switch_to_default(driver)
    print("[DEBUG] Intentando diagnosticar inputs disponibles...")

    def dump_inputs(context_name: str) -> None:
        try:
            inputs = driver.find_elements(By.CSS_SELECTOR, "input, textarea")
            print(f"[DEBUG] {context_name}: {len(inputs)} campos encontrados")
            for i, el in enumerate(inputs[:25], start=1):
                try:
                    typ = el.get_attribute("type")
                    name = el.get_attribute("name")
                    ide = el.get_attribute("id")
                    ph = el.get_attribute("placeholder")
                    val = el.get_attribute("value")
                    print(
                        f"[DEBUG]   {i:02d} type={typ!r} id={ide!r} name={name!r} "
                        f"placeholder={ph!r} value={val!r}"
                    )
                except Exception:
                    pass
        except Exception:
            pass

    dump_inputs("default")

    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"[DEBUG] iframes detectados: {len(iframes)}")
        for idx, frame in enumerate(iframes[:10]):
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame(frame)
                dump_inputs(f"iframe[{idx}]")
            except Exception:
                continue
    finally:
        driver.switch_to.default_content()


def find_main_search_input(driver: webdriver.Chrome):
    selectors = [
        "#frmBusquedajurisprudencia_TEXT",
        "input[name='TEXT']",
        "input[id*='TEXT']",
        "input[name*='TEXT']",
        "input[placeholder*='texto libre' i]",
        "input[title*='texto libre' i]",
        "input[aria-label*='texto libre' i]",
    ]

    for sel in selectors:
        el, where = find_element_in_all_frames(driver, By.CSS_SELECTOR, sel)
        if el is not None:
            print(f"[INFO] Campo de búsqueda encontrado con selector {sel!r} en {where}")
            return el

    # Fallback: buscar cualquier input de texto visible y usable.
    switch_to_default(driver)

    candidates = []

    def collect_candidates(context_name: str) -> None:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, "input, textarea")
            for el in elems:
                try:
                    typ = (el.get_attribute("type") or "").lower()
                    name = (el.get_attribute("name") or "").lower()
                    ide = (el.get_attribute("id") or "").lower()
                    ph = (el.get_attribute("placeholder") or "").lower()
                    title = (el.get_attribute("title") or "").lower()
                    aria = (el.get_attribute("aria-label") or "").lower()

                    if not el.is_displayed() or not el.is_enabled():
                        continue

                    score = 0
                    if typ in ("text", "search", ""):
                        score += 3
                    if "text" in name or "buscar" in name or "search" in name:
                        score += 3
                    if "text" in ide or "buscar" in ide or "search" in ide:
                        score += 3
                    if "texto libre" in ph or "texto libre" in title or "texto libre" in aria:
                        score += 5
                    if "buscar" in ph or "search" in ph:
                        score += 2

                    if score > 0:
                        candidates.append((score, context_name, el))
                except Exception:
                    pass
        except Exception:
            pass

    collect_candidates("default")

    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for idx, frame in enumerate(iframes):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            collect_candidates(f"iframe[{idx}]")
        except Exception:
            continue

    driver.switch_to.default_content()

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_where, best_el = candidates[0]

        # Volver al frame adecuado antes de devolverlo.
        if best_where == "default":
            driver.switch_to.default_content()
        elif best_where.startswith("iframe["):
            idx = int(best_where[7:-1])
            frames = driver.find_elements(By.TAG_NAME, "iframe")
            driver.switch_to.default_content()
            driver.switch_to.frame(frames[idx])

            # Reencontrar elemento similar dentro del iframe
            elems = driver.find_elements(By.CSS_SELECTOR, "input, textarea")
            for el in elems:
                try:
                    if el.is_displayed() and el.is_enabled():
                        typ = (el.get_attribute("type") or "").lower()
                        if typ in ("text", "search", ""):
                            print(f"[INFO] Campo de búsqueda encontrado por heurística en {best_where}")
                            return el
                except Exception:
                    pass

        print(f"[INFO] Campo de búsqueda encontrado por heurística en {best_where}, score={best_score}")
        return best_el

    return None


def fill_query(driver: webdriver.Chrome, query: str) -> None:
    inp = find_main_search_input(driver)
    if inp is None:
        debug_list_inputs(driver)
        raise RuntimeError("No encontré el campo principal de búsqueda.")

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
    safe_sleep(0.5)

    try:
        inp.click()
        safe_sleep(0.2)
    except Exception:
        pass

    try:
        inp.clear()
        safe_sleep(0.2)
    except Exception:
        pass

    ok = False

    # intento normal
    try:
        inp.send_keys(Keys.CONTROL, "a")
        safe_sleep(0.1)
        inp.send_keys(Keys.DELETE)
        safe_sleep(0.1)
        inp.send_keys(query)
        safe_sleep(0.3)
        value = inp.get_attribute("value") or ""
        if value.strip() == query.strip():
            ok = True
    except Exception:
        pass

    # fallback con JS
    if not ok:
        try:
            driver.execute_script("arguments[0].focus();", inp)
            driver.execute_script("arguments[0].value = '';", inp)
            driver.execute_script("arguments[0].value = arguments[1];", inp, query)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", inp)
            driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", inp)
            safe_sleep(0.3)
            value = driver.execute_script("return arguments[0].value;", inp) or ""
            if value.strip() == query.strip():
                ok = True
        except Exception:
            pass

    if not ok:
        raise RuntimeError("No pude escribir el texto de búsqueda.")


def submit_search(driver: webdriver.Chrome) -> None:
    xpaths = [
        "//input[@type='button' and contains(@value, 'Buscar')]",
        "//input[@type='submit' and contains(@value, 'Buscar')]",
        "//button[contains(normalize-space(.), 'Buscar')]",
        "//a[contains(normalize-space(.), 'Buscar')]",
        "//span[contains(normalize-space(.), 'Buscar')]",
    ]

    for xp in xpaths:
        el, where = find_element_in_all_frames(driver, By.XPATH, xp)
        if el is not None:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                safe_sleep(0.3)
                driver.execute_script("arguments[0].click();", el)
                print(f"[INFO] Búsqueda lanzada desde {where}")
                return
            except Exception:
                pass

    inp = find_main_search_input(driver)
    if inp is None:
        raise RuntimeError("No pude localizar el campo de búsqueda para lanzar Enter.")
    inp.send_keys(Keys.ENTER)


def wait_for_search_response(driver: webdriver.Chrome, timeout: int = 30) -> None:
    end = time.time() + timeout
    while time.time() < end:
        switch_to_default(driver)
        txt = page_text(driver).lower()
        url = driver.current_url.lower()

        if "/search/an?" in url or "/search/an/opendocument/" in url:
            return
        if "roj:" in txt:
            return
        if "resultados" in txt:
            return

        err = detect_search_error(driver)
        if err:
            raise RuntimeError(err)

        safe_sleep(0.5)

    raise RuntimeError("La búsqueda no devolvió resultados visibles a tiempo.")


def on_results_page(driver: webdriver.Chrome) -> bool:
    switch_to_default(driver)
    txt = page_text(driver).lower()
    url = driver.current_url.lower()

    if detect_search_error(driver):
        return False
    if "/search/an?" in url:
        return True
    if "resultados" in txt and "roj:" in txt:
        return True
    if "/opendocument/" in url:
        return True
    return False


def is_valid_result_link(href: str, text: str) -> bool:
    href_low = (href or "").lower()
    text_clean = (text or "").strip()
    text_low = text_clean.lower()

    if not href_low or href_low.startswith("javascript:") or href_low.endswith("#"):
        return False

    if "/search/an/opendocument/" not in href_low:
        return False

    good_prefixes = ("sts", "stsj", "sap", "san", "sjm", "sjs", "ats", "aat")
    good_markers = ("roj:", "ecli:", "sentencia", "auto")

    return bool(text_clean) and (
        text_low.startswith(good_prefixes) or any(m in text_low for m in good_markers)
    )


def extract_result_links(driver: webdriver.Chrome) -> List[Tuple[str, str]]:
    switch_to_default(driver)

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


def click_next_page(driver: webdriver.Chrome) -> bool:
    switch_to_default(driver)

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
                if e.is_displayed() and e.is_enabled():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", e)
                    safe_sleep(0.3)
                    driver.execute_script("arguments[0].click();", e)
                    safe_sleep(2.0)
                    wait_ready(driver, 20)
                    return driver.current_url != old or on_results_page(driver)
            except Exception:
                pass

    return False


def get_pdf_link_from_document_page(driver: webdriver.Chrome) -> Optional[str]:
    switch_to_default(driver)

    for a in driver.find_elements(By.TAG_NAME, "a"):
        try:
            href = a.get_attribute("href") or ""
            if ".pdf" in href.lower():
                return urljoin(driver.current_url, href)
        except Exception:
            continue

    xpaths = [
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), 'descargar')]",
        "//a[contains(., 'aquí')]",
        "//a[contains(., 'PDF')]",
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


def wait_for_download(pdf_dir: Path, before_names: Set[str], timeout: int = 60) -> Optional[Path]:
    end = time.time() + timeout

    while time.time() < end:
        current_files = [p for p in pdf_dir.iterdir() if p.is_file()]
        current_names = {p.name for p in current_files}
        new_names = current_names - before_names

        partials = [
            p for p in current_files
            if p.name.lower().endswith(".crdownload") or p.name.lower().endswith(".part")
        ]

        if new_names and not partials:
            candidates = [pdf_dir / name for name in new_names]
            try:
                return max(candidates, key=lambda p: p.stat().st_mtime)
            except Exception:
                return candidates[0]

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

        print("[INFO] Abriendo la web...")
        safe_get(driver, BASE_URL, ready_timeout=30, retries=5, retry_sleep=3.0)
        safe_sleep(2.0)
        close_overlays(driver)

        print("[INFO] Escribiendo búsqueda...")
        fill_query(driver, args.query)

        print("[INFO] Lanzando búsqueda...")
        submit_search(driver)
        safe_sleep(2.5)
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

                safe_get(driver, url, ready_timeout=30, retries=4, retry_sleep=2.5)
                safe_sleep(args.pause)

                pdf_url = get_pdf_link_from_document_page(driver)
                if not pdf_url:
                    print("  - No detecté enlace PDF en esta página.")
                    continue

                safe_get(driver, pdf_url, ready_timeout=30, retries=4, retry_sleep=2.5)
                safe_sleep(1.5)

                new_file = wait_for_download(pdf_dir, before_names, timeout=60)
                if new_file:
                    ext = new_file.suffix.lower() or ".pdf"
                    target = pdf_dir / f"{idx:04d}_{slugify(title)}{ext}"

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