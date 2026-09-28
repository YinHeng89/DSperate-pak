# DSperate 上游（beebono/DSperate）汉化可行性评估

- 评估日期：2026-09-28
- 上游仓库：`https://github.com/beebono/DSperate.git`
- 上游 HEAD：`ce8fce3`（2026-09-26），tag `v3.0.0` = `1b76c35`
- 本地 pin：`v2.1.1` = `baec965`（2026-09-19），见 `standalone/upstream.lock.json`

---

## 一、结论速览

**上游没有，而且短期看不会做菜单多语言。** 但它留下了三件对你极有价值的东西：一条**显式的「非 ASCII 显示不出来我认了」的决定**、一套**作者自己写的中文字体子集化工具**，以及一份**已经提交进仓库的 WenQuanYi Micro Hei + 中文字表**。

所以「更合理地添加汉化提交」的答案不是把 0006–0012 那 7 个补丁往上游推，而是**把汉化重构成上游形态的 i18n 层**，用 3 个独立提交、按上游的工具链和验收标准提出去。同时必须认清：上游改动量已经把当前补丁推向 v3.0.0 的悬崖边。

| 维度 | 结论 |
| --- | --- |
| i18n 框架 | **不存在**。无 gettext / .po / .mo / 翻译表 / `tr()` |
| UI 语言设置 | **不存在**。只有 `[user] language`（喂给游戏的固件语言） |
| 字体 | 5x7 ASCII 位图，62 字形（0x20–0x61），CJK 一律画 `?` |
| 贡献指引 | **无** CONTRIBUTING，README 零处提及 translation/i18n/localization |
| CJK 实际落地位置 | 只有 DSi 固件字体（`--region china`），服务游戏、不服务菜单 |
| TrueType 光栅化库 | **未 vendor**，上游 CMake 不引用任何字体文件/依赖 |

---

## 二、上游现状扫描（证据清单）

### 2.1 明面上的空白

| 项目 | 上游实际状态 | 位置 |
| --- | --- | --- |
| gettext / .po / .mo | 无 | 全仓检索无命中 |
| 翻译函数（`tr()` 之类） | 无 | 同上 |
| UI 语言配置项 | 无 | `src/frontend/sdl/settings.cpp` 的 `kLanguage[]` 是**游戏固件语言**，不是菜单语言 |
| 菜单可见文本 | 全部硬编码英文大写字面量 | `menu.cpp` 83 条唯一字符串 |
| 设置页文本 | 全部硬编码 | `settings.cpp` ≈200 条 |
| 贡献指南 | 无。`pull_request` 只跑 CI | `.github/workflows/ci.yml` |
| 字体定义 | 5x7 位图，`glyph()` 只映射 0x20–0x61 | `src/frontend/sdl/menu.h:47` |

### 2.2 `[user] language` 是陷阱，不是利好

```cpp
// src/frontend/sdl/settings.cpp:42
const Choice kLanguage[] = {{"0","JAPANESE"},{"1","ENGLISH"},{"2","FRENCH"},
                            {"3","GERMAN"},{"4","ITALIAN"},{"5","SPANISH"}};
// src/frontend/sdl/config.cpp:173 注释
// language = 1    # 0 Japanese, 1 English, ... (DSi: 6 Chinese, 7 Korean)
```

它一路流到 `freebios.h` / `firmware_gen.cpp` / `dsi_nand_synth.cpp`，最终写进**生成的 NDS/DSi 固件**，决定**游戏**用什么语言启动。它跟 DSperate 自己的菜单没有任何关系。

**别用这个键。** 本地 pak 的 `ui.language` 是 0007 自建的，名字恰好安全；将来上游若要加真 UI 语言，大概率也不会复用 `user.language`。

---

## 三、三条「代码迹象」的判读

### 3.1 真信号① `888437b` — UI 的 UTF-8 ASCII 兜底（**在 v2.1.1 内**）

```
commit 888437b  2026-09-10  ui: fallback to ASCII for UTF-8 characters
src/frontend/sdl/menu.cpp | 51 +++++-
```

```cpp
// menu.cpp —— 「Text arrives as UTF-8 but the font is ASCII ... anything else draws '?'」
char next_char(const char*& p) {
  /* UTF-8 解码 */
  if (cp >= 0xC0 && cp <= 0xFF) return kLatin1[cp - 0xC0];
  if (cp >= 0x100 && cp <= 0x17F) return kLatinA[cp - 0x100];
  return '?';                       // CJK 在此处变成问号
}
```

配套测试（已进 `v2.1.1`，也就是你本地 pin 的版本）：

```cpp
// tests/menu_test.cpp::test_utf8_folds_to_ascii_glyphs
draw_text(..., "\xE3\x81\x82");   // あ
// 与 draw_text(..., "?") 逐像素相等
```

