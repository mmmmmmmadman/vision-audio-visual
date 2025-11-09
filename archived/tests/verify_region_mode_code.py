#!/usr/bin/env python3
"""
GPU Region Mode 代碼完整性驗證
檢查所有相關功能是否正確實作
"""

import sys
import os

# 確保可以 import VAV 模組
sys.path.insert(0, '/Users/madzine/Documents/VAV')


def check_imports():
    """檢查所有必要的模組是否可以 import"""
    print("=" * 60)
    print("1. CHECKING IMPORTS")
    print("=" * 60)

    tests = []

    # PyQt6
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        print("✓ PyQt6 imported successfully")
        tests.append(("PyQt6", True))
    except ImportError as e:
        print(f"✗ PyQt6 import failed: {e}")
        tests.append(("PyQt6", False))

    # OpenGL
    try:
        import OpenGL.GL as GL
        from OpenGL.GL import shaders
        print("✓ OpenGL imported successfully")
        tests.append(("OpenGL", True))
    except ImportError as e:
        print(f"✗ OpenGL import failed: {e}")
        tests.append(("OpenGL", False))

    # OpenCV
    try:
        import cv2
        print("✓ OpenCV imported successfully")
        tests.append(("OpenCV", True))
    except ImportError as e:
        print(f"✗ OpenCV import failed: {e}")
        tests.append(("OpenCV", False))

    # NumPy
    try:
        import numpy as np
        print("✓ NumPy imported successfully")
        tests.append(("NumPy", True))
    except ImportError as e:
        print(f"✗ NumPy import failed: {e}")
        tests.append(("NumPy", False))

    # VAV modules
    try:
        from vav.core.controller import VAVController
        print("✓ VAVController imported successfully")
        tests.append(("VAVController", True))
    except ImportError as e:
        print(f"✗ VAVController import failed: {e}")
        tests.append(("VAVController", False))

    try:
        from vav.visual.qt_opengl_renderer import QtMultiverseRenderer
        print("✓ QtMultiverseRenderer imported successfully")
        tests.append(("QtMultiverseRenderer", True))
    except ImportError as e:
        print(f"✗ QtMultiverseRenderer import failed: {e}")
        tests.append(("QtMultiverseRenderer", False))

    try:
        from vav.visual.content_aware_regions import ContentAwareRegionMapper
        print("✓ ContentAwareRegionMapper imported successfully")
        tests.append(("ContentAwareRegionMapper", True))
    except ImportError as e:
        print(f"✗ ContentAwareRegionMapper import failed: {e}")
        tests.append(("ContentAwareRegionMapper", False))

    return tests


def check_qt_opengl_renderer():
    """檢查 Qt OpenGL Renderer 的 region mode 實作"""
    print("\n" + "=" * 60)
    print("2. CHECKING QT OPENGL RENDERER")
    print("=" * 60)

    tests = []

    try:
        from vav.visual.qt_opengl_renderer import QtMultiverseRenderer
        import inspect

        # 檢查 shader 是否包含 region map 支援
        source = inspect.getsource(QtMultiverseRenderer)

        # 檢查 Pass 3 shader
        if "uniform sampler2D region_tex" in source:
            print("✓ Pass 3 shader has region_tex uniform")
            tests.append(("region_tex uniform", True))
        else:
            print("✗ Pass 3 shader missing region_tex uniform")
            tests.append(("region_tex uniform", False))

        if "uniform int use_region_map" in source:
            print("✓ Pass 3 shader has use_region_map uniform")
            tests.append(("use_region_map uniform", True))
        else:
            print("✗ Pass 3 shader missing use_region_map uniform")
            tests.append(("use_region_map uniform", False))

        if "currentRegion" in source:
            print("✓ Pass 3 shader has region filtering logic")
            tests.append(("region filtering logic", True))
        else:
            print("✗ Pass 3 shader missing region filtering logic")
            tests.append(("region filtering logic", False))

        # 檢查 render() 方法是否接受 region_map 參數
        if "def render(self, channels_data: List[dict], region_map: np.ndarray = None)" in source:
            print("✓ render() method accepts region_map parameter")
            tests.append(("render() region_map param", True))
        else:
            print("✗ render() method missing region_map parameter")
            tests.append(("render() region_map param", False))

        # 檢查 region texture 創建
        if "self.region_tex = glGenTextures(1)" in source:
            print("✓ Region texture allocated")
            tests.append(("region texture creation", True))
        else:
            print("✗ Region texture not allocated")
            tests.append(("region texture creation", False))

        # 檢查 region texture 上傳
        if "glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, self.render_height," in source and \
           "GL_RED, GL_UNSIGNED_BYTE, self.region_map_data)" in source:
            print("✓ Region texture upload implemented")
            tests.append(("region texture upload", True))
        else:
            print("✗ Region texture upload not implemented")
            tests.append(("region texture upload", False))

        # 檢查 use_region_map uniform 設定
        if "glUniform1i(glGetUniformLocation(self.pass3_program, b\"use_region_map\"), self.use_region_map)" in source:
            print("✓ use_region_map uniform set correctly")
            tests.append(("use_region_map uniform set", True))
        else:
            print("✗ use_region_map uniform not set")
            tests.append(("use_region_map uniform set", False))

    except Exception as e:
        print(f"✗ Error checking Qt OpenGL Renderer: {e}")
        import traceback
        traceback.print_exc()
        tests.append(("Qt OpenGL Renderer", False))

    return tests


