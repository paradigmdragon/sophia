import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine.epidora import EpidoraValidator

def test_epidora_validator():
    validator = EpidoraValidator()

    # Test Case 1: Fixed Language (Error 1)
    text_error_1 = "The soul is always immutable."
    results_1 = validator.validate(text_error_1)
    assert len(results_1) > 0, "Failed to detect Error 1"
    print(f"Detected Error 1: {results_1[0]['match']}")
    assert results_1[0]['error_id'] == 1

    # Test Case 2: Discretization (Error 4)
    text_error_4 = "Is this good or bad?"
    results_4 = validator.validate(text_error_4)
    assert len(results_4) > 0, "Failed to detect Error 4"
    print(f"Detected Error 4: {results_4[0]['match']}")
    assert results_4[0]['error_id'] == 4

    # Test Case 3: Clean Text
    text_clean = "This is a dynamic process that evolves over time."
    results_clean = validator.validate(text_clean)
    assert len(results_clean) == 0, "False positive on clean text"

    print("All Epidora tests passed!")

if __name__ == "__main__":
    test_epidora_validator()