**判读：这是最强的负面信号，不是正面信号。** 作者是在 RetroAchievements 成就名真的带重音符号（"Ōkamiden"、Été、Š）之后，专门写了一个 UTF-8 解码器，然后**刻意选择「折叠到拉丁基字，其余画 `?`」**，而不是做多语言。同一提交还把 `text_width()` 从「按字节」改成「按字形」，理由是 `Ōkamiden` 会被算成 9 个字形宽。也就是说：**作者想到了国际化文本，量了它的宽度，然后决定不支持 CJK，并把决定写进了测试。**

### 3.2 真信号② `ca65833` — 中文/韩文系统字体表（**在 v2.1.1 内**）

```
commit ca65833  2026-09-13  dsi: Chinese and Korean system font tables for the hand-off
tools/make_dsi_font.py --region china|korea
src/core/io/dsi_font/{TWLFontTable-cn.dat, TWLFontTable-kr.dat, LICENSE-WenQuanYi-MicroHei.txt, ...}
```

要点（该文件 docstring 原文）：

- 栅格化依赖 **Noto Sans（SIL OFL 1.1）+ WenQuanYi Micro Hei（GPL-3+ with font exception）**；
- 中文取 **GB 2312** 字符集，韩文取 **KS X 1001 去汉字**，分别 7848 / 3679 字形；
- 输出 Nitro 字体 16x21 / 12x16 / 10x12，DSi 反向 LZ 压缩。

**判读：这是「上游会支持中文」最有力的证据，但作用域是游戏固件。** 不过它给你三件可直接复用的东西：

1. 一条现成的**「开源中文字体 → 位图子集 → 打包进二进制」**工具链（`Pillow` + `fontTools`，已在作者依赖里）；
2. **已在仓库内的 WenQuanYi Micro Hei 许可文件与字形源**（`src/core/io/dsi_font/LICENSE-WenQuanYi-MicroHei.txt`），汉化中文菜单时许可链路不用重新论证；
3. 作者的口味证明——他愿意为中文专门造字体表。

### 3.3 真信号③ `a1f3d83` — DS Options 页的字符编辑器（**在 v2.1.1 内**）

`[user]` 昵称/留言可编辑，`[user] language` 可选。但字符表强制 ASCII，理由是「固件把一个字节当 UTF-16 单元写」。

**判读：玩家写中文昵称会被静默写坏。** 又一个「已知限制，未解决」而非「待办」。

### 3.4 假信号（容易误读的两处）

| 命中 | 真实含义 |
| --- | --- |
| 15 万行里大量 `translation` | 全是 JIT 术语（代码翻译），跟自然语言无关 |
| `nds.cpp:160` `UTF-16 firmware string` | 只是从固件里抽出昵称/留言 |
| `rcheevos/rhash/hash.c` 的 `CP_UTF8` | 第三方库的 Windows 路径转换 |

---

## 四、版本差距与汉化补丁的重放风险

上游一周内从 pin 的 `v2.1.1` 走到 `v3.0.0`，且 `v2.1.1..v3.0.0` 对汉化依赖文件是**重写级**改动：

| 文件 | 新增行 | 删除行 |
| --- | --- | --- |
| `src/frontend/sdl/main.cpp` | 734 | 1536 |
| `src/frontend/sdl/display.cpp` | 341 | 435 |
| `src/frontend/sdl/input.cpp` | 253 | 156 |
| `src/frontend/sdl/menu.cpp` | 172 | 357 |
| `src/frontend/sdl/menu.h` | 100 | 166 |
| `src/frontend/sdl/settings.cpp` | 28 | 91 |

本地汉化补丁体量（`standalone/patches/`，全部锚在 v2.1.1 行号）：

| 补丁 | 行数 | 内容 |
| --- | --- | --- |
| 0006 | 48,555 | `cjk_font.cpp/.h` + 内嵌 stb_truetype + WenQuanYi 子集 |
| 0008 | 83,496 | CJK 绘制路径与字形度量 |
| 0007 | 1,172 | `i18n.h` + `ui.language` |
| 0009 / 0010 / 0012 | 1,210 | `tr_text()` 接管剩余英文行 |
| 0001–0005 / 0011 | — | 功能补丁，与汉化无关 |
| **合计** | **≈136,600** | 其中 7 个是汉化 |

`v3.0.0` 还动了菜单页面的行高亮灰显、layout 的 screen gap 与 integer scale——这三项直接影响 `Metrics` 的行高/度量，也就是中文行适配所依赖的那套参数。**结论：v3.0.0 之后重放 0006/0008 的成本会显著高于现在，越晚动越贵。**

---

## 五、推荐路径

### 方案 A（推荐）：把汉化重构成「上游形态的 i18n 层」，分 3 个提交提出去

