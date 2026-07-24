import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
import unittest

from plamp.cad_model import CadModel, CadSet
from plamp.cad_profiles import CadProfile, CadProfileError
from plamp.cad_planning import (
    CadSelection,
    build_render_plan,
    plan_as_dict,
)
from plamp.cad_values import resolve_variables
from plamp.cad_system import CadProduct, CadProductItem, CadSystem, load_system


def model(model_id, sets, *, variables=None, source_defaults=None):
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
        source_defaults=source_defaults or {},
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
    def test_selection_rejects_selector_owned_set_variable_overrides(self):
        cases = (
            {"defines": {"set": "floor"}},
            {"set_defines": {"floor": {"set": "floor"}}},
            {"raw_defines": ('set="floor"',)},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaisesRegex(
                ValueError, "selector-owned variable 'set'"
            ):
                CadSelection(**arguments)

    def test_resolver_retains_typed_and_raw_replacement_history(self):
        typed, raw, provenance = resolve_variables((
            ("scad", "box.scad", {"width": 2, "height": 4}, {}),
            ("profile", "system:draft", {}, {"width": "2+2"}),
            ("cli", "defines", {"width": 5}, {"height": "sqrt(16)"}),
        ))

        self.assertEqual(typed, {"width": 5})
        self.assertEqual(raw, {"height": "sqrt(16)"})
        self.assertEqual(
            tuple((layer.kind, layer.value, layer.raw_expression)
                  for layer in provenance["width"].layers),
            (("scad", 2, None), ("profile", None, "2+2"),
             ("cli", 5, None)),
        )
        self.assertEqual(provenance["height"].winner.raw_expression, "sqrt(16)")
        with self.assertRaises(TypeError):
            provenance["new"] = provenance["width"]

    def test_selector_owned_set_is_removed_from_every_variable_layer(self):
        kinds = ("scad", "model", "set", "profile", "product", "item", "cli")
        layers = []
        for index, kind in enumerate(kinds):
            layers.append((kind, str(index), {"set": f"typed-{kind}"}, {}))
            layers.append((kind, f"raw-{index}", {}, {"set": f'"raw-{kind}"'}))

        typed, raw, provenance = resolve_variables(tuple(layers))

        self.assertNotIn("set", typed)
        self.assertNotIn("set", raw)
        self.assertNotIn("set", provenance)

    def test_exact_variable_precedence_and_complete_provenance(self):
        box = model(
            "box", {"floor": {"clearance": 0.2}},
            variables={"clearance": 0.1},
            source_defaults={"clearance": 0.05, "set": "floor"},
        )
        profile = CadProfile(
            "draft", "system:draft", "quality", Path("draft.json"),
            {"clearance": 0.25}, {}, {}, "a" * 64,
        )
        products = {"complete": product(
            "complete",
            [item(model_id="box", set_name="floor",
                  variables={"clearance": 0.4})],
            variables={"clearance": 0.35, "set": "product-choice"},
            profiles=("draft",),
        )}
        system = CadSystem(
            "fixture", "", Path("cad/fixture.system.cad.json"),
            MappingProxyType({"box": box}), MappingProxyType(products),
            "complete", MappingProxyType({}), MappingProxyType({"draft": profile}),
            MappingProxyType({"schema": "plamp-cad-system/1", "name": "fixture"}),
        )

        job = build_render_plan(
            system, CadSelection(product="complete", defines={"clearance": 0.45}),
            {"box": "source"},
        ).jobs[0]

        self.assertEqual(job.variables["clearance"], 0.45)
        resolved = job.variable_sources["clearance"]
        self.assertEqual(tuple(layer.kind for layer in resolved.layers),
                         ("scad", "model", "set", "profile", "product", "item", "cli"))
        self.assertEqual(resolved.winner.kind, "cli")
        self.assertNotIn("set", job.variables)
    def test_repository_fit_and_function_expands_exact_order_and_paths(self):
        repo_root = Path(__file__).resolve().parents[1]
        system = load_system(repo_root / "cad" / "plamp.system.cad.json", repo_root)
        plan = build_render_plan(
            system,
            CadSelection(product="fit-and-function"),
            {model_id: f"test-{model_id}" for model_id in system.models},
        )
        expected = (
            ("relay_footprint", "component-floorplans"),
            ("psu_footprint", "component-floorplans"),
            ("converter_footprint", "component-floorplans"),
            ("ac_duplex_panel", "top-panel-fit"),
            ("dc_connector_panel", "top-panel-fit"),
            ("usb_c_panel", "top-panel-fit"),
            ("c13_panel", "top-panel-fit"),
            ("panel_corner_fastener_test", "corner-coupons"),
            ("corner_coupon", "corner-coupons"),
            ("wall_corner_fastener_assembly", "corner-coupons"),
        )
        self.assertEqual(
            tuple((job.model_id, job.set_name) for job in plan.jobs),
            tuple(("plamp8", set_name) for set_name, _ in expected),
        )
        self.assertEqual(
            tuple(job.product_paths for job in plan.jobs),
            tuple((("fit-and-function", product_name),) for _, product_name in expected),
        )

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
        self.assertEqual(tuple(j.geometry_fingerprint for j in default.jobs),
                         tuple(j.geometry_fingerprint for j in explicit.jobs))

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
        base = self.system(products=products)
        profile_names = ("draft", "quality", "inner-base", "edge", "outer-base")
        system = CadSystem(
            base.name, base.description, base.path, base.models, base.products,
            base.default_product, base.libraries,
            MappingProxyType({
                name: CadProfile(name, f"system:{name}", "quality",
                                 Path(f"{name}.json"), {"mode": name}, {}, {},
                                 f"{index:x}" * 64)
                for index, name in enumerate(profile_names, 1)
            }), base.metadata_snapshot,
        )
        plan = build_render_plan(
            system, CadSelection(product="complete"),
            {"box": "source"},
        )
        self.assertEqual(len(plan.jobs), 2)
        self.assertEqual(plan.jobs[0].profile_ids, (
            "system:outer-base", "system:edge", "system:inner-base", "system:draft",
        ))
        self.assertEqual(plan.jobs[1].profile_ids[-1], "system:quality")
        self.assertNotEqual(plan.jobs[0].geometry_fingerprint,
                            plan.jobs[1].geometry_fingerprint)

    def test_slicing_only_sibling_variants_remain_distinct_and_overlay_deepest_outward(self):
        products = {
            "inner": product("inner", [
                item(model_id="box", set_name="floor", variant="fine",
                     slicing={"layer_height": 0.12, "supports": "recommended"}),
                item(model_id="box", set_name="floor", variant="coarse",
                     slicing={"layer_height": 0.28, "supports": "recommended"}),
            ], slicing={"supports": "discouraged", "adhesion": "small brim"}),
            "complete": product("complete", [
                item(product="inner", slicing={"adhesion": "large brim"}),
            ], slicing={"supports": "forbidden"}),
        }
        plan = build_render_plan(
            self.system(products=products), CadSelection(product="complete"),
            {"box": "source"},
        )
        self.assertEqual(len(plan.jobs), 2)
        self.assertEqual(plan.jobs[0].manufacturing.directives["layer_height"].value,
                         0.12)
        self.assertEqual(plan.jobs[0].manufacturing.directives["supports"].value,
                         "forbidden")
        self.assertEqual(plan.jobs[0].manufacturing.directives["adhesion"].value,
                         "large brim")
        self.assertEqual(plan.jobs[1].manufacturing.directives["layer_height"].value,
                         0.28)
        self.assertEqual(plan.jobs[0].geometry_fingerprint,
                         plan.jobs[1].geometry_fingerprint)
        self.assertNotEqual(plan.jobs[0].manufacturing_fingerprint,
                            plan.jobs[1].manufacturing_fingerprint)
        self.assertEqual(len({job.artifact_id for job in plan.jobs}), 2)

    def test_variant_names_use_one_global_collision_namespace(self):
        products = {
            "inner": product("inner", [
                item(model_id="box", set_name="floor", variant="a"),
                item(model_id="box", set_name="top", variant="a"),
            ]),
            "complete": product("complete", [
                item(product="inner"),
                item(model_id="holder", set_name="standard", variant="a-2"),
            ]),
        }
        plan = build_render_plan(
            self.system(products=products), CadSelection(product="complete"),
            {"box": "box", "holder": "holder"},
        )
        self.assertEqual(tuple(job.variant_name for job in plan.jobs),
                         ("a", "a-2", "a-2-2"))
        self.assertEqual(len({job.artifact_id for job in plan.jobs}), 3)

    def test_geometry_fingerprint_is_stable_sha256_and_changes_with_source(self):
        system = self.nested_system()
        first = build_render_plan(system, CadSelection(product="complete"),
                                  {"box": "a", "holder": "b"})
        again = build_render_plan(system, CadSelection(product="complete"),
                                  {"box": "a", "holder": "b"})
        self.assertEqual(tuple(j.geometry_fingerprint for j in first.jobs),
                         tuple(j.geometry_fingerprint for j in again.jobs))
        self.assertTrue(all(len(j.geometry_fingerprint) == 64 for j in first.jobs))
        self.assertTrue(all(bytes.fromhex(j.geometry_fingerprint) for j in first.jobs))
        changed = build_render_plan(system, CadSelection(product="complete"),
                                    {"box": "different", "holder": "b"})
        self.assertNotEqual(first.jobs[0].geometry_fingerprint,
                            changed.jobs[0].geometry_fingerprint)
        expected_manifest_hash = hashlib.sha256(
            json.dumps(dict(system.metadata_snapshot), sort_keys=True, separators=(",", ":"))
            .encode()
        ).hexdigest()
        self.assertIn(expected_manifest_hash, json.dumps(plan_as_dict(first)))

    def test_manufacturing_only_system_and_model_metadata_do_not_change_geometry(self):
        base = self.nested_system()
        first = build_render_plan(
            base, CadSelection(product="complete"), {"box": "scad", "holder": "holder"}
        ).jobs[0]
        changed_model = replace(
            base.models["box"],
            metadata_snapshot={"sets": {"floor": {"slicing": {"ironing": "recommended"}}}},
        )
        changed = CadSystem(
            base.name, "different description", base.path,
            MappingProxyType({**base.models, "box": changed_model}),
            base.products, base.default_product, base.libraries, base.profiles,
            MappingProxyType({"description": "manufacturing-only edit", "profiles": ["x"]}),
        )
        second = build_render_plan(
            changed, CadSelection(product="complete"),
            {"box": "scad", "holder": "holder"},
        ).jobs[0]
        self.assertEqual(first.geometry_fingerprint, second.geometry_fingerprint)
        self.assertNotEqual(first.manufacturing_fingerprint,
                            second.manufacturing_fingerprint)

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
            "raw_defines", "variable_sources", "profiles",
            "product_paths", "geometry_fingerprint", "manufacturing_fingerprint",
            "manufacturing",
        })

    def test_slicing_only_profile_preserves_geometry_but_changes_manufacturing(self):
        ironing = CadProfile(
            "ironing", "system:ironing", "quality", Path("ironing.json"),
            {}, {"ironing": "recommended"}, {}, "1" * 64,
        )
        base = self.system()
        system = CadSystem(
            base.name, base.description, base.path, base.models, base.products,
            base.default_product, base.libraries,
            MappingProxyType({"ironing": ironing}), base.metadata_snapshot,
        )
        plain = build_render_plan(
            system, CadSelection(model="box", sets=("top",)), {"box": "source"}
        ).jobs[0]
        profiled = build_render_plan(
            system,
            CadSelection(model="box", sets=("top",), profiles=("system:ironing",)),
            {"box": "source"},
        ).jobs[0]
        self.assertEqual(plain.geometry_fingerprint, profiled.geometry_fingerprint)
        self.assertNotEqual(plain.manufacturing_fingerprint,
                            profiled.manufacturing_fingerprint)
        self.assertEqual(profiled.profile_ids, ("system:ironing",))
        self.assertEqual(profiled.manufacturing.directives["ironing"].source.id,
                         "system:ironing")

    def test_geometry_hash_uses_effective_cad_values_not_profile_content(self):
        def configured(content_hash, cad, slicing=None, machine=None):
            profile = CadProfile(
                "mixed", "system:mixed", "quality", Path("cad/mixed.json"),
                cad, slicing or {}, machine or {}, content_hash,
            )
            base = self.system()
            return CadSystem(
                base.name, base.description, base.path, base.models, base.products,
                base.default_product, base.libraries,
                MappingProxyType({"mixed": profile}), base.metadata_snapshot,
            )

        selection = CadSelection(
            model="box", sets=("top",), profiles=("mixed",),
            defines={"clearance": 9},
        )
        first = build_render_plan(
            configured("1" * 64, {"clearance": 1, "render_fn": 24},
                       {"ironing": "optional"}, {"bed": "a"}),
            selection, {"box": "source"},
        ).jobs[0]
        non_geometry_change = build_render_plan(
            configured("2" * 64, {"clearance": 2, "render_fn": 24},
                       {"ironing": "recommended"}, {"bed": "b"}),
            selection, {"box": "source"},
        ).jobs[0]
        effective_change = build_render_plan(
            configured("3" * 64, {"clearance": 2, "render_fn": 48}),
            selection, {"box": "source"},
        ).jobs[0]

        self.assertEqual(first.geometry_fingerprint,
                         non_geometry_change.geometry_fingerprint)
        self.assertNotEqual(first.manufacturing_fingerprint,
                            non_geometry_change.manufacturing_fingerprint)
        self.assertNotEqual(first.geometry_fingerprint,
                            effective_change.geometry_fingerprint)

    def test_profile_provenance_is_qualified_immutable_and_serializable(self):
        profile = CadProfile(
            "draft", "system:draft", "quality", Path("cad/profiles/draft.json"),
            {"render_fn": 24}, {}, {}, "a" * 64,
        )
        base = self.system()
        system = CadSystem(
            base.name, base.description, base.path, base.models, base.products,
            base.default_product, base.libraries,
            MappingProxyType({"draft": profile}), base.metadata_snapshot,
        )
        job = build_render_plan(
            system, CadSelection(model="box", profiles=("draft",)),
            {"box": "source"}, repo_root=Path("."),
        ).jobs[0]
        provenance = job.profiles[0]
        self.assertEqual(provenance.qualified_id, "system:draft")
        self.assertEqual(provenance.namespace, "system")
        self.assertEqual(provenance.kind, "quality")
        self.assertEqual(provenance.content_hash, "a" * 64)
        self.assertEqual(provenance.path, "cad/profiles/draft.json")
        self.assertEqual(job.profile_ids, ("system:draft",))
        json.dumps(plan_as_dict(build_render_plan(
            system, CadSelection(model="box", profiles=("draft",)),
            {"box": "source"}, repo_root=Path("."),
        )))

    def test_defaults_profile_order_and_cad_precedence(self):
        def profile_value(name, value, hash_character):
            return CadProfile(name, f"system:{name}", "quality", Path(f"{name}.json"),
                              {"clearance": value}, {}, {}, hash_character * 64)
        profiles = MappingProxyType({
            "default": profile_value("default", 1, "1"),
            "product": profile_value("product", 2, "2"),
            "item": profile_value("item", 3, "3"),
            "model": profile_value("model", 3.2, "5"),
            "set": profile_value("set", 3.4, "6"),
            "cli": profile_value("cli", 4, "4"),
        })
        products = {"complete": product(
            "complete", [item(model_id="box", set_name="floor",
                              profiles=("item",), variables={"clearance": 5})],
            profiles=("product",),
        )}
        base = self.system(products=products)
        box = replace(
            base.models["box"], profiles=("model",),
            sets=MappingProxyType({
                name: replace(cad_set, profiles=("set",) if name == "floor" else ())
                for name, cad_set in base.models["box"].sets.items()
            }),
        )
        models = MappingProxyType({**base.models, "box": box})
        system = CadSystem(
            base.name, base.description, base.path, models, base.products,
            base.default_product, base.libraries, profiles, base.metadata_snapshot,
        )
        job = build_render_plan(
            system,
            CadSelection(product="complete", profiles=("cli",)),
            {"box": "source"}, default_profile_ids=("default",),
        ).jobs[0]
        self.assertEqual(job.profile_ids, (
            "system:default", "system:product", "system:item", "system:model",
            "system:set", "system:cli",
        ))
        self.assertEqual(job.variables["clearance"], 5)
        self.assertEqual(tuple(layer.kind for layer in job.variable_sources["clearance"].layers),
                         ("model", "profile", "profile", "profile", "profile",
                          "profile", "profile", "item"))
        without_defaults = build_render_plan(
            system,
            CadSelection(product="complete", profiles=("cli",),
                         use_default_profiles=False),
            {"box": "source"}, default_profile_ids=("default",),
        ).jobs[0]
        self.assertNotIn("system:default", without_defaults.profile_ids)

    def test_ambiguous_short_profile_and_hard_manufacturing_conflict_fail(self):
        system_profile = CadProfile(
            "draft", "system:draft", "quality", Path("system.json"), {}, {}, {}, "a" * 64
        )
        local_profile = CadProfile(
            "draft", "local:draft", "quality", Path("local.json"), {}, {}, {}, "b" * 64
        )
        base = self.system()
        system = CadSystem(
            base.name, base.description, base.path, base.models, base.products,
            base.default_product, base.libraries,
            MappingProxyType({"draft": system_profile}), base.metadata_snapshot,
        )
        with self.assertRaises(CadProfileError):
            build_render_plan(
                system,
                CadSelection(model="box", profiles=("draft",)), {"box": "source"},
                local_profiles={"draft": local_profile},
            )

        conflict_products = {"complete": product(
            "complete", [item(model_id="box", set_name="floor",
                              slicing={"supports": "required"})],
            slicing={"supports": "forbidden"},
        )}
        conflict = self.system(products=conflict_products)
        with self.assertRaisesRegex(ValueError, "Conflicting requirements"):
            build_render_plan(conflict, CadSelection(product="complete"),
                              {"box": "source"})


if __name__ == "__main__":
    unittest.main()
