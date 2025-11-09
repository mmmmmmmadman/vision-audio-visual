#!/bin/bash
# Monitor Agent 1's Progress
# Agent 2: Quality Assurance

FILE="/Users/madzine/Documents/VAV/vav/visual/qt_opengl_renderer.py"
BACKUP="/Users/madzine/Documents/VAV/vav/visual/qt_opengl_renderer_old.py"
LAST_MOD=""

echo "=========================================="
echo "Agent 2: Monitoring Agent 1's Progress"
echo "=========================================="
echo ""
echo "Watching: $FILE"
echo "Backup:   $BACKUP"
echo ""
echo "Press Ctrl+C to stop monitoring"
echo ""

while true; do
    if [ -f "$FILE" ]; then
        CURRENT_MOD=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$FILE" 2>/dev/null)

        if [ "$CURRENT_MOD" != "$LAST_MOD" ] && [ -n "$LAST_MOD" ]; then
            echo "=========================================="
            echo "🔔 FILE CHANGE DETECTED!"
            echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
            echo "=========================================="
            echo ""

            # Check if content changed
            if ! diff -q "$FILE" "$BACKUP" > /dev/null 2>&1; then
                echo "✅ Content has changed from backup"
                echo ""

                # Show summary of changes
                echo "Lines changed:"
                diff "$BACKUP" "$FILE" | grep -E "^[0-9]" | head -5
                echo ""

                # Check for Multi-Pass keywords
                echo "Checking for Multi-Pass implementation..."
                if grep -q "Pass 1" "$FILE"; then
                    echo "  ✓ Found 'Pass 1' references"
                fi
                if grep -q "Pass 2" "$FILE"; then
                    echo "  ✓ Found 'Pass 2' references"
                fi
                if grep -q "Pass 3" "$FILE"; then
                    echo "  ✓ Found 'Pass 3' references"
                fi

                # Count FBOs
                FBO_COUNT=$(grep -c "glGenFramebuffers\|fbo.*=.*glGenFramebuffers" "$FILE" 2>/dev/null || echo "0")
                echo "  FBO count: $FBO_COUNT"

                echo ""
                echo "Agent 1 is actively working on the rewrite!"
                echo ""
            else
                echo "⚠️  File timestamp changed but content identical to backup"
                echo ""
            fi
        fi

        LAST_MOD="$CURRENT_MOD"
    else
        echo "⚠️  File not found: $FILE"
    fi

    # Check every 5 seconds
    sleep 5
done