**为什么值得。** pak 现在 12 个补丁里 7 个是汉化，每次上游发版都要重放一次，且 CJK 实现大量依赖 Leaf 侧的 `ui.language` 约定（README 明确写了「刻意不是 console language」）。把 i18n 沉进上游，pak 就能收敛回 5 个功能补丁，一劳永逸。

**提交 1 — 语言框架（先合，风险最低）**

```
menu: a tr() table and an interface language setting
```

- 新增 `src/frontend/sdl/i18n.h` / `i18n.cpp`，结构照搬本地 0007 的 `tr_text()`：每帧由 `Menu::draw` 从配置读一次语言，绘制与测宽路径统一经 `tr_text()`，**调用点零改动**；
- 配置键用 `ui.language`（沿用 pak 已有键，玩家零迁移、零配置变化）；
- 首个 PR **只翻译根页那批行**（`SAVE STATE` / `LOAD STATE` / `STATE SLOT` / `RESUME` / `RESTART REQUIRED` / `QUIT`），英文作默认；
- 位置建议放在 `Setting` 表内，与 `kLanguage` 并列但**不得同名**。

**提交 2 — CJK 字形（最硬的一块）**

```
font: a WenQuanYi Micro Hei bitmap subset for CJK rows
```

- **不要自带 stb_truetype**——上游没 vendor 任何光栅化库。走静态位图子集，与 5x7 ASCII 同一思路：Pillow 栅格化 WenQuanYi Micro Hei，按 GB/T 2312 一级字库取常用字（约 3000 字，12x12），生成 `cjk_glyphs.h`；
- 许可沿用上游已有的 `src/core/io/dsi_font/LICENSE-WenQuanYi-MicroHei.txt`（GPL-3+ font exception）与 `LICENSE-NotoSans-OFL-1.1.txt`；
- 与 ASCII 路径统一「字形宽度」度量，保证中英混排行等高（README 里 pak 已经实现过一次）。

**提交 3 — 测试与文档（缺了会被要求补）**

```
tests: every row is drawn in the language it was translated into
```

- 仿 `tests/menu_test.cpp::test_utf8_folds_to_ascii_glyphs` 写 `test_zh_rows()`：字符串双向配对、逐页逐行断言语言、断言 CJK 行与拉丁行等高；
- README 在 `### Features` 下补一节说明界面语言与中文字体子集——作者 README 极详尽，不补一定被打回。

**上游验收门槛（不写清楚 PR 大概率挂）**

| 门槛 | 要求 |
| --- | --- |
| SPDX 头 | `// SPDX-License-Identifier: GPL-3.0-or-later`（上游每个 .cpp 都有，0006 也遵守） |
| PGO 严格模式 | CI 的 arm64 任务开 `DSPERATE_PGO_STRICT=ON`，新函数会刷 `control flow of function ... changed` 警告。**同一 PR 内必须用 `tools/pgo_refresh.sh` 刷新 profile**（作者自己在 3.0.0 前刚做 `e398230` / `d17a3a8`） |
| CI | `ctest --preset host` 必须全绿；`tools/gen_example_configs.sh && git diff --exit-code configs/default.ini` 必须无差异 |
| 提交信息 | 按作者段式：**一段「是什么」+ 一段「为什么」**；`Co-Authored-By:` 行照旧（他每条都有） |

**风险。** beebono 单人维护、无 CONTRIBUTING，话题高度集中在 JIT / GPU / DSi；作者有与 AI 协作的明确习惯（`Co-Authored-By: Claude Opus 5`），对「结构清晰的小改动」接受度通常高于「大功能」。PR 滞留下的兜底见方案 B/C。

### 方案 B（次选）：先提一个小而零风险的增量，建立上游信任

拿不到上面那套大改动的耐心时，从这类问题里挑一个提：

- `[user]` 昵称/留言若写入非 ASCII，当前会**静默写坏**；改成「拒绝并提示」或按 `[user] language` 决定可输入字符集；
- RA 标题里无法折叠到拉丁基字的 CJK，当前画成 `?`；给一个可见的替代标记（而不是无信息量的问号）。

这类改动自包含、可测、不碰字体，被直接合并的概率远高于一个完整汉化层。

### 方案 C（不推荐）：整个汉化当一个上游大 PR 推

0006 + 0008 已 13 万行，作者的 PGO + ctest 流程会被拖垮，且 pak 的 CJK 实现绑定 Leaf 约定的 `ui.language`，上游未必想引入第二个语言键。**直接推的结果几乎必然是长期挂着。**

---

## 六、一句话建议

**别把补丁往上游搬，把 i18n 按上游的规格造出来，分 3 个提交提。** 顺序是：框架先行、字体随后、测试与文档收尾——而动手窗口就在现在，v3.0.0 已经把重放成本抬起来了。
