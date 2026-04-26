from services.recommendation_presentation import (
    CONFIDENCE_SCORE_HIGH,
    confidence_level_from_01,
    confidence_01_from_review_claim,
)


def test_confidence_thresholds():
    assert confidence_level_from_01(0.75) == "high"
    assert confidence_level_from_01(0.76) == "high"
    assert confidence_level_from_01(0.4) == "medium"
    assert confidence_level_from_01(0.74) == "medium"
    assert confidence_level_from_01(0.39) == "low"
    assert CONFIDENCE_SCORE_HIGH == 0.75


def test_confidence_01_saturated_high():
    from review_claims import (
        Audit,
        ClaimConfidenceSummary,
        ConsumerResponse,
        EvidenceSummary,
        ImpactAssessment,
        ReviewClaim,
        ReviewType,
    )

    rc = ReviewClaim(
        review_claim_id="t1",
        review_type=ReviewType.NEGATIVE_IMPACT,
        summary="x",
        question="q",
        entities={},
        supporting_claim_ids=[],
        evidence_summary=EvidenceSummary(
            claim_confidence_summary=ClaimConfidenceSummary(high=2, medium=0, low=0)
        ),
        consumer_response=ConsumerResponse(),
        impact_assessment=ImpactAssessment(),
        audit=Audit(),
    )
    s = confidence_01_from_review_claim(rc)
    assert s >= 0.75
    assert confidence_level_from_01(s) == "high"
