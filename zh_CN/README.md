# zh_CN — 中文本地化的说明与索引

本目录是 DSperate-pak 中文本地化的**说明与索引**，不是字面翻译文件的存放处。

## 基准语言是英文（重要）

菜单源码里的 UI 文本**保持英文**，与上游写法一致；中文是 `tr_data.inc` 里的一层
**增量覆盖表**，以英文为键。

- 英文模式：直接绘制源码里的英文，**不查表**；
- 中文模式：由 `tr_text()` 拿英文去表里查，取出中文再绘制；
- 一个没有条目的串会保持英文，而不是画错——这正是覆盖率检查要抓的东西。

这样相对上游的 diff 很小。上游发新版后只需要两件事：

1. 重新打功能补丁（0001-0005 及 0007 的连发页）；
2. 为新增的英文串在 `tr_data.inc` 补一行中文，调用点一行都不用动。

## 翻译数据在哪里

- 运行期使用的翻译表 `tr_data.inc`（英文&rarr;中文，315 条）和 CJK 字库
  `font_cn_data.inc` 由补丁 `standalone/patches/0006-chinese-localization.patch`
  与 `0008-cjk-drawing.patch` 打进 **beebono/DSperate 的源码树**，随
  `make standalone` 一同编译进二进制。它们不单独放在本仓库，以避免出现
  "未跟踪树 vs 幽灵目录"的分裂。
- 这些补丁的**可维护来源**是维护 fork
  [YinHeng89/DSperate](https://github.com/YinHeng89/DSperate)：
  - `main` 分支 = beebono v3.0.0 基线（`1b76c35`）；
  - `zh-menu-v3.0.0` 分支 = 全部本地改动（功能 0001-0005 + 本地化 0006-0010）的
    全量提交。每个 `standalone/patches/0001-0010` 补丁都是该分支相对 `main` 的一个切片。

## 重新生成字库 / 翻译表

- 字库由 `tools/make_menu_font.py`（在源码树内）从 WenQuanYi Micro Hei 子集生成，
  写入 `src/frontend/sdl/font_cn_data.inc`。它记录的 SOURCES 表钉死了所用字面的
  SHA-256，确保字库可复现。它会扫描 `tr_data.inc`，所以**改动中文后必须重跑生成器
  并重编**，否则新字会画成 `？`。
- 翻译表 `tr_data.inc` 以英文为键。补翻译时在 fork 的 `zh-menu-v3.0.0` 分支改
  `src/frontend/sdl/tr_data.inc` 即可（源码里的英文串一般不动），再按"维护手册"
  把改动重新切回 `standalone/patches/`。

## 一致性守护

- `standalone/check-tr-coverage.py`（`make test-tr-coverage`）：检查每个英文 UI 串
  是否都在表里有中文条目；源码 `src/` 下残留中文也会失败。**这是上游发新版后要跑
  的工具**，它会列出所有还缺中文的串。
- `tests/menu_test.cpp` 的覆盖率测试（补丁 0009）：在中文模式下遍历编译后的设置表，
  逐行检查 label / note / choice 是否都有中文——这是唯一能精确回答"这一行有没有
  中文"的检查，因为源码里看不出哪个参数是标签、哪个是 ini 值。
- 运行期泄漏检查：英文模式下画出中文会计数（抓源码里漏改的中文）。反向的"中文模式
  下画出英文"在屏幕上无法与"本来就应该是英文"（ROM 名、数字）区分，因此交给上面
  两个静态检查。

## 维护手册

跟随上游、重生成本地化的完整步骤见仓库根 `README.md` 的 *Source & upstreams* 一节与
`standalone/PROVENANCE.md`。
