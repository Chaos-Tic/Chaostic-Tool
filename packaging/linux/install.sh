#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
destination="${XDG_DATA_HOME:-$HOME/.local/share}/ChaosticTool/application"
applications="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$destination" "$applications"
if [ "$source_dir" != "$destination" ]; then
    cp -R "$source_dir/." "$destination/"
fi
chmod +x "$destination/ChaosticTool" "$destination/uninstall.sh"
# Desktop Entry quoted values have their own escaping rules.
escaped=$(printf '%s' "$destination" | sed 's/\\/\\\\/g; s/"/\\"/g; s/`/\\`/g; s/\$/\\$/g')
cat > "$applications/chaostictool.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ChaosticTool Desktop
Comment=Catalogue et execution d'outils
Exec="$escaped/ChaosticTool"
Icon=$destination/_internal/desktop/assets/icon.png
Terminal=false
Categories=Utility;Network;
EOF
printf 'ChaosticTool installé dans %s\nDisponible dans le menu des applications.\nDésinstallation : %s/uninstall.sh\n' "$destination" "$destination"
