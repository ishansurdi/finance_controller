"""Documented business rules for deterministic reconciliation."""

from fractions import Fraction

FEE_RATE = Fraction(2, 100)  # Contracted gateway fee used to validate captures.
GST_ON_FEE_RATE = Fraction(18, 100)  # Indian GST charged on the gateway fee.
SETTLEMENT_LAG_DAYS = 2  # Gateway settlements normally arrive at T+2.
TIMING_TOLERANCE_DAYS = 4  # Operations accepts delays through T+6 for auto-match.
ROUNDING_TOLERANCE_PAISE = 3  # Tiny processor rounding drift is operationally safe.
BATCH_MAX_MEMBERS = 6  # Bounds subset search and prevents speculative large groups.
CONFIDENCE_AUTO_MATCH = 0.90  # Lower-confidence cases require human review.

