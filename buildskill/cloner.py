"""
GitHub 仓库克隆模块
将指定仓库克隆到项目的 git 子目录下
"""

import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

from git import Repo


def parse_github_url(url: str) -> tuple[str, str] | None:
    """
    解析 GitHub URL 获取 owner 和 repo 名称
    支持格式:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - git@github.com:owner/repo.git
    """
    # HTTPS 格式
    https_match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url, re.IGNORECASE
    )
    if https_match:
        owner, repo = https_match.groups()
        return owner, repo.rstrip(".git")

    # SSH 格式
    ssh_match = re.match(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if ssh_match:
        owner, repo = ssh_match.groups()
        return owner, repo.rstrip(".git")

    # 简写格式 owner/repo
    short_match = re.match(r"^([^/]+)/([^/]+)$", url.strip())
    if short_match:
        return short_match.groups()

    return None


def normalize_repo_url(url: str) -> str:
    """将各种格式转换为标准 HTTPS URL"""
    parsed = parse_github_url(url)
    if parsed:
        owner, repo = parsed
        return f"https://github.com/{owner}/{repo}.git"
    return url


def clone_repo(
    repo_url: str,
    target_dir: Path,
    *,
    force: bool = False,
    depth: int | None = 1,
    log=None,
) -> Path:
    """
    克隆 GitHub 仓库到目标目录

    Args:
        repo_url: GitHub 仓库 URL 或 owner/repo 格式
        target_dir: 克隆目标目录（项目根目录下的 git/ 子目录）
        force: 若目录已存在，是否删除后重新克隆
        depth: 浅克隆深度，None 表示完整克隆

    Returns:
        克隆后的仓库路径

    Raises:
        ValueError: URL 格式无效
        Exception: 克隆失败
    """
    log = log or (lambda x: None)
    parsed = parse_github_url(repo_url)
    if not parsed:
        raise ValueError(f"无效的 GitHub URL: {repo_url}")

    owner, repo_name = parsed
    repo_path = target_dir / repo_name

    log(f"  仓库: {owner}/{repo_name}")
    log(f"  目标: {repo_path}")

    if repo_path.exists():
        if force:
            shutil.rmtree(repo_path)
        else:
            raise FileExistsError(
                f"目录已存在: {repo_path}\n"
                "使用 --force 参数可删除后重新克隆"
            )

    url = normalize_repo_url(repo_url)
    clone_kwargs = {"url": url, "to_path": str(repo_path)}
    if depth is not None:
        clone_kwargs["depth"] = depth

    try:
        log("  正在克隆...")
        Repo.clone_from(**clone_kwargs)
        log("  克隆完成")
    except Exception as e:
        err = str(e)
        if "Repository not found" in err or "404" in err:
            raise FileNotFoundError(
                f"仓库不存在或无权访问: {owner}/{repo_name}\n  {e}"
            ) from e
        if "Authentication failed" in err or "403" in err:
            raise PermissionError(
                f"认证失败，请检查网络或使用 HTTPS/SSH 凭据\n  {e}"
            ) from e
        raise
    return repo_path
