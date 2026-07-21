import json
import subprocess
import sys
import unittest
from pathlib import Path

from plamp.cad_metadata import CadDocument, PresetMetadata, ViewMetadata
from plamp.cad_recipes import (
    Selection,
    build_render_plan,
    plan_as_dict,
    serialize_scad_value,
)


def document(
    *,
    views=("floor", "box", "north_south_walls", "assembly"),
    default_view="assembly",
    global_variables=None,
    view_metadata=None,
    presets=None,
    default_preset=None,
):
    return CadDocument(
        path=Path("part.scad"),
        default_view=default_view,
        views=tuple(views),
        global_variables=global_variables or {},
        view_metadata=view_metadata or {},
        presets=presets or {},
        default_preset=default_preset,
        metadata_snapshot={},
    )


DOCUMENT_WITH_SHARED_AND_VARIANT_WALLS = document(
    view_metadata={
        "north_south_walls": ViewMetadata(variables={"coarse": False})
    },
    presets={
        "shared": PresetMetadata(items=("view:north_south_walls",)),
        "outer": PresetMetadata(items=("preset:shared",)),
        "coarse": PresetMetadata(
            items=("view:north_south_walls",),
            view_variables={"north_south_walls": {"coarse": True}},
        ),
    },
)


DOCUMENT_WITH_ALL_VARIABLE_SCOPES = document(
    global_variables={"rib": "global", "global_only": 1},
    view_metadata={
        "box": ViewMetadata(
            variables={"rib": "view", "view_only": 2}
        )
    },
    presets={
        "outer": PresetMetadata(
            items=("preset:inner",),
            variables={"rib": "outer", "outer_only": 3},
            view_variables={"box": {"rib": "outer-view", "outer_view_only": 4}},
        ),
        "inner": PresetMetadata(
            items=("view:box",),
            variables={"rib": "inner", "inner_only": 5},
            view_variables={"box": {"rib": "inner-view", "inner_view_only": 6}},
        ),
    },
)


