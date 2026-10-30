MANIFEST=/var/lib/chaostictool/manifest
# $1 == 0 means full removal (not an upgrade).
if [ "$1" = 0 ] && [ -f "$MANIFEST" ]; then
    count=$(grep -cvE '^[[:space:]]*(#|$)' "$MANIFEST" 2>/dev/null || true)
    [ -n "$count" ] || count=0
    if [ "$count" -gt 0 ]; then
        echo "ChaosticTool recorded $count installed item(s) in $MANIFEST." >&2
        echo "Removing this package does NOT remove those external tools, repository" >&2
        echo "entries or system edits. To review and remove them, run:" >&2
        echo "    sudo chaostictool-uninstall --dry-run   # preview" >&2
        echo "    sudo chaostictool-uninstall             # remove what ChaosticTool installed" >&2
        echo "The manifest is kept so this can also be done later." >&2
    fi
fi
