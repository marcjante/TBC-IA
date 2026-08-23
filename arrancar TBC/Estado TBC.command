#!/bin/bash
# Estado TBC.command
# Doble clic desde Finder para ver si los tres servicios están activos.

cd "$(dirname "$0")"
bash status_tbc_stack.sh
echo ""
read -p "Pulsa Enter para cerrar esta ventana..."