class CadRecipeTests(unittest.TestCase):
    def test_nested_presets_expand_depth_first_in_declared_item_order(self):
        source = document(
            presets={
                "outer": PresetMetadata(
                    description="Outer",
                    items=("view:floor", "preset:inner", "view:assembly"),
                ),
                "inner": PresetMetadata(
                    description="Inner", items=("view:box", "view:north_south_walls")
                ),
            }
        )

        plan = build_render_plan(source, Selection(preset="outer"), "abc123")

        self.assertEqual(
            [job.view for job in plan.jobs],
            ["floor", "box", "north_south_walls", "assembly"],
        )
        self.assertEqual(plan.preset_tree[0].name, "outer")
        self.assertEqual(plan.preset_tree[0].children[0].name, "inner")

    def test_empty_preset_produces_one_implicit_default_job(self):
        source = document(presets={"configured-default": PresetMetadata()})

        plan = build_render_plan(
            source, Selection(preset="configured-default"), "abc123"
        )

        self.assertEqual(len(plan.jobs), 1)
        self.assertIsNone(plan.jobs[0].view)
        self.assertEqual(plan.jobs[0].preset_paths, (("configured-default",),))

    def test_default_selection_uses_default_preset(self):
        source = document(
            presets={"print": PresetMetadata(items=("view:box",))},
            default_preset="print",
        )

        plan = build_render_plan(source, Selection(), "abc123")

        self.assertEqual([job.view for job in plan.jobs], ["box"])
        self.assertEqual(plan.selection.preset, "print")

    def test_no_default_preset_produces_implicit_default_job(self):
        plan = build_render_plan(document(), Selection(), "abc123")

        self.assertEqual([job.view for job in plan.jobs], [None])

    def test_cycle_diagnostic_contains_complete_active_path(self):
        source = document(
            presets={
                "all": PresetMetadata(items=("preset:tests",)),
                "tests": PresetMetadata(items=("preset:coupons",)),
                "coupons": PresetMetadata(items=("preset:all",)),
            }
        )

        with self.assertRaisesRegex(
            ValueError, "all -> tests -> coupons -> all"
        ):
            build_render_plan(source, Selection(preset="all"), "abc123")

    def test_all_views_uses_customizer_order_without_preset_membership(self):
        source = document(views=("box", "assembly", "floor"))

        plan = build_render_plan(source, Selection(preset="all-views"), "abc123")

        self.assertEqual([job.view for job in plan.jobs], ["box", "assembly", "floor"])
        self.assertTrue(all(job.preset_paths == () for job in plan.jobs))
        self.assertEqual(plan.preset_tree, ())

    def test_all_presets_deduplicates_identical_jobs_but_keeps_variants(self):
        plan = build_render_plan(
            DOCUMENT_WITH_SHARED_AND_VARIANT_WALLS,
            Selection(preset="all-presets"),
            source_identity="abc123",
        )
        wall_jobs = [job for job in plan.jobs if job.view == "north_south_walls"]
        self.assertEqual(len(wall_jobs), 2)
        self.assertEqual({job.variables["coarse"] for job in wall_jobs}, {True, False})
        shared = next(job for job in wall_jobs if not job.variables["coarse"])
        self.assertGreater(len(shared.preset_paths), 1)
        self.assertIn(("shared",), shared.preset_paths)
        self.assertIn(("outer", "shared"), shared.preset_paths)

    def test_same_view_variants_have_distinct_human_names_and_artifacts(self):
        plan = build_render_plan(
            DOCUMENT_WITH_SHARED_AND_VARIANT_WALLS,
            Selection(preset="all-presets"),
            "abc123",
        )
        wall_jobs = [job for job in plan.jobs if job.view == "north_south_walls"]

        self.assertEqual(
            [job.variant_name for job in wall_jobs],
            ["north_south_walls", "north_south_walls-2"],
        )
        self.assertEqual(len({job.artifact_id for job in wall_jobs}), 2)
        for job in wall_jobs:
            self.assertEqual(job.artifact_id, f"{job.variant_name}--{job.fingerprint[:12]}")

    def test_direct_selection_moves_assembly_last_and_preserves_other_order(self):
        plan = build_render_plan(
            document(),
            Selection(views=("assembly", "box", "floor")),
            "abc123",
        )

        self.assertEqual([job.view for job in plan.jobs], ["box", "floor", "assembly"])

    def test_repeatable_direct_views_are_deduplicated_stably(self):
        plan = build_render_plan(
            document(),
            Selection(views=("box", "floor", "box", "assembly")),
            "abc123",
        )

        self.assertEqual([job.view for job in plan.jobs], ["box", "floor", "assembly"])

    def test_preset_and_direct_views_conflict(self):
        with self.assertRaisesRegex(ValueError, "preset.*views|views.*preset"):
            build_render_plan(
                document(presets={"print": PresetMetadata()}),
                Selection(preset="print", views=("box",)),
                "abc123",
            )

    def test_unknown_runtime_selectors_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown preset.*missing"):
            build_render_plan(document(), Selection(preset="missing"), "abc123")
        with self.assertRaisesRegex(ValueError, "Unknown view.*missing"):
            build_render_plan(document(), Selection(views=("missing",)), "abc123")

    def test_every_variable_scope_resolves_in_documented_precedence(self):
        plan = build_render_plan(
            DOCUMENT_WITH_ALL_VARIABLE_SCOPES,
            Selection(
                preset="outer",
                defines={"rib": "cli", "cli_only": 7},
                view_defines={"box": {"rib": "view-cli", "view_cli_only": 8}},
            ),
            "abc123",
        )

        variables = plan.jobs_by_view["box"].variables
        self.assertEqual(variables["rib"], "view-cli")
        self.assertEqual(
            variables,
            {
                "rib": "view-cli",
                "global_only": 1,
                "view_only": 2,
                "outer_only": 3,
                "inner_only": 5,
                "outer_view_only": 4,
                "inner_view_only": 6,
                "cli_only": 7,
                "view_cli_only": 8,
            },
        )

    def test_cli_define_overrides_preset_view_scope(self):
        plan = build_render_plan(
            DOCUMENT_WITH_ALL_VARIABLE_SCOPES,
            Selection(preset="outer", defines={"rib": "cli"}),
            "abc123",
        )
        self.assertEqual(plan.jobs_by_view["box"].variables["rib"], "cli")

    def test_cli_view_define_has_highest_precedence(self):
        plan = build_render_plan(
            DOCUMENT_WITH_ALL_VARIABLE_SCOPES,
            Selection(
                preset="outer",
                defines={"rib": "cli"},
                view_defines={"box": {"rib": "view-cli"}},
            ),
            source_identity="abc123",
        )
        self.assertEqual(plan.jobs_by_view["box"].variables["rib"], "view-cli")

    def test_implicit_job_receives_global_preset_and_cli_scopes(self):
        source = document(
            global_variables={"value": "global"},
            presets={
                "default": PresetMetadata(variables={"value": "preset"})
            },
        )
        plan = build_render_plan(
            source,
            Selection(preset="default", defines={"value": "cli"}),
            "abc123",
        )

        self.assertEqual(plan.jobs[0].variables["value"], "cli")

    def test_fingerprint_is_stable_and_covers_source_view_variables_and_schema(self):
        first = build_render_plan(
            document(global_variables={"b": 2, "a": 1}),
            Selection(views=("box",)),
            "source-a",
        ).jobs[0]
        reordered = build_render_plan(
            document(global_variables={"a": 1, "b": 2}),
            Selection(views=("box",)),
            "source-a",
        ).jobs[0]
        other_source = build_render_plan(
            document(global_variables={"a": 1, "b": 2}),
            Selection(views=("box",)),
            "source-b",
        ).jobs[0]
        implicit = build_render_plan(
            document(global_variables={"a": 1, "b": 2}), Selection(), "source-a"
        ).jobs[0]

        self.assertEqual(first.fingerprint, reordered.fingerprint)
        self.assertNotEqual(first.fingerprint, other_source.fingerprint)
        self.assertNotEqual(first.fingerprint, implicit.fingerprint)
        self.assertEqual(len(first.fingerprint), 64)

        script = """
from pathlib import Path
from plamp.cad_metadata import CadDocument
from plamp.cad_recipes import Selection, build_render_plan
d = CadDocument(Path('part.scad'), 'box', ('box',), {'b':2,'a':1}, {}, {}, None, {})
print(build_render_plan(d, Selection(views=('box',)), 'source-a').jobs[0].fingerprint)
"""
        output = subprocess.check_output(
            [sys.executable, "-c", script], text=True
        ).strip()
        self.assertEqual(first.fingerprint, output)

    def test_scad_values_serialize_deterministically(self):
        self.assertEqual(serialize_scad_value(None), "undef")
        self.assertEqual(serialize_scad_value(True), "true")
        self.assertEqual(serialize_scad_value(False), "false")
        self.assertEqual(serialize_scad_value(3.5), "3.5")
        self.assertEqual(serialize_scad_value('a"b'), '"a\\\"b"')
        self.assertEqual(serialize_scad_value([1, "x"]), '[1, "x"]')
        self.assertEqual(
            serialize_scad_value({"z": 2, "a": True}),
            '[["a", true], ["z", 2]]',
        )

    def test_plan_as_dict_returns_json_serializable_public_shape(self):
        plan = build_render_plan(
            document(
                view_metadata={"box": ViewMetadata(description="Printable box")},
                presets={
                    "print": PresetMetadata(
                        description="Print it", items=("view:box",)
                    )
                },
            ),
            Selection(preset="print"),
            "abc123",
        )

        value = plan_as_dict(plan)

        json.dumps(value, sort_keys=True)
        self.assertEqual(value["selection"]["preset"], "print")
        self.assertEqual(value["jobs"][0]["view"], "box")
        self.assertEqual(value["preset_tree"][0]["description"], "Print it")
        self.assertEqual(value["preset_tree"][0]["views"][0]["description"], "Printable box")


if __name__ == "__main__":
    unittest.main()
