El código realiza las siguuentes tareas: 
- Descarga un listado de pdfs del cendoj
- Es muy posible que muchos de ellos no tengo nada que ver con temas de autónomos, por lo que descartamos aquellos que no cumplan ciertos patrones

Ejemplo de comando a lanzar:  python cendoj_scraper.py "falso autonomo glovo" --max-pages 2 --max-docs 5 --pause 3

 - falso autonomo glovo --> El campo libre sobre el que se quiere buscar
 - max-pages: número de páginas que saldrán en la web de cendoj al hacer la búsqueda
 - max-docs: cuántos documentos (sentencias) quieres que el script procese y descargue
 - pause: tiempo entre descarga y descarga.
