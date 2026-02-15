# buildskill

根据运行时命令行提供的 GitHub 仓库，下载该仓库到本项目的 `git` 子目录下，分析项目代码、配置文件和提示词，并转换为同名 Cursor Skill 文件。

## 功能

- **克隆仓库**: 支持 `https://github.com/owner/repo`、`owner/repo`、SSH 等格式
- **智能分析**: 解析 README、package.json、pyproject.toml 等配置文件
- **提示词提取**: 识别项目中的 system/user/assistant 提示词
- **Skill 生成**: 输出符合 Cursor Skill 规范的 `SKILL.md`

## 安装

```bash
cd buildskill
pip install -e .
```

或直接安装依赖后运行模块：

```bash
pip install GitPython
python -m buildskill.main <github-repo>
```

## 用法

```bash
# 基本用法
buildskill https://github.com/owner/repo

# 简写格式
buildskill owner/repo

# 指定输出目录
buildskill owner/repo --output ./my-skills

# 若目录已存在则强制重新克隆
buildskill owner/repo --force

# 完整克隆（默认浅克隆）
buildskill owner/repo --full-clone

# 提示词库模式：为每个提示词生成独立 Skill（如 Guro）
buildskill owner/repo --prompt-library
buildskill --from-path ./git/Guro --prompt-library -o ./output/guro
```

## 输出结构

```
buildskill/
├── git/                    # 克隆的仓库
│   └── <repo-name>/
├── output/                 # 生成的 Skill
│   └── <skill-name>/
│       └── SKILL.md
└── ...
```

## 分析内容

| 类型 | 说明 |
|------|------|
| README | 提取项目描述、功能列表、用法 |
| package.json | 项目名、描述、脚本 |
| pyproject.toml | Python 项目元数据 |
| 提示词文件 | 文件名含 prompt/system 的文件 |
| 技术栈 | 根据配置文件自动检测 |

## 提示词库模式 (--prompt-library)

针对 [Guro](https://github.com/is-leeroy-jenkins/Guro) 等 prompt library 仓库，为 **每个提示词** 生成独立的 Skill 文件：

- 扫描 `prompts/`、`prompts/xml/` 等目录
- 每个 `.md`/`.txt` 提示词 → 一个 `guro-{名称}/SKILL.md`
- 支持 `<role>` 与 `### Role` 两种格式

## 文档分析模式 (analyze)

对指定目录下的文档进行**三智能体元知识分析**，生成可指导同类文档写作的 Skill 文件。需配置 Gemini API Key。

### 三智能体架构

| 智能体 | 职责 | 输出 |
|--------|------|------|
| **Agent1** | 文档结构与文体分析（一级规范） | level1/*_L1.md |
| **Agent2** | 文档元逻辑与认知结构（二级元语义） | level2/*_L2.md |
| **Agent3** | 写作质量评审专家，8 维度打分 | scores/*_score.md |

### Agent3 评审 8 维度（权重 100%）

1. 事实准确性 20% | 2. 来源可信度 15% | 3. 分析深度与逻辑性 20% | 4. 客观性与偏见控制 15%  
5. 全面性与覆盖度 10% | 6. 时效性与前瞻性 10% | 7. 清晰度与结构化 5% | 8. 实用价值与洞察力 5%

综合评分 = 各维度加权平均，四舍五入至 0.5。

### 流程

1. Agent1 → Level1 一级规范分析  
2. Agent2 → Level2 二级元语义分析  
3. Agent3 → 结合源文档与 L1/L2 进行 8 维度打分  
4. **汇总归纳**：融入评分，重点学习高分文档与高得分维度，提炼写作规范  
5. **Skill 生成**：转为写作指导 Skill（含质量标杆）

### API Key 配置（优先级从高到低）

1. **`.env` 文件（推荐）**：在项目根目录或当前工作目录创建 `.env`，内容：
   ```
   GEMINI_API_KEY=your-key
   ```
2. 环境变量：`GEMINI_API_KEY` 或 `GOOGLE_API_KEY`
3. 命令行：`--api-key YOUR_KEY`

### 用法

```bash
# 分析文档目录（默认 gemini-2.5-pro，支持多模态）
buildskill analyze ./docs

# 指定模型
buildskill analyze ./my_papers -m gemini-2.5-flash

# 命令行传入 API Key
buildskill analyze ./docs --api-key YOUR_KEY
```

### 输出

所有结果保存在文档目录下的 `_analysis/` 子目录：

```
docs/
├── paper1.md
├── paper2.md
└── _analysis/
    ├── level1/          # Agent1 一级规范分析
    │   ├── paper1_L1.md
    │   └── paper2_L1.md
    ├── level2/          # Agent2 二级元语义分析
    │   ├── paper1_L2.md
    │   └── paper2_L2.md
    ├── scores/          # Agent3 评审结果
    │   ├── paper1_score.md
    │   ├── paper2_score.md
    │   └── ranking.md   # 评分排序表
    ├── summary.md       # 汇总归纳（融入评分）
    └── SKILL.md         # 写作指导 Skill
```

支持的文档格式：
- 文本：`.md`、`.txt`、`.rst`
- Word：`.docx`（需 `pip install python-docx`）
- PDF：`.pdf`（多模态，直接传 API）
- 图片：`.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`（多模态）

## License

MIT
