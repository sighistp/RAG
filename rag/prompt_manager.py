"""Prompt 版本管理器 — YAML 文件化、版本化、模板变量。"""

from __future__ import annotations

import os

import yaml


class PromptManager:
    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = prompts_dir

    def _load_all_versions(self, name: str) -> list[dict]:
        """加载指定 prompt 的所有版本文件。"""
        versions = []
        if not os.path.isdir(self.prompts_dir):
            raise FileNotFoundError(f"Prompts directory not found: {self.prompts_dir}")
        for fname in os.listdir(self.prompts_dir):
            if fname.endswith(".yaml") and fname.startswith(name):
                path = os.path.join(self.prompts_dir, fname)
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and data.get("name") == name:
                        versions.append(data)
        if not versions:
            raise FileNotFoundError(f"Prompt '{name}' not found in {self.prompts_dir}")
        return sorted(versions, key=lambda x: x.get("version", 0))

    def get(self, name: str, version: int | None = None) -> str:
        """加载 prompt 模板。version=None 时加载最新版本。"""
        all_versions = self._load_all_versions(name)
        if version is not None:
            for v in all_versions:
                if v.get("version") == version:
                    return v["template"]
            raise ValueError(f"Version {version} not found for prompt '{name}'")
        return all_versions[-1]["template"]

    def render(self, prompt_name: str, version: int | None = None, **kwargs) -> str:
        """加载并渲染模板变量。"""
        template = self.get(prompt_name, version=version)
        return template.format(**kwargs)

    def list_versions(self, name: str) -> list[dict]:
        """列出 prompt 的所有版本信息。"""
        all_versions = self._load_all_versions(name)
        result = []
        for v in reversed(all_versions):
            changelog = v.get("changelog", [{}])
            latest = changelog[0] if changelog else {}
            result.append(
                {
                    "version": v.get("version"),
                    "date": latest.get("date", ""),
                    "change": latest.get("change", ""),
                }
            )
        return result
