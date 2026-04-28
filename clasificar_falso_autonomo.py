from pathlib import Path
import shutil
import re

try:
    from pypdf import PdfReader
except ImportError:
    raise SystemExit("Instala pypdf con: pip install pypdf")


ORIGEN = Path(r"C:\Datos\IA\MasterIA\codigo\JuezIA\cendoj\cendoj_output\pdfs")
DESTINO = ORIGEN / "buenos"


PATRONES_AUTONOMO = [
    r"\btrabajador(?:es)? autónomo(?:s)?\b",
    r"\btrabajo autónomo\b",
    r"\bprestación de servicios profesionales\b",
    r"\bcontrato de prestación de servicios\b",
    r"\bcontrato de arrendamiento de servicios\b",
    r"\bcontrato mercantil\b",
    r"\brelación mercantil\b",
    r"\bnaturaleza mercantil\b",
    r"\barrendamiento de servicios\b",
    r"\bcontratista independiente\b",
    r"\bno será considerado empleado\b",
    r"\balta en el reta\b",
    r"\brégimen especial de trabajadores autónomos\b",
    r"\bcenso de obligados tributarios\b",
    r"\bepígrafe i\.?a\.?e\.?\b",
    r"\btrabajador autónomo económicamente dependiente\b",
    r"\bautónomo económicamente dependiente\b",
    r"\bcontrato de autónomo económicamente dependiente\b",
    r"\bcondición de trade\b",
    r"\bcontrato trade\b",
    r"\bcontrato de trade\b",
    r"\bestatuto del trabajo autónomo\b",
    r"\bleta\b",
    r"\bfacturas emitidas\b",
    r"\bemisión de facturas\b",
    r"\bfacturas eran confeccionadas\b",
    r"\blas facturas eran confeccionadas por\b",
    r"\bfacturas confeccionadas por\b",
    r"\biva correspondiente\b",
]


PATRONES_LABORALIDAD = [
    r"\brelación laboral\b",
    r"\bnaturaleza laboral\b",
    r"\blaboralidad de la relación\b",
    r"\bexistencia de relación laboral\b",
    r"\bexistencia de una relación laboral\b",
    r"\bcontrato de trabajo\b",
    r"\bcalificación de la relación\b",
    r"\bnaturaleza de la relación\b",
    r"\bverdadera naturaleza jurídica\b",
    r"\brelación laboral encubierta\b",
    r"\bmodalidad de trabajo autónomo\b",
    r"\benmascarado bajo la modalidad\b",
    r"\bprestación de servicios laborales\b",
    r"\btrabajo por cuenta ajena\b",
    r"\bservicios retribuidos por cuenta ajena\b",
    r"\bdentro del ámbito de organización y dirección\b",
    r"\brégimen general de la seguridad social\b",
    r"\balta en seguridad social\b",
    r"\bdespido improcedente\b",
    r"\bdeclaración de improcedencia\b",
    r"\bdespido tácito\b",
    r"\bdespido expreso\b",
    r"\bextinción indemnizada\b",
    r"\bacciones de despido\b",
    r"\bincompetencia de jurisdicción\b",
    r"\bcompetencia del orden social\b",
    r"\border social de la jurisdicción\b",
    r"\bnotas definitorias de la relación laboral\b",
    r"\bconcurren las notas definitorias\b",
    r"\bconcurren las notas de dependencia y ajenidad\b",
]


