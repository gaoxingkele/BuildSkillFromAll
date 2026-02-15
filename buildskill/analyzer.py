"""
仓库分析模块
分析代码、配置文件、提示词等，提取项目功能和用途
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field


# 需要分析的配置文件模式
CONFIG_PATTERNS = [
    "README*",
    "readme*",
    "package.json",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "*.md",
]

# 可能包含提示词的文件
PROMPT_PATTERNS = [
    "*prompt*",
    "*system*",
    "*.md",
    "*.txt",
]

# 忽略的目录
IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "vendor",
}


@dataclass
class ProjectAnalysis:
    """项目分析结果"""

    name: str
    description: str = ""
    triggers: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    config_summary: dict = field(default_factory=dict)
    prompts: list[str] = field(default_factory=list)
    key_files: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    raw_readme: str = ""


def _read_file_safe(path: Path, encoding: str = "utf-8") -> str:
    """安全读取文件，忽略编码错误"""
    try:
        return path.read_text(encoding=encoding, errors="ignore")
    except Exception:
        return ""


def _extract_from_readme(content: str) -> dict:
    """从 README 提取关键信息"""
    result = {"description": "", "features": [], "usage": ""}

    # 提取第一个标题下的描述
    desc_match = re.search(
        r"^#\s+.+?\n\n(.+?)(?=\n#|\n##|\Z)",
        content,
        re.DOTALL | re.MULTILINE,
    )
    if desc_match:
        result["description"] = desc_match.group(1).strip()[:500]

    # 提取功能列表
    for pattern in [r"[-*]\s+(.+?)(?=\n|$)", r"\d+\.\s+(.+?)(?=\n|$)"]:
        for m in re.finditer(pattern, content):
            line = m.group(1).strip()
            if len(line) > 10 and len(line) < 200:
                result["features"].append(line)

    # 截取用法部分
    usage_match = re.search(
        r"(##\s+[Uu]sage.*?)(?=\n## |\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if usage_match:
        result["usage"] = usage_match.group(1).strip()[:1000]

    return result


def _extract_from_package_json(content: str) -> dict:
    """从 package.json 提取信息"""
    try:
        data = json.loads(content)
        return {
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "scripts": list(data.get("scripts", {}).keys()),
        }
    except json.JSONDecodeError:
        return {}


def _extract_from_pyproject(content: str) -> dict:
    """从 pyproject.toml 提取信息"""
    result = {"name": "", "description": ""}
    name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
    if name_match:
        result["name"] = name_match.group(1)
    desc_match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
    if desc_match:
        result["description"] = desc_match.group(1)
    return result


def _detect_prompts(content: str, path: str) -> list[str]:
    """检测文件中的提示词内容"""
    prompts = []

    # 常见提示词模式
    patterns = [
        r'(?:system|user|assistant)\s*:\s*["\']?(.+?)["\']?(?=\n\n|\n(?:system|user|assistant)|\Z)',
        r'["\']([^"\']{50,500})["\']\s*(?:#|//).*prompt',
        r"```(?:system|prompt)\n(.+?)```",
        r"<\|(?:system|user|assistant)\|>\s*\n(.+?)(?=\n<\||\Z)",
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
            text = m.group(1).strip()
            if len(text) > 30:
                prompts.append(text[:300])

    return prompts


def _detect_tech_stack(repo_path: Path) -> list[str]:
    """检测技术栈"""
    tech = []
    if (repo_path / "package.json").exists():
        tech.append("Node.js")
    if (repo_path / "pyproject.toml").exists() or (repo_path / "setup.py").exists():
        tech.append("Python")
    if (repo_path / "Cargo.toml").exists():
        tech.append("Rust")
    if (repo_path / "go.mod").exists():
        tech.append("Go")
    if (repo_path / "requirements.txt").exists():
        tech.append("Python")
    return list(set(tech))


def analyze_repo(repo_path: Path) -> ProjectAnalysis:
    """
    分析仓库，提取功能描述和关键信息

    Args:
        repo_path: 仓库根路径

    Returns:
        ProjectAnalysis 分析结果
    """
    analysis = ProjectAnalysis(name=repo_path.name)

    # 检测技术栈
    analysis.tech_stack = _detect_tech_stack(repo_path)

    # 遍历仓库文件
    for item in repo_path.rglob("*"):
        if not item.is_file():
            continue
        rel_path = item.relative_to(repo_path)
        if any(part in IGNORE_DIRS for part in rel_path.parts):
            continue

        content = _read_file_safe(item)
        rel_str = str(rel_path)

        # 分析 README
        if rel_str.upper().startswith("README"):
            analysis.raw_readme = content
            readme_data = _extract_from_readme(content)
            if readme_data["description"] and not analysis.description:
                analysis.description = readme_data["description"]
            analysis.instructions.extend(
                f"- {f}" for f in readme_data["features"][:10]
            )
            if readme_data["usage"]:
                analysis.examples.append(readme_data["usage"])
            analysis.key_files.append(rel_str)
            continue

        # 分析 package.json
        if "package.json" == rel_str:
            data = _extract_from_package_json(content)
            analysis.config_summary["package.json"] = data
            if data.get("description") and not analysis.description:
                analysis.description = data["description"]
            if data.get("name"):
                analysis.name = data["name"]
            analysis.key_files.append(rel_str)
            continue

        # 分析 pyproject.toml
        if "pyproject.toml" == rel_str:
            data = _extract_from_pyproject(content)
            analysis.config_summary["pyproject.toml"] = data
            if data.get("description") and not analysis.description:
                analysis.description = data["description"]
            if data.get("name"):
                analysis.name = data["name"]
            analysis.key_files.append(rel_str)
            continue

        # 检测提示词文件
        if "prompt" in rel_str.lower() or "system" in rel_str.lower():
            prompts = _detect_prompts(content, rel_str)
            analysis.prompts.extend(prompts)
            if content.strip() and len(content) < 2000:
                analysis.prompts.append(content.strip()[:500])
            analysis.key_files.append(rel_str)

    # 从描述生成触发器关键词
    if analysis.description:
        words = re.findall(r"\b[a-zA-Z]{3,}\b", analysis.description)
        analysis.triggers = list(set(words))[:15]

    # 生成默认描述
    if not analysis.description:
        analysis.description = f"Tools and workflows from {analysis.name} project."

    return analysis
