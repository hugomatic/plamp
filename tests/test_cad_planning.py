import hashlib
import json
from pathlib import Path
from types import MappingProxyType
import unittest

from plamp.cad_model import CadModel, CadSet
from plamp.cad_planning import (
    CadSelection,
    build_render_plan,
    plan_as_dict,
)
from plamp.cad_system import CadProduct, CadProductItem, CadSystem


def model(model_id, sets, *, variables=None):
    return CadModel(
        model_id=model_id,
        name=model_id.title(),
        description="",
        source_path=Path(f"things/{model_id}/{model_id}.scad"),
        sidecar_path=None,
        default_set=next(iter(sets)),
        sets=MappingProxyType({
            name: CadSet(name, variables=values)
            for name, values in sets.items()
        }),
        variables=variables or {},
        metadata_snapshot={},
    )


def item(*, product=None, model_id=None, set_name=None, variant=None,
         variables=None, profiles=(), slicing=None):
    return CadProductItem(
        product=product, model=model_id, set_name=set_name, variant=variant,
        variables=variables or {}, profiles=profiles, slicing=slicing or {},
    )


def product(name, items, *, variables=None, profiles=(), slicing=None):
    return CadProduct(
        name, "", tuple(items), variables or {}, profiles, slicing or {}
    )


class CadPlanningTests(unittest.TestCase):
    def system(self, *, products=None, default_product=None):
        models = {
            "box": model("box", {
                "floor": {"height": 10}, "top": {"height": 12}
            }, variables={"clearance": 0.1, "material": "pla"}),
            "holder": model("holder", {"standard": {"height": 3}}),
        }
        snapshot = {"schema": "plamp-cad-system/1", "name": "fixture"}
        return CadSystem(
            "fixture", "", Path("cad/fixture.system.cad.json"),
            MappingProxyType(models), MappingProxyType(products or {}),
            default_product, MappingProxyType({}), MappingProxyType({}),
            MappingProxyType(snapshot),
        )

    def nested_system(self):
        products = {
            "split-box": product("split-box", [
                item(model_id="box", set_name="floor"),
                item(model_id="box", set_name="top"),
            ]),
            "complete": product("complete", [
                item(product="split-box"),
                item(model_id="holder", set_name="standard"),
            ]),
        }
        return self.system(products=products, default_product="complete")

    def test_nested_product_order_deduplication_and_memberships(self):
        system = self.nested_system()
        system.products["complete"].items  # prove immutable input is accepted
        plan = build_render_plan(
            system, CadSelection(product="complete"),
            source_identities={"box": "box123", "holder": "holder456"},
        )
        self.assertEqual(
            tuple((job.model_id, job.set_name) for job in plan.jobs),
            (("box", "floor"), ("box", "top"), ("holder", "standard")),
        )
        self.assertEqual(plan.jobs[0].product_paths, (("complete", "split-box"),))

        repeated = dict(system.products)
        repeated["complete"] = product("complete", [
            item(product="split-box"), item(product="split-box")
        ])
        deduped = build_render_plan(
            self.system(products=repeated), CadSelection(product="complete"),
            source_identities={"box": "box123", "holder": "holder456"},
        )
        self.assertEqual(len(deduped.jobs), 2)

    def test_variable_precedence_runs_deepest_product_outward_then_cli(self):
        products = {
            "inner": product("inner", [item(
                model_id="box", set_name="floor",
                variables={"clearance": 0.25, "leaf": True},
            )], variables={"clearance": 0.2, "inner": True}),
            "complete": product("complete", [item(
                product="inner", variables={"clearance": 0.35, "edge": True},
            )], variables={"clearance": 0.3, "outer": True}),
        }
        plan = build_render_plan(
            self.system(products=products),
            CadSelection(product="complete", defines={"clearance": 0.4}),
            source_identities={"box": "abc", "holder": "unused"},
        )
        job = plan.jobs[0]
        self.assertEqual(job.variables["clearance"], 0.4)
        self.assertEqual(job.variable_sources["clearance"].kind, "cli")
        self.assertEqual(job.variable_sources["edge"].source_id, "complete[0]")
        self.assertTrue(all(job.variables[key] for key in ("leaf", "inner", "outer", "edge")))

    def test_empty_default_and_direct_named_set_selection(self):
        system = self.nested_system()
        default = build_render_plan(
            system, CadSelection(), {"box": "a", "holder": "b"}
        )
        explicit = build_render_plan(
            system, CadSelection(product="complete"), {"box": "a", "holder": "b"}
        )
        self.assertEqual(tuple(j.fingerprint for j in default.jobs),
                         tuple(j.fingerprint for j in explicit.jobs))

        direct = build_render_plan(
            system, CadSelection(model="box", sets=("top", "floor", "top")),
            {"box": "a"},
        )
        self.assertEqual(tuple(j.set_name for j in direct.jobs), ("top", "floor"))
        all_sets = build_render_plan(
            system, CadSelection(model="box", all_sets=True), {"box": "a"}
        )
        self.assertEqual(tuple(j.set_name for j in all_sets.jobs), ("floor", "top"))

    def test_unknown_and_conflicting_selections_are_diagnostic(self):
        system = self.nested_system()
        cases = (
            (CadSelection(product="missing"), "Unknown product"),
            (CadSelection(model="missing"), "Unknown model"),
            (CadSelection(model="box", sets=("missing",)), "Unknown set"),
            (CadSelection(product="complete", model="box"), "cannot be combined"),
            (CadSelection(sets=("floor",)), "requires a model"),
        )
        for selection, message in cases:
            with self.subTest(selection=selection), self.assertRaisesRegex(ValueError, message):
                build_render_plan(system, selection, {"box": "a", "holder": "b"})

    def test_repeated_variants_raw_precedence_and_human_artifacts(self):
        products = {"complete": product("complete", [
            item(model_id="box", set_name="floor", variant="narrow",
                 variables={"width": 1, "shape": "narrow"}),
            item(model_id="box", set_name="floor", variant="wide",
                 variables={"width": 2, "shape": "wide"}),
        ])}
        plan = build_render_plan(
            self.system(products=products),
            CadSelection(
                product="complete", defines={"width": 5},
                set_defines={"floor": {"width": 6}},
                raw_defines=("width=2+2", "formula=first=value", "formula=last=value"),
            ), {"box": "source"},
        )
        self.assertEqual(tuple(j.variant_name for j in plan.jobs), ("narrow", "wide"))
        self.assertEqual(len({j.artifact_id for j in plan.jobs}), 2)
        self.assertTrue(all("width" not in j.variables for j in plan.jobs))
        self.assertTrue(all(j.raw_defines == {"width": "2+2", "formula": "last=value"}
                            for j in plan.jobs))

    def test_profile_only_sibling_variants_remain_distinct_and_compose_root_to_leaf(self):
        products = {
            "inner": product("inner", [
                item(model_id="box", set_name="floor", variant="draft",
                     profiles=("draft",)),
                item(model_id="box", set_name="floor", variant="quality",
                     profiles=("quality",)),
            ], profiles=("inner-base",)),
            "complete": product("complete", [
                item(product="inner", profiles=("edge",)),
            ], profiles=("outer-base",)),
        }
        plan = build_render_plan(
            self.system(products=products), CadSelection(product="complete"),
            {"box": "source"},
        )
        self.assertEqual(len(plan.jobs), 2)
        self.assertEqual(plan.jobs[0].profiles, (
            "outer-base", "edge", "inner-base", "draft",
        ))
        self.assertEqual(plan.jobs[1].profiles[-1], "quality")
        self.assertNotEqual(plan.jobs[0].fingerprint, plan.jobs[1].fingerprint)

    def test_slicing_only_sibling_variants_remain_distinct_and_overlay_deepest_outward(self):
        products = {
            "inner": product("inner", [
                item(model_id="box", set_name="floor", variant="fine",
                     slicing={"layer_height": 0.12, "supports": "required"}),
                item(model_id="box", set_name="floor", variant="coarse",
                     slicing={"layer_height": 0.28, "supports": "required"}),
            ], slicing={"supports": "discouraged", "brim": 2}),
            "complete": product("complete", [
                item(product="inner", slicing={"brim": 5}),
            ], slicing={"supports": "forbidden"}),
        }
        plan = build_render_plan(
            self.system(products=products), CadSelection(product="complete"),
            {"box": "source"},
        )
        self.assertEqual(len(plan.jobs), 2)
        self.assertEqual(plan.jobs[0].slicing, {
            "layer_height": 0.12, "supports": "forbidden", "brim": 5,
        })
        self.assertEqual(plan.jobs[1].slicing["layer_height"], 0.28)
        self.assertNotEqual(plan.jobs[0].fingerprint, plan.jobs[1].fingerprint)

    def test_fingerprint_is_stable_sha256_and_changes_with_manifest_or_source(self):
        system = self.nested_system()
        first = build_render_plan(system, CadSelection(product="complete"),
                                  {"box": "a", "holder": "b"})
        again = build_render_plan(system, CadSelection(product="complete"),
                                  {"box": "a", "holder": "b"})
        self.assertEqual(tuple(j.fingerprint for j in first.jobs),
                         tuple(j.fingerprint for j in again.jobs))
        self.assertTrue(all(len(j.fingerprint) == 64 for j in first.jobs))
        self.assertTrue(all(bytes.fromhex(j.fingerprint) for j in first.jobs))
        changed = build_render_plan(system, CadSelection(product="complete"),
                                    {"box": "different", "holder": "b"})
        self.assertNotEqual(first.jobs[0].fingerprint, changed.jobs[0].fingerprint)
        expected_manifest_hash = hashlib.sha256(
            json.dumps(dict(system.metadata_snapshot), sort_keys=True, separators=(",", ":"))
            .encode()
        ).hexdigest()
        self.assertIn(expected_manifest_hash, json.dumps(plan_as_dict(first)))

    def test_cycle_defense_and_json_shape(self):
        cyclic = self.system(products={
            "a": product("a", [item(product="b")]),
            "b": product("b", [item(product="a")]),
        })
        with self.assertRaisesRegex(ValueError, "a -> b -> a"):
            build_render_plan(cyclic, CadSelection(product="a"), {})

        plan = build_render_plan(self.nested_system(), CadSelection(product="complete"),
                                 {"box": "a", "holder": "b"})
        value = plan_as_dict(plan)
        json.dumps(value, allow_nan=False)
        self.assertEqual(set(value), {"system_name", "system_path", "selection",
                                      "system_manifest_hash", "jobs"})
        self.assertEqual(set(value["jobs"][0]), {
            "artifact_id", "model_id", "set_name", "variant_name", "variables",
            "raw_defines", "variable_sources", "profiles", "slicing",
            "product_paths", "fingerprint",
        })


if __name__ == "__main__":
    unittest.main()