PATRONES_INDICIOS = [
    r"\bajenidad y dependencia\b",
    r"\bdependencia y ajenidad\b",
    r"\bnotas de laboralidad\b",
    r"\bnota de dependencia\b",
    r"\bnota de ajenidad\b",
    r"\bnotas de dependencia y ajenidad\b",
    r"\bpoder de dirección\b",
    r"\bpoder disciplinario\b",
    r"\bámbito de organización\b",
    r"\borganización y dirección\b",
    r"\bámbito de organización y dirección\b",
    r"\bintegración en la organización\b",
    r"\binserción en la organización\b",
    r"\borganización empresarial\b",
    r"\bcarecía de organización empresarial\b",
    r"\bcriterios organizativos propios\b",
    r"\bmedios de producción\b",
    r"\bmedios propios\b",
    r"\bherramientas de trabajo\b",
    r"\bteléfono móvil de su propiedad\b",
    r"\bmoto y el teléfono móvil\b",
    r"\bbicicleta y su teléfono móvil\b",
    r"\bplataforma virtual\b",
    r"\bplataforma digital\b",
    r"\baplicación informática\b",
    r"\baplicación móvil\b",
    r"\ba través de la app\b",
    r"\bapp de la empresa\b",
    r"\bdescargan la aplicación\b",
    r"\biniciar sesión en la app\b",
    r"\bcerrar sesión en la app\b",
    r"\bpunto de control\b",
    r"\bcentroide\b",
    r"\bzona asignada\b",
    r"\bárea asignada\b",
    r"\bfranja horaria\b",
    r"\bfranjas horarias\b",
    r"\breserva de la franja horaria\b",
    r"\bturnos de reparto\b",
    r"\basignación de turnos\b",
    r"\bcambio de turno\b",
    r"\bsistema de calendario\b",
    r"\bstaffomatic\b",
    r"\bdisponibilidad horaria\b",
    r"\bauto-asignación\b",
    r"\bposición de auto-asignación\b",
    r"\basignación automática\b",
    r"\basignación de pedidos\b",
    r"\bsistema de asignación de pedidos\b",
    r"\balgoritmo de glovo\b",
    r"\bsistema de valoración\b",
    r"\bsistema de puntuación\b",
    r"\bsistema de ranking\b",
    r"\bnivel de excelencia\b",
    r"\bnivel de calidad\b",
    r"\bcalidad\/excelencia\b",
    r"\bboletín de incidencias\b",
    r"\bincidencia grave\b",
    r"\bpreferencia de acceso\b",
    r"\bmejor puntuación\b",
    r"\bbajarle de categoría\b",
    r"\bprincipiante, junior y senior\b",
    r"\bhoras diamante\b",
    r"\bfranjas pico\b",
    r"\bporcentaje de aceptación\b",
    r"\baceptación de pedidos\b",
    r"\brechazo de pedidos\b",
    r"\brechazar un pedido\b",
    r"\brechazo de ofertas\b",
    r"\bfalta de disponibilidad\b",
    r"\bno está operativo\b",
    r"\bpenalización de\b",
    r"\bvaloración del cliente\b",
    r"\bvaloración del cliente final\b",
    r"\beficiencia demostrada\b",
    r"\brapidez de las entregas\b",
    r"\btiempos estimados\b",
    r"\bfalseo de métricas\b",
    r"\bcontrol de equipamientos\b",
    r"\brevisiones periódicas del equipamiento\b",
    r"\bgeolocalización gps\b",
    r"\bgeolocalizados\b",
    r"\bpermanentemente localizado\b",
    r"\bcontrol empresarial en tiempo real\b",
    r"\bregistraban los kilómetros\b",
    r"\btiempo que tardan\b",
    r"\bse solicitan explicaciones\b",
    r"\binstrucciones empresariales\b",
    r"\binstrucciones sobre cómo\b",
    r"\breglas precisas impuestas\b",
    r"\bforma exigida por el cliente\b",
    r"\bequipo de operaciones\b",
    r"\blive operations\b",
    r"\bdriver operations\b",
    r"\btelegram\b",
    r"\briders\b",
    r"\briders valencia\b",
    r"\brepartidor(?:es)?\b",
    r"\brider(?:s)?\b",
    r"\bglovers\b",
    r"\brecados o encargos\b",
    r"\brecados, pedidos o microtareas\b",
    r"\bpedido entregado\b",
    r"\bcliente final\b",
    r"\bconsumidor final\b",
    r"\brestaurantes adheridos\b",
    r"\brestaurantes favoritos\b",
    r"\bcondiciones de los restaurantes\b",
    r"\bidentidad de los clientes\b",
    r"\bfijación de precios\b",
    r"\bfijaba el precio\b",
    r"\bprecio del servicio\b",
    r"\bprecio de los servicios\b",
    r"\bcobraba éste a través de la aplicación\b",
    r"\bno estando permitida.*cantidad.*metálico\b",
    r"\bretribución fija por servicio\b",
    r"\bcantidad por pedido\b",
    r"\bpago de una cantidad por pedido\b",
    r"\bkilometraje y tiempo de espera\b",
    r"\bcompensación económica por el tiempo de espera\b",
    r"\bcomisión por la intermediación\b",
    r"\bno participando.*beneficios\b",
    r"\bimagen de la compañía\b",
    r"\bcara de la empresa\b",
    r"\bropa de deliveroo\b",
    r"\buniforme\b",
    r"\bbolsa térmica\b",
    r"\bequipamiento\b",
    r"\bmochila\b",
    r"\bcaja\b",
    r"\btarjeta de crédito facilitada\b",
    r"\btarjeta de crédito proporcionada\b",
    r"\badelanto de 100 euros\b",
    r"\bsubcontratar.*previa autorización\b",
    r"\bprevia autorización de la empresa\b",
    r"\bsubcontratación.*residual\b",
    r"\bno existe pacto de exclusividad\b",
    r"\btrabajar para varias plataformas\b",
    r"\blibertad para contratar con terceros\b",
    r"\bprestación personal\b",
    r"\bdesempeño personal del trabajo\b",
    r"\bsin sufrir penalización\b",
    r"\bconsecuencia desfavorable\b",
    r"\bprocedimiento para comunicarlo\b",
    r"\bjustificar dicha causa\b",
    r"\bausencia sin justificar\b",
]


