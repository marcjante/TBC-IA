#!/bin/bash
# Arrancar TBC.command
# Doble clic desde Finder para arrancar los tres servicios.
# Se queda abierta la ventana de Terminal para que veas el resultado.

cd "$(dirname "$0")"
bash start_tbc_stack.sh
echo ""
bash status_tbc_stack.sh
echo ""
read -p "Pulsa Enter para cerrar esta ventana..."
