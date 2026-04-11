El código busca sentencias de una temática en cendoj y se las descarga en formato pdf.

Ejmplo de como invocar al desarrollo:
python cendoj_scraper.py "ajenidad dependencia autonomo" --max-pages 1 --max-docs 5 --pause 3
 - ajenidad dependencia autonomo --> El campo libre sobre el que se quiere buscar
 - max-pages: número de páginas que saldrán en la web de cendoj al hacer la búsqueda
 - max-docs: cuántos documentos (sentencias) quieres que el script procese y descargue
 - pause: tiempo entre descarga y descarga.

Es necesario usar "pause" ya que cendoj no permite descarga masivas.
