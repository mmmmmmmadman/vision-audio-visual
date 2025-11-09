#!/bin/bash
# VAV 專案清理腳本 - 2025-11-04
# 移除過時的文件和程式

set -e

PROJECT_DIR="/Users/madzine/Documents/VAV"
ARCHIVE_DIR="$PROJECT_DIR/archive_20251104"

echo "=================================="
echo "VAV 專案清理 - 2025-11-04"
echo "=================================="

# 建立歸檔目錄
mkdir -p "$ARCHIVE_DIR"/{docs,tests}

echo ""
echo "步驟 1: 歸檔過時的計劃文件..."
# 過時計劃文件
OLD_PLAN_DOCS=(
    "VAV_20251103_RESTORATION_PLAN.md"
    "VAV_20251103_RESTORATION_STATUS.md"
    "VAV_GUI_REORGANIZATION_PLAN.md"
    "GPU_REFACTOR_PLAN_20251104.md"
    "CLEANUP_PLAN_20251104.md"
)

for doc in "${OLD_PLAN_DOCS[@]}"; do
    if [ -f "$PROJECT_DIR/$doc" ]; then
        echo "  歸檔: $doc"
        mv "$PROJECT_DIR/$doc" "$ARCHIVE_DIR/docs/"
    fi
done

echo ""
echo "步驟 2: 歸檔過時的功能文件..."
OLD_FEATURE_DOCS=(
    "PBO_IMPLEMENTATION_SUMMARY.md"
    "REGION_RENDERING_GUIDE.md"
)

for doc in "${OLD_FEATURE_DOCS[@]}"; do
    if [ -f "$PROJECT_DIR/$doc" ]; then
        echo "  歸檔: $doc"
        mv "$PROJECT_DIR/$doc" "$ARCHIVE_DIR/docs/"
    fi
done

echo ""
echo "步驟 3: 歸檔過時的最佳化報告..."
OLD_OPTIMIZATION_DOCS=(
    "OPTIMIZATION_REPORT.md"
    "GRAIN_OPTIMIZATION_REPORT.md"
)

for doc in "${OLD_OPTIMIZATION_DOCS[@]}"; do
    if [ -f "$PROJECT_DIR/$doc" ]; then
        echo "  歸檔: $doc"
        mv "$PROJECT_DIR/$doc" "$ARCHIVE_DIR/docs/"
    fi
done

echo ""
echo "步驟 4: 移動測試檔案..."
# 測試程式移到 tests 目錄
TEST_FILES=(
    "test_grain_stats.py"
    "test_grain_performance.py"
    "test_grain_chaos.py"
    "test_ellen_ripley_chaos.py"
    "test_effects_optimization.py"
    "test_effects_functional_verification.py"
    "test_edge_cv.py"
    "verification_tests.py"
)

for test in "${TEST_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$test" ]; then
        echo "  移動: $test"
        mv "$PROJECT_DIR/$test" "$ARCHIVE_DIR/tests/"
    fi
done

echo ""
echo "步驟 5: 刪除備份檔案..."
# 刪除備份檔案
if [ -f "$PROJECT_DIR/vav/visual/qt_opengl_renderer.py.backup_before_refactor" ]; then
    echo "  刪除: vav/visual/qt_opengl_renderer.py.backup_before_refactor"
    rm "$PROJECT_DIR/vav/visual/qt_opengl_renderer.py.backup_before_refactor"
fi

echo ""
echo "步驟 6: 清理 benchmark 輸出..."
if [ -f "$PROJECT_DIR/benchmark_sd_output.txt" ]; then
    echo "  移動: benchmark_sd_output.txt"
    mv "$PROJECT_DIR/benchmark_sd_output.txt" "$ARCHIVE_DIR/"
fi

echo ""
echo "=================================="
echo "清理完成！"
echo "=================================="
echo ""
echo "歸檔位置: $ARCHIVE_DIR"
echo ""
ls -lh "$ARCHIVE_DIR"
echo ""
ls -lh "$ARCHIVE_DIR/docs" | wc -l | xargs echo "文件數量:"
ls -lh "$ARCHIVE_DIR/tests" | wc -l | xargs echo "測試數量:"
echo ""
echo "重要文件已保留:"
echo "  - GPU_REFACTOR_20251104_2318.md"
echo "  - BENCHMARK_RESULTS_20251104.md"
echo "  - BENCHMARK_SD_RESULTS_20251104.md"
echo "  - GPU_MULTIVERSE_BUGFIX_20251104.md"
echo "  - VAV_20251104_GPU_MILESTONE.md (新建)"
echo "  - CHANGELOG.md"
echo "  - ARCHIVED_FEATURES.md"
