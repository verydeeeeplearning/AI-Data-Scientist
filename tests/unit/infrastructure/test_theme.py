"""Tests for CLI theme constants."""

from rich.theme import Theme

from ds_agent.cli.theme import DS_THEME, MODE_ICONS


class TestTheme:
    def test_ds_theme_is_theme_instance(self):
        assert isinstance(DS_THEME, Theme)

    def test_mode_icons_has_all_modes(self):
        expected = {"auto", "supervised", "step-by-step"}
        assert expected.issubset(set(MODE_ICONS.keys()))

    def test_mode_icons_values_are_strings(self):
        for value in MODE_ICONS.values():
            assert isinstance(value, str)
            assert len(value) > 0
