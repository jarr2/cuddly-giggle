#!/bin/bash
# Carga zonas horarias para que Django pueda usar America/Mexico_City en la base.
if command -v mariadb-tzinfo-to-sql >/dev/null 2>&1; then
  mariadb-tzinfo-to-sql /usr/share/zoneinfo | mariadb --protocol=socket -uroot -p"${MARIADB_ROOT_PASSWORD}" mysql || true
fi