PATRONES_PLATAFORMA = [
    r"\bglovo\b",
    r"\bglovoapp\b",
    r"\bglover(?:s)?\b",
    r"\bdeliveroo\b",
    r"\broofoods\b",
    r"\brider(?:s)?\b",
    r"\brepartidor(?:es)?\b",
    r"\bplataforma on demand\b",
    r"\breparto exprés\b",
    r"\breparto y distribución\b",
    r"\bentrega de comida\b",
    r"\bcomida preparada\b",
    r"\bservicios de reparto\b",
    r"\bservicios de recadero\b",
]


PATRONES_DESCARTE = [
    r"\btrabajadores extranjeros sin permiso\b",
    r"\bsin permiso de trabajo\b",
    r"\bsin permiso de residencia\b",
    r"\bsituación irregular\b",
    r"\bsin contrato de trabajo\b",
    r"\bsin alta en la seguridad social\b",
    r"\bdelito contra los derechos de los trabajadores\b",
    r"\bprocedimiento abreviado\b",
    r"\bsala de lo penal\b",
    r"\baudiencia provincial\b",
    r"\btráfico de drogas\b",
    r"\bdelito contra la salud pública\b",
    r"\birpf\b",
    r"\bexención fiscal\b",
    r"\bliquidación tributaria\b",
    r"\btribunal económico administrativo\b",
]


