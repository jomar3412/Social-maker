"""
Tests for NanoBanana prompt generation.

Verifies that prompts:
- Meet minimum word count requirements
- Include all required visual fields (camera, subject, environment, lighting, negatives)
- Maintain proper structure
- Support different detail levels
"""

import pytest

from content_engine.pipeline.prompt_spec import (
    ScenePromptSpec,
    CameraSpec,
    SubjectSpec,
    EnvironmentSpec,
    LightingSpec,
    ColorStyleSpec,
    NegativeConstraints,
    OutputFormatSpec,
    ShotType,
    CameraAngle,
    CameraMovement,
    TimeOfDay,
    LightingStyle,
    PromptDetailLevel,
)
from content_engine.pipeline.nanobanana_generator import (
    NanoBananaPromptGenerator,
    generate_nanobanana_prompt,
    MIN_WORD_COUNTS,
    MAX_WORD_COUNTS,
    BEAT_PROFILES,
    VisualStrategy,
    NICHE_VISUAL_DEFAULTS,
)


class TestPromptSpec:
    """Tests for ScenePromptSpec data structures."""

    def test_camera_spec_to_prompt_text(self):
        """CameraSpec should generate descriptive prompt text."""
        camera = CameraSpec(
            shot_type=ShotType.MEDIUM_CLOSE,
            angle=CameraAngle.LOW_ANGLE,
            lens_mm=50,
            movement=CameraMovement.SLOW_PUSH,
            depth_of_field="shallow",
            framing_notes="subject centered",
        )

        text = camera.to_prompt_text()

        assert "medium close-up" in text
        assert "low angle" in text
        assert "50mm" in text
        assert "slow push-in" in text
        assert "shallow" in text
        assert "subject centered" in text

    def test_subject_spec_to_prompt_text(self):
        """SubjectSpec should include all specified details."""
        subject = SubjectSpec(
            count=1,
            subject_type="person",
            age_range="30s",
            wardrobe="dark business suit",
            facial_expression="contemplative",
            pose="standing arms crossed",
            action="looking out window",
            skin_texture="natural skin with visible pores",
        )

        text = subject.to_prompt_text()

        assert "person" in text.lower()
        assert "30s" in text
        assert "dark business suit" in text
        assert "contemplative" in text
        assert "standing arms crossed" in text
        assert "looking out window" in text
        assert "natural skin" in text

    def test_environment_spec_to_prompt_text(self):
        """EnvironmentSpec should describe the setting completely."""
        env = EnvironmentSpec(
            indoor_outdoor="indoor",
            location_type="modern office",
            key_objects=["desk", "laptop"],
            background_elements="city skyline through window",
            time_of_day=TimeOfDay.GOLDEN_HOUR,
            weather="",
            atmosphere="warm hazy",
        )

        text = env.to_prompt_text()

        assert "indoor" in text
        assert "modern office" in text
        assert "desk" in text or "laptop" in text
        assert "golden hour" in text
        assert "warm hazy" in text

    def test_lighting_spec_to_prompt_text(self):
        """LightingSpec should describe lighting setup."""
        lighting = LightingSpec(
            style=LightingStyle.DRAMATIC,
            key_light_direction="45 degrees from camera right",
            softness="mixed",
            rim_light=True,
            shadow_style="deep shadows",
            mood="warm dramatic",
            contrast_level="high",
        )

        text = lighting.to_prompt_text()

        assert "dramatic" in text.lower()
        assert "45 degrees" in text
        assert "rim light" in text
        assert "deep shadows" in text or "shadows" in text
        assert "warm" in text
        assert "high contrast" in text

    def test_negative_constraints_to_prompt_text(self):
        """NegativeConstraints should list all exclusions."""
        negatives = NegativeConstraints(
            standard=["watermarks", "text overlays", "logos"],
            custom=["green tones", "fish-eye lens"],
        )

        text = negatives.to_prompt_text()

        assert "watermarks" in text
        assert "text overlays" in text
        assert "logos" in text
        assert "green tones" in text
        assert "fish-eye lens" in text

    def test_full_scene_prompt_spec(self):
        """Full ScenePromptSpec should generate complete prompt."""
        spec = ScenePromptSpec(
            scene_number=1,
            beat_type="HOOK",
            voiceover_segment="You did good today.",
            camera=CameraSpec(shot_type=ShotType.MEDIUM_CLOSE),
            subject=SubjectSpec(
                age_range="30s",
                facial_expression="warm smile",
            ),
            environment=EnvironmentSpec(
                location_type="modern home",
                time_of_day=TimeOfDay.GOLDEN_HOUR,
            ),
            lighting=LightingSpec(style=LightingStyle.NATURAL_SOFT),
            color_style=ColorStyleSpec(color_palette="warm earth tones"),
            detail_level=PromptDetailLevel.ULTRA,
        )

        full_prompt = spec.to_full_prompt()
        negative_prompt = spec.to_negative_prompt()

        # Verify all sections present
        assert "medium close-up" in full_prompt
        assert "30s" in full_prompt
        assert "warm smile" in full_prompt
        assert "modern home" in full_prompt
        assert "golden hour" in full_prompt
        assert "natural" in full_prompt.lower()
        assert "warm earth tones" in full_prompt

        # Verify negatives
        assert "watermarks" in negative_prompt or "text" in negative_prompt

    def test_scene_prompt_spec_to_dict(self):
        """ScenePromptSpec should serialize to dict correctly."""
        spec = ScenePromptSpec(
            scene_number=2,
            beat_type="TENSION",
            voiceover_segment="The struggle was real.",
        )

        d = spec.to_dict()

        assert d["scene_number"] == 2
        assert d["beat_type"] == "TENSION"
        assert "camera" in d
        assert "subject" in d
        assert "environment" in d
        assert "lighting" in d
        assert "color_style" in d
        assert "negatives" in d
        assert "full_prompt" in d
        assert "negative_prompt" in d

    def test_word_count_property(self):
        """word_count() should return accurate count."""
        spec = ScenePromptSpec(
            scene_number=1,
            beat_type="HOOK",
            voiceover_segment="Test",
            subject=SubjectSpec(
                age_range="20s",
                wardrobe="casual clothes",
                facial_expression="happy",
                pose="standing",
                action="waving",
                skin_texture="natural",
                additional_notes="extra details here for word count",
            ),
        )

        count = spec.word_count()

        # Should have a reasonable number of words
        assert count > 30, f"Word count {count} too low"


