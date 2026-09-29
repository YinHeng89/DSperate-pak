# zh_CN — 中文本地化的唯一事实来源

本目录是 DSperate-pak 中文本地化的**说明与索引**，不是字面的翻译文件存放处。

## 翻译数据在哪里

- 运行期使用的翻译表 `tr_data.inc`（zh/en 对照）和 CJK 字库 `font_cn_data.inc`
  由补丁系列 `standalone/patches/0006-chinese-localization.patch` 与
  `0008-cjk-drawing.patch` 打进 **beebono/DSperate 的源码树**，随 `make standalone`
  一同编译进二进制。它们不单独放在本仓库，以避免出现"未跟踪树 vs 幽灵目录"的分裂。
- 这些补丁的**可维护来源**是维护 fork
  [YinHeng89/DSperate](https://github.com/YinHeng89/DSperate)：
  - `main` 分支 = beebono v3.0.0 基线（`1b76c35`）；
  - `zh-menu-v3.0.0` 分支 = 全部本地改动（功能 0001-0005 + 本地化 0006-0010）的
    全量提交。每个 `standalone/patches/0001-0010` 补丁都是该分支相对 `main` 的一个切片。

## 重新生成字库 / 翻译表

- 字库由 `tools/make_menu_font.py`（在源码树内）从 WenQuanYi Micro Hei 子集生成，
  写入 `src/frontend/sdl/font_cn_data.inc`。它记录的 SOURCES 表钉死了所用字面的
  SHA-256，确保字库可复现。
- 翻译表 `tr_data.inc` 的对照条目是手维护的；新增/修改中文串后，应在 fork 的
  `zh-menu-v3.0.0` 分支改动 `src/frontend/sdl/tr_data.inc` 与 `menu.cpp` /
  `settings.cpp` 的字面量，再按"维护手册"把改动重新切回 `standalone/patches/`。

## 一致性守护

- `standalone/check-tr-coverage.py`（`make test-tr-coverage`）：检查每个字面串是否
  都在翻译表里有条目，漏译会在英文模式下画成中文。
- `standalone/check-upstream-text.py`（`make check-upstream` / `repack.sh`）：比对上游
  最新 tag 的 UI 文本与钉住的基线，新增/改动的屏幕文本会以 exit 3 拦下，避免发出没人
  翻译的串。

## 维护手册

跟随上游、重生成本地化的完整步骤见仓库根 `README.md` 的 *Source & upstreams* 一节与
`standalone/PROVENANCE.md`。