def check_controller():
    """檢查 Controller 的 region mode 整合"""
    print("\n" + "=" * 60)
    print("3. CHECKING CONTROLLER")
    print("=" * 60)

    tests = []

    try:
        from vav.core.controller import VAVController
        import inspect

        source = inspect.getsource(VAVController)

        # 檢查 region rendering 屬性
        if "self.use_region_rendering = False" in source:
            print("✓ use_region_rendering attribute exists")
            tests.append(("use_region_rendering", True))
        else:
            print("✗ use_region_rendering attribute missing")
            tests.append(("use_region_rendering", False))

        if "self.region_mode = 'brightness'" in source:
            print("✓ region_mode attribute exists")
            tests.append(("region_mode", True))
        else:
            print("✗ region_mode attribute missing")
            tests.append(("region_mode", False))

        # 檢查 region mapper 初始化
        if "self.region_mapper = ContentAwareRegionMapper(" in source:
            print("✓ ContentAwareRegionMapper initialized")
            tests.append(("region_mapper init", True))
        else:
            print("✗ ContentAwareRegionMapper not initialized")
            tests.append(("region_mapper init", False))

        # 檢查 region map 生成
        if "region_map = self.region_mapper.create_brightness_based_regions(input_frame)" in source:
            print("✓ Region map generation (brightness) implemented")
            tests.append(("brightness region map", True))
        else:
            print("✗ Brightness region map generation missing")
            tests.append(("brightness region map", False))

        # 檢查 render() 調用傳遞 region_map
        if "rendered_rgb = self.renderer.render(channels_data, region_map=region_map)" in source:
            print("✓ region_map passed to renderer")
            tests.append(("region_map passed", True))
        else:
            print("✗ region_map not passed to renderer")
            tests.append(("region_map passed", False))

        # 檢查 API 方法
        if "def enable_region_rendering(self, enabled: bool):" in source:
            print("✓ enable_region_rendering() method exists")
            tests.append(("enable_region_rendering()", True))
        else:
            print("✗ enable_region_rendering() method missing")
            tests.append(("enable_region_rendering()", False))

        if "def set_region_mode(self, mode: str):" in source:
            print("✓ set_region_mode() method exists")
            tests.append(("set_region_mode()", True))
        else:
            print("✗ set_region_mode() method missing")
            tests.append(("set_region_mode()", False))

    except Exception as e:
        print(f"✗ Error checking Controller: {e}")
        import traceback
        traceback.print_exc()
        tests.append(("Controller", False))

    return tests