class TestNanoBananaGenerator:
    """Tests for NanoBananaPromptGenerator."""

    def test_generator_basic(self):
        """Generator should create valid prompts."""
        generator = NanoBananaPromptGenerator()

        spec = generator.generate_scene_spec(
            scene_number=1,
            beat_type="HOOK",
            voiceover_segment="You did good today. Really good.",
        )

        assert spec.scene_number == 1
        assert spec.beat_type == "HOOK"
        assert spec.to_full_prompt()  # Not empty
        assert spec.to_negative_prompt()  # Not empty

    def test_minimum_word_count_ultra(self):
        """ULTRA detail level should meet minimum word count."""
        generator = NanoBananaPromptGenerator(detail_level=PromptDetailLevel.ULTRA)

        for beat in ["HOOK", "TENSION", "SHIFT", "CLIMB", "RESOLUTION", "CTA"]:
            spec = generator.generate_scene_spec(
                scene_number=1,
                beat_type=beat,
                voiceover_segment="This is a test voiceover segment for the scene.",
            )

            word_count = spec.word_count()
            min_required = MIN_WORD_COUNTS[PromptDetailLevel.ULTRA]

            assert word_count >= min_required, (
                f"Beat {beat}: word count {word_count} < minimum {min_required}"
            )

    def test_minimum_word_count_normal(self):
        """NORMAL detail level should meet its minimum."""
        generator = NanoBananaPromptGenerator(detail_level=PromptDetailLevel.NORMAL)

        spec = generator.generate_scene_spec(
            scene_number=1,
            beat_type="HOOK",
            voiceover_segment="A normal test voiceover.",
        )

        word_count = spec.word_count()
        min_required = MIN_WORD_COUNTS[PromptDetailLevel.NORMAL]

        assert word_count >= min_required, f"Word count {word_count} < minimum {min_required}"

    def test_all_beats_have_profiles(self):
        """All standard beats should have visual profiles."""
        beats = ["HOOK", "TENSION", "SHIFT", "CLIMB", "RESOLUTION", "CTA"]

        for beat in beats:
            assert beat in BEAT_PROFILES, f"Missing profile for beat: {beat}"
            profile = BEAT_PROFILES[beat]
            assert profile.shot_types, f"Beat {beat} has no shot types"
            assert profile.lighting_styles, f"Beat {beat} has no lighting styles"

    def test_hook_generates_high_contrast(self):
        """HOOK beat should generate high-contrast visual."""
        generator = NanoBananaPromptGenerator()

        spec = generator.generate_scene_spec(
            scene_number=1,
            beat_type="HOOK",
            voiceover_segment="Stop scrolling. This matters.",
        )

        # HOOK should have high contrast
        assert spec.lighting.contrast_level == "high"

    def test_emotional_tone_detection(self):
        """Generator should detect emotional tone from voiceover."""
        generator = NanoBananaPromptGenerator()

        # Positive tone
        spec_positive = generator.generate_scene_spec(
            scene_number=1,
            beat_type="RESOLUTION",
            voiceover_segment="You achieved something great today. Be proud.",
        )

        # The color palette should reflect positive tone
        prompt = spec_positive.to_full_prompt()
        assert any(word in prompt.lower() for word in ["warm", "gold", "bright"])

    def test_continuity_with_prior_scene(self):
        """Generator should reference prior scene for continuity."""
        generator = NanoBananaPromptGenerator()

        # First scene
        spec1 = generator.generate_scene_spec(
            scene_number=1,
            beat_type="HOOK",
            voiceover_segment="First scene content.",
        )

        # Second scene with prior reference
        spec2 = generator.generate_scene_spec(
            scene_number=2,
            beat_type="TENSION",
            voiceover_segment="Second scene content.",
            prior_scene_spec=spec1,
        )

        # Continuity should reference prior scene
        d = spec2.to_dict()
        continuity = d.get("continuity", {})

        # Should have some continuity reference
        assert (
            continuity.get("prior_scene_references")
            or continuity.get("consistency_notes")
        )

    def test_overlay_text_inclusion(self):
        """Generator should include overlay text when provided."""
        generator = NanoBananaPromptGenerator()

        spec = generator.generate_scene_spec(
            scene_number=1,
            beat_type="HOOK",
            voiceover_segment="Important message here.",
            overlay_text="IMPORTANT",
        )

        assert spec.overlay_text == "IMPORTANT"

    def test_entities_continuity(self):
        """Generator should reference provided entities."""
        entities = [
            {"name": "Young Professional", "description": "30s, dark suit, confident demeanor"},
            {"name": "Modern Office", "description": "minimalist design, large windows"},
        ]

        generator = NanoBananaPromptGenerator(entities=entities)

        spec = generator.generate_scene_spec(
            scene_number=1,
            beat_type="HOOK",
            voiceover_segment="The day begins.",
        )

        d = spec.to_dict()
        continuity_entities = d.get("continuity", {}).get("entities", [])

        # Should have entity references
        assert len(continuity_entities) > 0
        assert any("Young Professional" in e for e in continuity_entities)

    def test_visual_preset_integration(self):
        """Generator should use visual preset configuration."""
        preset = {
            "generation": {
                "aspect_ratio": "9:16",
                "resolution": "1080x1920",
                "fps": 24,
            },
            "style": {
                "color_grading": "teal-orange",
            },
        }

        generator = NanoBananaPromptGenerator(visual_preset=preset)

        spec = generator.generate_scene_spec(
            scene_number=1,
            beat_type="HOOK",
            voiceover_segment="Preset test.",
        )

        d = spec.to_dict()

        # Should use preset values
        assert d["output_format"]["aspect_ratio"] == "9:16"
        assert d["output_format"]["resolution"] == "1080x1920"