def normalizar_texto(texto: str) -> str:
    texto = texto.lower()
    texto = texto.replace("\n", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto


def extraer_texto_pdf(ruta_pdf: Path) -> str:
    texto_paginas = []

    try:
        reader = PdfReader(str(ruta_pdf))

        for page in reader.pages:
            texto = page.extract_text() or ""
            texto_paginas.append(texto)

    except Exception as e:
        print(f"[ERROR] No se pudo leer {ruta_pdf.name}: {e}")
        return ""

    return normalizar_texto(" ".join(texto_paginas))


def contar_patrones(texto: str, patrones: list[str]) -> int:
    total = 0

    for patron in patrones:
        if re.search(patron, texto, flags=re.IGNORECASE):
            total += 1

    return total


def obtener_patrones_encontrados(texto: str, patrones: list[str]) -> list[str]:
    encontrados = []

    for patron in patrones:
        if re.search(patron, texto, flags=re.IGNORECASE):
            encontrados.append(patron)

    return encontrados


def es_pdf_bueno(texto: str) -> tuple[bool, dict]:
    score_autonomo = contar_patrones(texto, PATRONES_AUTONOMO)
    score_laboralidad = contar_patrones(texto, PATRONES_LABORALIDAD)
    score_indicios = contar_patrones(texto, PATRONES_INDICIOS)
    score_plataforma = contar_patrones(texto, PATRONES_PLATAFORMA)
    score_descarte = contar_patrones(texto, PATRONES_DESCARTE)

    score_total = (
        score_autonomo * 4
        + score_laboralidad * 3
        + score_indicios * 2
        + score_plataforma * 2
        - score_descarte * 3
    )

    resultado = {
        "autonomo": score_autonomo,
        "laboralidad": score_laboralidad,
        "indicios": score_indicios,
        "plataforma": score_plataforma,
        "descarte": score_descarte,
        "score_total": score_total,
        "patrones_autonomo": obtener_patrones_encontrados(texto, PATRONES_AUTONOMO),
        "patrones_laboralidad": obtener_patrones_encontrados(texto, PATRONES_LABORALIDAD),
        "patrones_indicios": obtener_patrones_encontrados(texto, PATRONES_INDICIOS),
        "patrones_plataforma": obtener_patrones_encontrados(texto, PATRONES_PLATAFORMA),
        "patrones_descarte": obtener_patrones_encontrados(texto, PATRONES_DESCARTE),
    }

    if score_descarte >= 2 and score_autonomo == 0:
        return False, resultado

    if score_plataforma >= 1 and score_autonomo >= 1 and score_laboralidad >= 1:
        return True, resultado

    if score_autonomo >= 2 and score_laboralidad >= 1:
        return True, resultado

    if score_autonomo >= 1 and score_laboralidad >= 1 and score_indicios >= 2:
        return True, resultado

    if score_total >= 12 and score_descarte <= 1:
        return True, resultado

    return False, resultado


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)

    pdfs = [
        pdf
        for pdf in ORIGEN.glob("*.pdf")
        if pdf.is_file() and pdf.parent != DESTINO
    ]

    print(f"Carpeta origen: {ORIGEN}")
    print(f"Carpeta destino: {DESTINO}")
    print(f"PDFs encontrados: {len(pdfs)}")
    print("-" * 100)

    buenos = 0
    omitidos = 0

    for pdf in pdfs:
        texto = extraer_texto_pdf(pdf)

        if not texto.strip():
            omitidos += 1
            print(f"[OMITIDO] {pdf.name} -> sin texto extraíble")
            continue

        cumple, info = es_pdf_bueno(texto)

        if cumple:
            destino_pdf = DESTINO / pdf.name
            shutil.copy2(pdf, destino_pdf)
            buenos += 1

            print(f"[BUENO] {pdf.name}")
            print(
                f"        score_total={info['score_total']} | "
                f"autonomo={info['autonomo']} | "
                f"laboralidad={info['laboralidad']} | "
                f"indicios={info['indicios']} | "
                f"plataforma={info['plataforma']} | "
                f"descarte={info['descarte']}"
            )
            print(f"        patrones_autonomo={info['patrones_autonomo']}")
            print(f"        patrones_laboralidad={info['patrones_laboralidad']}")
            print(f"        patrones_indicios={info['patrones_indicios']}")
            print(f"        patrones_plataforma={info['patrones_plataforma']}")
        else:
            print(f"[NO] {pdf.name}")
            print(
                f"     score_total={info['score_total']} | "
                f"autonomo={info['autonomo']} | "
                f"laboralidad={info['laboralidad']} | "
                f"indicios={info['indicios']} | "
                f"plataforma={info['plataforma']} | "
                f"descarte={info['descarte']}"
            )

    print("-" * 100)
    print(f"PDFs buenos copiados: {buenos}")
    print(f"PDFs omitidos por falta de texto: {omitidos}")


if __name__ == "__main__":
    main()