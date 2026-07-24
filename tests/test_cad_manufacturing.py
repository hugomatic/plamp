import math
import unittest

from plamp.cad_manufacturing import (
    DirectiveSource,
    ManufacturingConflict,
    merge_manufacturing,
    manufacturing_fingerprint,
    normalize_slicing,
)


class CadManufacturingTests(unittest.TestCase):
    def source(self, source_id="set:top"):
        return DirectiveSource(source_id)

    def layer(self, source_id, slicing):
        return self.source(source_id), slicing

    def test_normalizes_every_portable_directive(self):
        directives, notes = normalize_slicing({
            "orientation": "as-exported",
            "supports": "forbidden",
            "support_style": "build-plate-only",
            "ironing": "recommended",
            "material": "PETG",
            "layer_height": 0.2,
            "minimum_perimeters": 3,
            "adhesion": "brim",
            "notes": ["Dry the filament.", "Iron the engraved face."],
        }, self.source())
        self.assertEqual(tuple(directives), (
            "orientation", "supports", "support_style", "ironing", "material",
            "layer_height", "minimum_perimeters", "adhesion",
        ))
        self.assertEqual(directives["supports"].strength, "requirement")
        self.assertEqual(directives["ironing"].strength, "preference")
        self.assertEqual(directives["layer_height"].strength, "preference")
        self.assertEqual(notes, (("set:top", "Dry the filament."),
                                 ("set:top", "Iron the engraved face.")))

    def test_explicit_strength_makes_scalar_a_requirement(self):
        directives, _ = normalize_slicing({
            "orientation": {"value": "as-exported", "strength": "required"},
            "layer_height": {"value": 0.16, "strength": "required"},
        }, self.source())
        self.assertEqual(directives["orientation"].strength, "requirement")
        self.assertEqual(directives["layer_height"].strength, "requirement")

    def test_profile_cannot_weaken_product_support_requirement(self):
        policy = merge_manufacturing((
            self.layer("product:box", {"supports": "required"}),
            self.layer("profile:draft", {"supports": "discouraged"}),
        ))
        self.assertEqual(policy.directives["supports"].value, "required")
        self.assertEqual(policy.directives["supports"].source.id, "product:box")

    def test_conflicting_hard_requirements_report_both_sources(self):
        with self.assertRaises(ManufacturingConflict) as caught:
            merge_manufacturing((
                self.layer("set:top", {"supports": "forbidden"}),
                self.layer("product:complete", {"supports": "required"}),
            ))
        self.assertEqual(caught.exception.sources, ("set:top", "product:complete"))

    def test_later_preference_wins_and_notes_remain_ordered(self):
        policy = merge_manufacturing((
            self.layer("set:top", {"material": "PLA", "notes": ["first"]}),
            self.layer("profile:petg", {"material": "PETG", "notes": ["second"]}),
        ))
        self.assertEqual(policy.directives["material"].value, "PETG")
        self.assertEqual(policy.notes, (("set:top", "first"),
                                        ("profile:petg", "second")))

    def test_equal_requirements_are_not_a_conflict(self):
        policy = merge_manufacturing((
            self.layer("set:a", {"supports": "forbidden"}),
            self.layer("product:b", {"supports": "forbidden"}),
        ))
        self.assertEqual(policy.directives["supports"].source.id, "set:a")

    def test_rejects_invalid_values_and_unknown_keys(self):
        invalid = (
            {"supports": "sometimes"}, {"ironing": "yes"},
            {"orientation": ""}, {"support_style": ""}, {"material": ""},
            {"layer_height": 0}, {"layer_height": math.inf},
            {"minimum_perimeters": 0}, {"minimum_perimeters": 2.5},
            {"adhesion": ""}, {"notes": "not-an-array"}, {"notes": [1]},
            {"mystery": True},
            {"material": {"value": "PETG", "strength": "maybe"}},
        )
        for slicing in invalid:
            with self.subTest(slicing=slicing), self.assertRaises(ValueError):
                normalize_slicing(slicing, self.source())

    def test_policy_is_immutable_and_fingerprint_is_stable(self):
        first = merge_manufacturing((self.layer("set:top", {
            "material": "PETG", "supports": "forbidden", "notes": ["hello"],
        }),))
        second = merge_manufacturing((self.layer("set:top", {
            "material": "PETG", "supports": "forbidden", "notes": ["hello"],
        }),))
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.fingerprint, manufacturing_fingerprint(
            first.directives, first.notes))
        self.assertEqual(len(first.fingerprint), 64)
        with self.assertRaises(TypeError):
            first.directives["material"] = None
        changed = merge_manufacturing((self.layer("set:top", {
            "material": "PLA", "supports": "forbidden", "notes": ["hello"],
        }),))
        self.assertNotEqual(first.fingerprint, changed.fingerprint)


if __name__ == "__main__":
    unittest.main()
