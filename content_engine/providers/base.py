"""
Base provider interface for content generation.

All providers must implement this interface to be used by the orchestrator.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
import json


class ProviderType(Enum):
    """Available provider types."""
    STUB = "stub"
    CLI = "cli"
    API = "api"  # Future


@dataclass
class ProviderConfig:
    """Configuration for a provider."""
    provider_type: ProviderType
    timeout_seconds: int = 120
    max_retries: int = 2

    # CLI-specific settings
    cli_model: str = "claude"  # claude, gemini, codex
    cli_command_template: Optional[str] = None

    # Stub-specific settings
    stub_delay_ms: int = 100  # Simulated delay

    @classmethod
    def from_config(cls, config: dict) -> "ProviderConfig":
        """Create from config.yaml settings."""
        # Look for "type" key first (config.yaml format), then "provider" for legacy
        provider_str = config.get("type", config.get("provider", "stub"))
        provider_type = ProviderType(provider_str)

        return cls(
            provider_type=provider_type,
            timeout_seconds=config.get("provider_timeout", 120),
            max_retries=config.get("provider_retries", 2),
            cli_model=config.get("cli_model", "claude"),
            stub_delay_ms=config.get("stub_delay_ms", 100),
        )


@dataclass
class GenerationResult:
    """Result of a generation operation."""
    success: bool
    output_files: dict[str, Path] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output_files": {k: str(v) for k, v in self.output_files.items()},
            "artifacts": self.artifacts,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }


class ProviderError(Exception):
    """Base exception for provider errors."""
    def __init__(self, message: str, recoverable: bool = True):
        super().__init__(message)
        self.recoverable = recoverable


class ContentProvider(ABC):
    """
    Abstract base class for content generation providers.

    Providers implement the actual generation logic for each pipeline stage.
    The orchestrator calls these methods and handles state management.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._progress_callback: Optional[Callable[[str, int], None]] = None

    def set_progress_callback(self, callback: Callable[[str, int], None]):
        """
        Set a callback for progress updates.

        Callback signature: (stage_name: str, percent: int) -> None
        """
        self._progress_callback = callback

    def _report_progress(self, stage: str, percent: int):
        """Report progress to callback if set."""
        if self._progress_callback:
            self._progress_callback(stage, percent)

    @abstractmethod
    def generate_script(
        self,
        run_id: str,
        niche: str,
        style: str,
        topic: Optional[str],
        output_dir: Path,
        loop_friendly_ending: bool = False,
    ) -> GenerationResult:
        """
        Generate a script for the given configuration.

        Outputs:
        - script.txt: Plain text script (voiceover)
        - script_meta.json: Hook, body, keywords, hashtags, script_type

        Args:
            run_id: Unique identifier for this run
            niche: Content niche (motivation, fun_facts, etc.)
            style: Content style (affirming, aggressive_energy, etc.)
            topic: Optional specific topic
            output_dir: Directory to write output files

        Returns:
            GenerationResult with paths to generated files
        """
        pass

    @abstractmethod
    def regenerate_script(
        self,
        run_id: str,
        niche: str,
        style: str,
        prior_script: dict,
        feedback: Optional[str],
        output_dir: Path,
    ) -> GenerationResult:
        """
        Regenerate a script based on prior attempt and feedback.

        Args:
            run_id: Unique identifier for this run
            niche: Content niche
            style: Content style
            prior_script: Previous script artifacts
            feedback: User feedback for improvement
            output_dir: Directory to write output files

        Returns:
            GenerationResult with paths to regenerated files
        """
        pass

    @abstractmethod
    def generate_shot_list(
        self,
        run_id: str,
        script: dict,
        visual_mode: str,
        output_dir: Path,
    ) -> GenerationResult:
        """
        Generate shot list from approved script.

        Outputs:
        - shot_list.json: Structured shot list with beats
        - shot_list.md: Human-readable markdown format

        Args:
            run_id: Unique identifier for this run
            script: Approved script artifacts (hook, body, etc.)
            visual_mode: Visual generation mode (hybrid, stock, nanobanana)
            output_dir: Directory to write output files

        Returns:
            GenerationResult with paths to generated files
        """
        pass

    @abstractmethod
    def generate_visual_prompts(
        self,
        run_id: str,
        shot_list: dict,
        visual_mode: str,
        realism_mode: str,
        output_dir: Path,
    ) -> GenerationResult:
        """
        Generate NanoBanana visual prompts from shot list.

        Outputs:
        - nanobanana_prompts.txt: Copy-paste ready prompts for NanoBanana

        Args:
            run_id: Unique identifier for this run
            shot_list: Generated shot list
            visual_mode: Visual generation mode
            realism_mode: Realism level (standard, photorealistic)
            output_dir: Directory to write output files

        Returns:
            GenerationResult with paths to generated files
        """
        pass

    @abstractmethod
    def generate_stock_queries(
        self,
        run_id: str,
        shot_list: dict,
        output_dir: Path,
    ) -> GenerationResult:
        """
        Generate stock footage search queries from shot list.

        Outputs:
        - stock_queries.txt: Search queries (tight/broad/negative)

        Args:
            run_id: Unique identifier for this run
            shot_list: Generated shot list
            output_dir: Directory to write output files

        Returns:
            GenerationResult with paths to generated files
        """
        pass

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Generate text using the provider's LLM.

        This is a simpler interface for ad-hoc text generation tasks
        like prompt regeneration.

        Args:
            system_prompt: System/context prompt
            user_prompt: User query prompt

        Returns:
            Generated text string

        Note: Base implementation raises NotImplementedError.
        Subclasses should override if they support text generation.
        """
        raise NotImplementedError(
            f"Provider {self.config.provider_type.value} does not support generate_text"
        )

    def get_provider_info(self) -> dict:
        """Return provider type and configuration info."""
        return {
            "type": self.config.provider_type.value,
            "timeout_seconds": self.config.timeout_seconds,
            "max_retries": self.config.max_retries,
        }


def get_provider(config: dict) -> ContentProvider:
    """
    Factory function to get the appropriate provider.

    Args:
        config: Configuration dict with 'provider' key

    Returns:
        Configured ContentProvider instance
    """
    from .stub_provider import StubProvider
    from .cli_provider import CLIProvider

    provider_config = ProviderConfig.from_config(config)

    if provider_config.provider_type == ProviderType.STUB:
        return StubProvider(provider_config)
    elif provider_config.provider_type == ProviderType.CLI:
        return CLIProvider(provider_config)
    else:
        raise ValueError(f"Unknown provider type: {provider_config.provider_type}")
