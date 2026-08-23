#!/bin/bash
# Parar TBC.command
# Doble clic desde Finder para parar los tres servicios.

cd "$(dirname "$0")"
bash stop_tbc_stack.sh
echo ""
read -p "Pulsa Enter para cerrar esta ventana..."
