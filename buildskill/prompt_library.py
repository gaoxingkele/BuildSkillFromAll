"""
提示词库模式：为每个提示词文件生成独立的 Skill
支持 Guro 等 prompt library 仓库结构
"""

import re
from pathlib import Path
from dataclasses import dataclass

from .skill_generator import _sanitize_skill_name, _sanitize_description


# 提示词文件搜索路径（相对于仓库根）
PROMPT_DIRS = ["prompts", "prompts/xml", "prompts/txt"]

# 支持的提示词文件扩展名
PROMPT_EXTENSIONS = {".md", ".txt"}


@dataclass
class PromptFile:
    """单个提示词文件分析结果"""

    name: str  # 如 AcademicWriter
    path: Path
    content: str
    role_summary: str = ""
    instructions_summary: str = ""


def _read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_role_summary(content: str) -> str:
    """从 <role> 标签或 ### Role 标题提取角色描述，用于 description"""
    # XML 格式: <role>...</role>
    match = re.search(r"<role>\s*(.+?)</role>", content, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
        first_line = text.split("\n")[0].strip().strip("-* ")
        return first_line[:300] if first_line else ""

    # Markdown 格式: ### Role 或 ### 🤖 Role
    match = re.search(r"###\s*(?:🤖\s*)?Role\s*\n(.+?)(?=\n###|\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
        first_line = text.split("\n")[0].strip().strip("-* ")
        return first_line[:300] if first_line else ""
    return ""


def _extract_instructions_summary(content: str) -> str:
    """从 <instructions> 或 ### Instructions 提取简要说明"""
    # XML 格式
    match = re.search(
        r"<instructions>\s*(.+?)</instructions>", content, re.DOTALL | re.IGNORECASE
    )
    if match:
        text = match.group(1).strip()
        lines = [l.strip().strip("-*123456789. ") for l in text.split("\n")[:3] if l.strip()]
        return " ".join(lines)[:200] if lines else ""

    # Markdown 格式: ### Instructions（仅取第一段，避免混入子标题）
    match = re.search(
        r"###\s*📝?\s*Instructions?\s*\n(.+?)(?=\n###\s|\n##\s|\Z)", content, re.DOTALL | re.IGNORECASE
    )
    if match:
        text = match.group(1).strip()
        # 仅取前 2-3 行实质内容，跳过空行和子标题
        lines = []
        for line in text.split("\n")[:5]:
            stripped = line.strip().strip("-*123456789. ")
            if stripped and not stripped.startswith("###") and len(stripped) > 5:
                lines.append(stripped)
                if len(lines) >= 2:
                    break
        return " ".join(lines)[:200] if lines else ""
    return ""


def find_prompt_files(repo_path: Path) -> list[PromptFile]:
    """
    在仓库中查找所有提示词文件
    支持 prompts/、prompts/xml/、prompts/*.md 等结构
    """
    found: list[PromptFile] = []
    seen_names: set[str] = set()

    # 1. 检查已知的提示词目录
    for dir_name in PROMPT_DIRS:
        prompt_dir = repo_path / dir_name
        if not prompt_dir.exists():
            continue
        for ext in PROMPT_EXTENSIONS:
            for path in prompt_dir.glob(f"*{ext}"):
                if not path.is_file():
                    continue
                name = path.stem
                # 避免重复（如 xml 和根目录都有同名文件）
                if name in seen_names:
                    continue
                seen_names.add(name)
                content = _read_file_safe(path)
                if not content.strip():
                    continue
                role = _extract_role_summary(content)
                instructions = _extract_instructions_summary(content)
                found.append(
                    PromptFile(
                        name=name,
                        path=path,
                        content=content,
                        role_summary=role,
                        instructions_summary=instructions,
                    )
                )

    # 2. 若未找到，尝试递归搜索 prompts 相关目录
    if not found and (repo_path / "prompts").exists():
        for path in (repo_path / "prompts").rglob("*"):
            if not path.is_file() or path.suffix not in PROMPT_EXTENSIONS:
                continue
            name = path.stem
            if name in seen_names:
                continue
            seen_names.add(name)
            content = _read_file_safe(path)
            if not content.strip():
                continue
            role = _extract_role_summary(content)
            instructions = _extract_instructions_summary(content)
            found.append(
                PromptFile(
                    name=name,
                    path=path,
                    content=content,
                    role_summary=role,
                    instructions_summary=instructions,
                )
            )

    return sorted(found, key=lambda p: p.name.lower())


def prompt_to_skill_content(
    prompt: PromptFile,
    *,
    library_name: str = "guro",
    base_description: str = "",
) -> str:
    """
    将单个提示词文件转换为 SKILL.md 内容
    """
    skill_name = _sanitize_skill_name(f"{library_name}-{prompt.name}")
    display_name = prompt.name.replace("-", " ").replace("_", " ").replace(".", " ")

    # 生成 description（从 role 提取，instructions 仅在不含子标题时追加）
    desc_parts = []
    if prompt.role_summary:
        desc_parts.append(prompt.role_summary)
    # 优先使用 role；instructions 易含列表/格式，通常不加入 description
    if base_description and not desc_parts:
        desc_parts.append(base_description)
    raw_desc = " ".join(desc_parts).strip()
    if raw_desc:
        # 补充触发词
        triggers = f" Use when user needs {display_name.replace('-', ' ')} capabilities."
        raw_desc = (raw_desc + triggers) if len(raw_desc) < 900 else raw_desc
    else:
        raw_desc = (
            f"AI persona: {display_name}. "
            f"Use when user needs {display_name.replace('-', ' ')} capabilities."
        )
    description = _sanitize_description(raw_desc)

    sections = []

    # YAML frontmatter
    sections.append(f"""---
name: {skill_name}
description: {description}
---
""")

    # 标题
    sections.append(f"# {display_name}\n")

    # 概述
    if prompt.role_summary:
        sections.append("## Role\n")
        sections.append(f"{prompt.role_summary}\n")

    # 完整提示词（供 Agent 遵循）
    sections.append("## System Prompt\n")
    sections.append("When using this skill, adopt the following persona and instructions:\n")
    sections.append("```\n")
    sections.append(prompt.content)
    sections.append("\n```\n")

    # 变量说明
    vars_found = re.findall(r"\{\{\s*(\w+)\s*\}\}", prompt.content)
    if vars_found:
        sections.append("## Variables\n")
        for v in sorted(set(vars_found)):
            sections.append(f"- `{v}`: User-provided input (replace with actual value)\n")
        sections.append("")

    return "\n".join(sections)


def generate_prompt_library_skills(
    repo_path: Path,
    output_dir: Path,
    *,
    library_name: str | None = None,
    base_description: str = "",
) -> list[Path]:
    """
    为提示词库中每个提示词生成独立 Skill

    Args:
        repo_path: 仓库根路径
        output_dir: 输出目录
        library_name: 库名前缀，默认用仓库名
        base_description: 无 role 时的默认描述

    Returns:
        生成的 SKILL.md 路径列表
    """
    lib_name = library_name or repo_path.name
    prompt_files = find_prompt_files(repo_path)

    if not prompt_files:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    for prompt in prompt_files:
        skill_name = _sanitize_skill_name(f"{lib_name}-{prompt.name}")
        skill_dir = output_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        content = prompt_to_skill_content(
            prompt,
            library_name=lib_name,
            base_description=base_description,
        )
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(content, encoding="utf-8")
        generated.append(skill_file)

    return generated