def check_gui():
    """檢查 GUI 的 region mode 控制"""
    print("\n" + "=" * 60)
    print("4. CHECKING GUI")
    print("=" * 60)

    tests = []

    try:
        from vav.gui.compact_main_window import CompactMainWindow
        import inspect

        source = inspect.getsource(CompactMainWindow)

        # 檢查 Region Map checkbox
        if "self.region_rendering_checkbox = QCheckBox(\"Region Map\")" in source:
            print("✓ Region Map checkbox exists")
            tests.append(("Region Map checkbox", True))
        else:
            print("✗ Region Map checkbox missing")
            tests.append(("Region Map checkbox", False))

        # 檢查事件處理
        if "def _on_region_rendering_toggle(self, state: int):" in source:
            print("✓ _on_region_rendering_toggle() handler exists")
            tests.append(("region toggle handler", True))
        else:
            print("✗ _on_region_rendering_toggle() handler missing")
            tests.append(("region toggle handler", False))

        # 檢查是否調用 controller API
        if "self.controller.enable_region_rendering(enabled)" in source:
            print("✓ GUI calls enable_region_rendering()")
            tests.append(("enable_region_rendering() call", True))
        else:
            print("✗ GUI doesn't call enable_region_rendering()")
            tests.append(("enable_region_rendering() call", False))

        if "self.controller.set_region_mode('brightness')" in source:
            print("✓ GUI sets region mode to brightness")
            tests.append(("set_region_mode() call", True))
        else:
            print("✗ GUI doesn't set region mode")
            tests.append(("set_region_mode() call", False))

    except Exception as e:
        print(f"✗ Error checking GUI: {e}")
        import traceback
        traceback.print_exc()
        tests.append(("GUI", False))

    return tests


def check_content_aware_regions():
    """檢查 ContentAwareRegionMapper 實作"""
    print("\n" + "=" * 60)
    print("5. CHECKING CONTENT AWARE REGIONS")
    print("=" * 60)

    tests = []

    try:
        from vav.visual.content_aware_regions import ContentAwareRegionMapper
        import inspect

        source = inspect.getsource(ContentAwareRegionMapper)

        # 檢查 brightness-based regions
        if "def create_brightness_based_regions(self, frame: np.ndarray) -> np.ndarray:" in source:
            print("✓ create_brightness_based_regions() method exists")
            tests.append(("brightness regions", True))
        else:
            print("✗ create_brightness_based_regions() method missing")
            tests.append(("brightness regions", False))

        # 檢查其他 region modes
        mode_methods = {
            'color': 'create_color_based_regions',
            'quadrant': 'create_quadrant_regions',  # Note: no "_based" suffix
            'edge': 'create_edge_based_regions'
        }
        for mode, method_name in mode_methods.items():
            if f"def {method_name}(" in source:
                print(f"✓ {method_name}() method exists")
                tests.append((f"{mode} regions", True))
            else:
                print(f"✗ {method_name}() method missing")
                tests.append((f"{mode} regions", False))

        # 檢查返回類型
        if "return self.region_map" in source:
            print("✓ Methods return region_map")
            tests.append(("region_map return", True))
        else:
            print("✗ Methods don't return region_map")
            tests.append(("region_map return", False))

    except Exception as e:
        print(f"✗ Error checking ContentAwareRegionMapper: {e}")
        import traceback
        traceback.print_exc()
        tests.append(("ContentAwareRegionMapper", False))

    return tests


def generate_summary(all_tests):
    """生成測試摘要"""
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    total = len(all_tests)
    passed = sum(1 for _, result in all_tests if result)
    failed = total - passed

    print(f"\nTotal checks: {total}")
    print(f"Passed: {passed} ✓")
    print(f"Failed: {failed} ✗")
    print(f"Success rate: {passed/total*100:.1f}%")

    if failed > 0:
        print("\nFailed checks:")
        for name, result in all_tests:
            if not result:
                print(f"  ✗ {name}")

    print("\n" + "=" * 60)
    if failed == 0:
        print("✓ ALL CHECKS PASSED - Code implementation is COMPLETE")
        print("  GPU Region Mode is ready for functional testing")
    elif failed <= 3:
        print("⚠ MINOR ISSUES DETECTED - Review failed checks")
        print("  Most functionality should work correctly")
    else:
        print("✗ MAJOR ISSUES DETECTED - Implementation incomplete")
        print("  Fix failed checks before functional testing")
    print("=" * 60)

    return failed == 0


def main():
    """主驗證流程"""
    print("GPU Region Mode - Code Verification")
    print("Checking implementation completeness\n")

    all_tests = []

    # 1. Imports
    all_tests.extend(check_imports())

    # 2. Qt OpenGL Renderer
    all_tests.extend(check_qt_opengl_renderer())

    # 3. Controller
    all_tests.extend(check_controller())

    # 4. GUI
    all_tests.extend(check_gui())

    # 5. Content Aware Regions
    all_tests.extend(check_content_aware_regions())

    # Generate summary
    success = generate_summary(all_tests)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