class TestConvenienceFunction:
    """Tests for the generate_nanobanana_prompt convenience function."""

    def test_generate_nanobanana_prompt_basic(self):
        """Convenience function should generate valid prompt."""
        spec = generate_nanobanana_prompt(
            scene_number=1,
            beat_type="HOOK",
            voiceover="This is test voiceover content.",
        )

        assert isinstance(spec, ScenePromptSpec)
        assert spec.scene_number == 1
        assert spec.beat_type == "HOOK"
        assert spec.to_full_prompt()

    def test_generate_nanobanana_prompt_detail_levels(self):
        """Convenience function should respect detail level."""
        for level in ["short", "normal", "ultra"]:
            spec = generate_nanobanana_prompt(
                scene_number=1,
                beat_type="TENSION",
                voiceover="Test content for different detail levels.",
                detail_level=level,
            )

            assert spec.detail_level.value == level


class TestPromptRequiredFields:
    """Tests ensuring prompts include all required fields."""

    @pytest.fixture
    def sample_spec(self):
        """Generate a sample spec for testing."""
        return generate_nanobanana_prompt(
            scene_number=1,
            beat_type="HOOK",
            voiceover="Test voiceover for required fields.",
            detail_level="ultra",
        )

    def test_has_camera_spec(self, sample_spec):
        """Prompt spec must include camera details."""
        d = sample_spec.to_dict()

        assert "camera" in d
        camera = d["camera"]
        assert "shot_type" in camera
        assert "angle" in camera
        assert "lens_mm" in camera
        assert "movement" in camera
        assert "depth_of_field" in camera

    def test_has_subject_spec(self, sample_spec):
        """Prompt spec must include subject details."""
        d = sample_spec.to_dict()

        assert "subject" in d
        subject = d["subject"]
        assert "count" in subject
        assert "subject_type" in subject
        assert "facial_expression" in subject
        assert "pose" in subject

    def test_has_environment_spec(self, sample_spec):
        """Prompt spec must include environment details."""
        d = sample_spec.to_dict()

        assert "environment" in d
        env = d["environment"]
        assert "indoor_outdoor" in env
        assert "location_type" in env
        assert "time_of_day" in env

    def test_has_lighting_spec(self, sample_spec):
        """Prompt spec must include lighting details."""
        d = sample_spec.to_dict()

        assert "lighting" in d
        lighting = d["lighting"]
        assert "style" in lighting
        assert "key_light_direction" in lighting
        assert "softness" in lighting
        assert "mood" in lighting

    def test_has_color_style_spec(self, sample_spec):
        """Prompt spec must include color/style details."""
        d = sample_spec.to_dict()

        assert "color_style" in d
        style = d["color_style"]
        assert "color_palette" in style
        assert "contrast" in style
        assert "realism_level" in style

    def test_has_negatives(self, sample_spec):
        """Prompt spec must include negative constraints."""
        d = sample_spec.to_dict()

        assert "negatives" in d
        negatives = d["negatives"]
        assert "standard" in negatives
        assert len(negatives["standard"]) > 0

    def test_has_output_format(self, sample_spec):
        """Prompt spec must include output format."""
        d = sample_spec.to_dict()

        assert "output_format" in d
        fmt = d["output_format"]
        assert "aspect_ratio" in fmt
        assert "resolution" in fmt

    def test_full_prompt_contains_camera_info(self, sample_spec):
        """Full prompt text must contain camera information."""
        prompt = sample_spec.to_full_prompt()

        # Should contain shot type or camera angle info
        assert any(
            word in prompt.lower()
            for word in ["shot", "angle", "lens", "depth of field", "close", "wide", "medium"]
        )

    def test_full_prompt_contains_subject_info(self, sample_spec):
        """Full prompt text must contain subject information."""
        prompt = sample_spec.to_full_prompt()

        # Should contain subject-related info
        assert any(
            word in prompt.lower()
            for word in ["person", "expression", "pose", "skin", "natural"]
        )

    def test_full_prompt_contains_lighting_info(self, sample_spec):
        """Full prompt text must contain lighting information."""
        prompt = sample_spec.to_full_prompt()

        # Should contain lighting info
        assert any(
            word in prompt.lower()
            for word in ["light", "lighting", "shadow", "rim", "key"]
        )

    def test_negative_prompt_has_standard_exclusions(self, sample_spec):
        """Negative prompt must include standard exclusions."""
        negative = sample_spec.to_negative_prompt()

        # Should exclude common AI artifacts
        assert any(
            word in negative.lower()
            for word in ["watermark", "logo", "text", "distorted", "blurry"]
        )


