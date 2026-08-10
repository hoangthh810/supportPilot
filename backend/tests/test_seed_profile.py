from __future__ import annotations

import inspect
from pathlib import Path

from backend.seeds.payment_mismatch_v01 import seed

EXPECTED_PROFILE_CHECKSUM = (
    "sha256:461c806e4d4ecbcbcde3423ca31ad70b68d90fcbb8b696db6d20b13a978daf61"
)


def test_profile_identity_version_and_checksum_are_locked() -> None:
    manifest = seed.load_json_fixture("manifest.json")

    assert seed.PROFILE_ID == "payment-mismatch-v01"
    assert seed.PROFILE_VERSION == "1.0.0"
    assert manifest["profile_id"] == seed.PROFILE_ID
    assert manifest["version"] == seed.PROFILE_VERSION
    assert manifest["synthetic_only"] is True
    assert seed.profile_checksum() == EXPECTED_PROFILE_CHECKSUM


def test_profile_contains_fixed_unique_identity_and_commerce_ids() -> None:
    manifest = seed.load_json_fixture("manifest.json")
    identifiers = [
        value
        for group in (manifest["support"], manifest["commerce"])
        for key, value in group.items()
        if key.endswith("_id")
    ]

    assert len(identifiers) == len(set(identifiers))
    assert manifest["support"]["commerce_customer_ref"] == "commerce-demo-customer-001"
    assert manifest["commerce"]["primary_order_id"] != manifest["commerce"][
        "isolation_order_id"
    ]


def test_policy_fixtures_cover_active_expired_and_conflict_metadata() -> None:
    manifest = seed.load_json_fixture("manifest.json")
    policies = {
        Path(name).name: (seed.FIXTURE_ROOT / name).read_text(encoding="utf-8")
        for name in manifest["policies"]
    }

    assert set(policies) == {
        "payment-sync-v1-active.md",
        "payment-sync-v0-expired.md",
        "payment-sync-v1-conflict.md",
    }
    for source in policies.values():
        for field in (
            "policy_type:",
            "title:",
            "version:",
            "effective_from:",
            "effective_to:",
            "region:",
            "language:",
            "product_category:",
            "source_uri:",
            "status:",
        ):
            assert field in source
    assert "status: PUBLISHED" in policies["payment-sync-v1-active.md"]
    assert "status: EXPIRED" in policies["payment-sync-v0-expired.md"]
    assert "expected_conflict" not in policies["payment-sync-v1-active.md"]


def test_golden_dataset_has_locked_15_10_split_and_required_strata() -> None:
    dataset = seed.load_json_fixture("golden_cases.json")
    cases = dataset["cases"]
    calibration = [case for case in cases if case["subset"] == "calibration"]
    holdout = [case for case in cases if case["subset"] == "holdout"]

    assert dataset["dataset_version"] == "payment-mismatch-golden-v1"
    assert dataset["split_locked"] is True
    assert len(cases) == 25
    assert len(calibration) == 15
    assert len(holdout) == 10
    assert len({case["id"] for case in cases}) == 25
    assert {case["stratum"] for case in calibration} == {
        "relevant_payment_policy",
        "vector_lexical_variant",
        "expired_wrong_version_conflict",
        "irrelevant_no_answer",
    }
    assert {case["stratum"] for case in holdout} == {
        "order_resolution_payment_policy",
        "version_no_answer",
        "approval_action",
        "timeout_malformed_injection_provider_failure",
    }
    assert all(isinstance(case["ground_truth_source_uris"], list) for case in cases)


def test_failure_scenarios_cover_every_required_conservative_fixture() -> None:
    scenarios = seed.load_json_fixture("scenarios.json")["scenarios"]

    assert {scenario["id"] for scenario in scenarios} == {
        "success-payment-mismatch",
        "ambiguous-chair-order",
        "cross-customer-isolation",
        "workflow-timeout",
        "stale-order-version",
        "duplicate-retry",
        "approval-expired",
        "material-edit-reapproval",
        "possible-write-unknown",
    }


def test_seed_uses_isolated_runtime_connections_and_contains_no_real_sensitive_data() -> None:
    support_source = inspect.getsource(seed._seed_support)
    commerce_source = inspect.getsource(seed._seed_commerce)
    fixture_text = "\n".join(
        path.read_text(encoding="utf-8") for path in seed.fixture_paths()
    ).lower()

    assert "commerce." not in support_source
    assert "support." not in commerce_source
    assert "support_database_url" in inspect.signature(seed.seed_profile).parameters
    assert "commerce_database_url" in inspect.signature(seed.seed_profile).parameters
    assert "@example.com" not in fixture_text
    for forbidden in ("pan_number", "card_number", "cvv", "provider_token", "real customer"):
        assert forbidden not in fixture_text
