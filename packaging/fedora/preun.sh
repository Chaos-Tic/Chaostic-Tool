MANIFEST=/var/lib/chaostictool/manifest
# $1 == 0 means full removal (not an upgrade).
if [ "$1" = 0 ] && [ -f "$MANIFEST" ]; then
    count=$(grep -cvE '^[[:space:]]*(#|$)' "$MANIFEST" 2>/dev/null || true)
    [ -n "$count" ] || count=0
    if [ "$count" -gt 0 ]; then
        # Short names of the recorded items (last path or field component), 8 at most.
        names=$(grep -vE '^[[:space:]]*(#|$)' "$MANIFEST" 2>/dev/null | sed 's/.*[:/]//' | grep -v '^$' | sort -u || true)
        shown=$(printf '%s\n' "$names" | head -n 8 | tr '\n' ' ')
        [ "$(printf '%s\n' "$names" | grep -c .)" -gt 8 ] && shown="$shown..."
        echo "ChaosticTool recorded $count installed item(s) in $MANIFEST:" >&2
        echo "    $shown" >&2
        echo "Removing this package does NOT remove those external tools, repository" >&2
        echo "entries or system edits; it also removes the chaostictool-uninstall command." >&2
        echo "The manifest is kept. To remove the recorded items, either reinstall" >&2
        echo "ChaosticTool and run 'sudo chaostictool-uninstall' (preview: --dry-run)," >&2
        echo "or run 'sudo ./uninstall.sh' from a source checkout." >&2
    fi
fi