class TestVisualStrategy:
    """Tests for visual strategy system (people vs environment)."""

    def test_motivation_niche_uses_environment_strategy(self):
        """Motivation niche should default to environment (no people)."""
        spec = generate_nanobanana_prompt(
            scene_number=1,
            beat_type="HOOK",
            voiceover="The only way to do great work is to love what you do.",
            niche="motivation",
        )

        # Should NOT be a person
        assert spec.subject.subject_type == "environment"
        # Negatives should include no-people constraints
        assert any("no people" in neg.lower() for neg in spec.negatives.custom)

    def test_fitness_niche_uses_people_strategy(self):
        """Fitness niche should use people visuals."""
        spec = generate_nanobanana_prompt(
            scene_number=1,
            beat_type="HOOK",
            voiceover="Get ready to transform your body.",
            niche="fitness",
        )

        # Should be a person
        assert spec.subject.subject_type == "person"
        # Negatives should NOT include no-people constraints
        assert not any("no people" in neg.lower() for neg in spec.negatives.custom)

    def test_explicit_environment_strategy(self):
        """Explicit environment strategy should override niche default."""
        spec = generate_nanobanana_prompt(
            scene_number=1,
            beat_type="TENSION",
            voiceover="Push through the pain.",
            niche="fitness",  # Would normally use people
            visual_strategy="environment",  # Override to environment
        )

        assert spec.subject.subject_type == "environment"

    def test_explicit_people_strategy(self):
        """Explicit people strategy should override niche default."""
        spec = generate_nanobanana_prompt(
            scene_number=1,
            beat_type="HOOK",
            voiceover="Rise above your fears.",
            niche="motivation",  # Would normally use environment
            visual_strategy="people",  # Override to people
        )

        assert spec.subject.subject_type == "person"

    def test_environment_subjects_exist_for_all_beats(self):
        """All beat profiles should have environment_subjects."""
        for beat, profile in BEAT_PROFILES.items():
            assert profile.environment_subjects is not None, f"Missing environment_subjects for {beat}"
            assert len(profile.environment_subjects) > 0, f"Empty environment_subjects for {beat}"

    def test_niche_defaults_mapping(self):
        """Verify niche defaults are properly configured."""
        # Motivation niches should use ENVIRONMENT
        assert NICHE_VISUAL_DEFAULTS.get("motivation") == VisualStrategy.ENVIRONMENT
        assert NICHE_VISUAL_DEFAULTS.get("stoicism") == VisualStrategy.ENVIRONMENT
        assert NICHE_VISUAL_DEFAULTS.get("fun_facts") == VisualStrategy.ENVIRONMENT

        # Lifestyle niches should use PEOPLE
        assert NICHE_VISUAL_DEFAULTS.get("fitness") == VisualStrategy.PEOPLE
        assert NICHE_VISUAL_DEFAULTS.get("beauty") == VisualStrategy.PEOPLE

    def test_environment_prompt_excludes_person_terms(self):
        """Environment prompts should use environment subject type."""
        spec = generate_nanobanana_prompt(
            scene_number=1,
            beat_type="RESOLUTION",
            voiceover="Find your inner peace.",
            niche="stoicism",
        )

        # Subject should be environment type
        assert spec.subject.subject_type == "environment"

        # Subject should NOT have person-specific fields filled
        assert spec.subject.age_range == ""
        assert spec.subject.wardrobe == ""
        assert spec.subject.hair_style == ""
        assert spec.subject.facial_expression == ""
        assert spec.subject.skin_texture == ""

        # Additional notes should mention NO PEOPLE
        assert "NO PEOPLE" in spec.subject.additional_notes
