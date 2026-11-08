#!/bin/sh
# vyrenderuje jeden čtverec mapy: ./render_chunk.sh 0,-1 [varianty]
# okraje s řezem zeminou se berou ze scény (strany bez souseda), všechny čtverce s průhledným pozadím
set -e
C=$1; shift; V=${*:-"autumn winter spring summer lights"}
if [ "$C" = "0,0" ]; then D=build; else D=build/c$(echo $C | tr ',' '_'); fi
G="gx0=-1646.34559672906 gy1=988.7958500237901"
for s in $V; do
  if [ "$s" = lights ]; then
    node render.mjs mpp=0.2 dir=$D out=$D/tiles_lights season=autumn mode=lights alpha=1 $G | grep -c dlaždice
  else
    node render.mjs mpp=0.2 dir=$D out=$D/tiles_$s season=$s alpha=1 $G | grep -c dlaždice
  fi
done
echo HOTOVO $C
